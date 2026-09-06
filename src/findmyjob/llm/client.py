"""A small wrapper over the Anthropic API.

What it adds over the raw SDK:

* **model routing** by tier (``cheap`` / ``smart``);
* a **content-addressed cache** (identical prompts are free on repeat);
* **token + cost accounting** written to ``llm_call`` and rolled onto the run;
* **JSON mode** with one automatic repair retry and schema validation;
* **testability** — the network call is a single injectable function.

Nothing here knows about jobs, profiles or cover letters. Callers build the
prompt; this sends it.
"""

from __future__ import annotations

import hashlib
import json
import re
from collections.abc import Callable
from dataclasses import dataclass
from typing import Any, Literal, TypeVar

from pydantic import BaseModel, ValidationError

from findmyjob.config import Settings, get_settings
from findmyjob.db import session_scope
from findmyjob.logging import get_logger
from findmyjob.models.enums import LlmPurpose
from findmyjob.models.llm_cache import LlmCacheEntry
from findmyjob.models.run import LlmCall

log = get_logger("llm")

Tier = Literal["cheap", "smart"]
TModel = TypeVar("TModel", bound=BaseModel)


class LlmError(RuntimeError):
    """Raised when the model call fails or returns unusable output."""


@dataclass(slots=True)
class RawCompletion:
    text: str
    input_tokens: int
    output_tokens: int


@dataclass(slots=True)
class LlmResult:
    text: str
    model: str
    tier: Tier
    input_tokens: int
    output_tokens: int
    cost_eur: float
    cache_hit: bool


ApiFn = Callable[[str, str, str, int, float], RawCompletion]


def _anthropic_call(
    model: str, system: str, user: str, max_tokens: int, temperature: float
) -> RawCompletion:
    import anthropic  # imported lazily so tests never need the package configured

    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LlmError("ANTHROPIC_API_KEY is not set")
    client = anthropic.Anthropic(api_key=settings.anthropic_api_key)
    message = client.messages.create(  # type: ignore[call-overload]
        model=model,
        max_tokens=max_tokens,
        temperature=temperature,
        system=system,
        messages=[{"role": "user", "content": user}],
    )
    text = "".join(getattr(block, "text", "") for block in message.content if block.type == "text")
    return RawCompletion(
        text=text,
        input_tokens=message.usage.input_tokens,
        output_tokens=message.usage.output_tokens,
    )


_RETRY_AFTER_RE = re.compile(r"try again in ([0-9.]+)\s*s", re.IGNORECASE)
_MAX_RATE_LIMIT_WAIT = 75.0  # give up rather than stall a run for minutes


def _retry_after_seconds(resp: Any) -> float | None:
    """How long a 429 asks us to wait: the header, or the hint in the body."""
    header = resp.headers.get("retry-after")
    if header:
        try:
            return min(float(header), _MAX_RATE_LIMIT_WAIT)
        except ValueError:
            pass
    match = _RETRY_AFTER_RE.search(resp.text or "")
    if match:
        return min(float(match.group(1)) + 0.5, _MAX_RATE_LIMIT_WAIT)
    return None


def _openai_compatible_call(
    model: str, system: str, user: str, max_tokens: int, temperature: float
) -> RawCompletion:
    """Any OpenAI-style ``/chat/completions`` endpoint (Groq, Gemini shim, Ollama...).

    Uses ``httpx`` directly - no extra dependency. Auth is optional so a local
    Ollama with no key works. Honours a 429 ``Retry-After`` (free tiers rate-limit
    aggressively) up to a cap, then gives up so a run cannot stall for minutes.
    """
    import time

    import httpx

    settings = get_settings()
    base = (settings.llm_openai_base_url or "").rstrip("/")
    if not base:
        raise LlmError("LLM_OPENAI_BASE_URL is not set (LLM_PROVIDER=openai)")
    headers = {"content-type": "application/json"}
    if settings.llm_openai_api_key:
        headers["authorization"] = f"Bearer {settings.llm_openai_api_key}"
    payload = {
        "model": model,
        "temperature": temperature,
        "max_tokens": max_tokens,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": user},
        ],
    }
    url = f"{base}/chat/completions"
    for attempt in range(4):
        try:
            resp = httpx.post(url, json=payload, headers=headers, timeout=120.0)
            if resp.status_code == 429 and attempt < 3:
                wait = _retry_after_seconds(resp)
                if wait is not None:
                    log.info("llm.rate_limited", model=model, wait_s=round(wait, 1))
                    time.sleep(wait)
                    continue
            resp.raise_for_status()
            data = resp.json()
            break
        except httpx.HTTPStatusError as exc:
            body = exc.response.text[:300]
            raise LlmError(f"{model}: HTTP {exc.response.status_code} - {body}") from exc
        except httpx.HTTPError as exc:
            raise LlmError(f"{model}: request failed - {exc}") from exc
    else:
        raise LlmError(f"{model}: still rate-limited after retries")

    try:
        text = data["choices"][0]["message"]["content"] or ""
    except (KeyError, IndexError, TypeError) as exc:
        raise LlmError(f"{model}: unexpected response shape - {str(data)[:300]}") from exc
    usage = data.get("usage") or {}
    return RawCompletion(
        text=text,
        input_tokens=int(usage.get("prompt_tokens", 0)),
        output_tokens=int(usage.get("completion_tokens", 0)),
    )


def _default_api_fn(settings: Settings) -> ApiFn:
    return _openai_compatible_call if settings.llm_provider == "openai" else _anthropic_call


class LlmClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_fn: ApiFn | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        #: offline stub mode — only when nobody injected a real/fake api_fn
        self._offline = api_fn is None and self._settings.llm_offline
        self._api_fn = api_fn or _default_api_fn(self._settings)

    # ---- public API -------------------------------------------------

    def complete(
        self,
        *,
        purpose: LlmPurpose,
        system: str,
        user: str,
        tier: Tier = "cheap",
        max_tokens: int = 2048,
        temperature: float = 0.0,
        run_id: int | None = None,
        use_cache: bool = True,
    ) -> LlmResult:
        model = self._model_for(tier)

        if self._offline:
            raw = _offline_completion(purpose)
            self._record_call(purpose, model, raw.input_tokens, raw.output_tokens, run_id, cost=0.0)
            log.info("llm.offline_stub", purpose=purpose.value)
            return LlmResult(
                text=raw.text,
                model=f"offline/{model}",
                tier=tier,
                input_tokens=raw.input_tokens,
                output_tokens=raw.output_tokens,
                cost_eur=0.0,
                cache_hit=False,
            )

        key = self._cache_key(purpose, model, system, user)

        if use_cache and (cached := self._cache_get(key)) is not None:
            self._record_call(
                purpose,
                model,
                cached.input_tokens,
                cached.output_tokens,
                run_id,
                cache_hit=True,
            )
            log.info("llm.cache_hit", purpose=purpose.value, model=model)
            return LlmResult(
                text=cached.response_text,
                model=model,
                tier=tier,
                input_tokens=cached.input_tokens,
                output_tokens=cached.output_tokens,
                cost_eur=0.0,
                cache_hit=True,
            )

        try:
            raw = self._api_fn(model, system, user, max_tokens, temperature)
        except LlmError:
            raise
        except Exception as exc:  # wrap any SDK error
            self._record_call(purpose, model, 0, 0, run_id, ok=False, error=str(exc))
            raise LlmError(f"{purpose.value} call failed: {exc}") from exc

        cost = self._cost(tier, raw.input_tokens, raw.output_tokens)
        if use_cache:
            self._cache_put(key, purpose, model, raw)
        self._record_call(purpose, model, raw.input_tokens, raw.output_tokens, run_id, cost=cost)
        log.info(
            "llm.call",
            purpose=purpose.value,
            model=model,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cost_eur=round(cost, 4),
        )
        return LlmResult(
            text=raw.text,
            model=model,
            tier=tier,
            input_tokens=raw.input_tokens,
            output_tokens=raw.output_tokens,
            cost_eur=cost,
            cache_hit=False,
        )

    def complete_json(
        self,
        *,
        purpose: LlmPurpose,
        system: str,
        user: str,
        schema: type[TModel],
        tier: Tier = "cheap",
        max_tokens: int = 2048,
        run_id: int | None = None,
        use_cache: bool = True,
    ) -> tuple[TModel, LlmResult]:
        """Return a validated model instance, retrying once on malformed JSON."""
        json_system = (
            system + "\n\nReturn ONLY a single valid JSON object. No prose, no markdown fences."
        )
        result = self.complete(
            purpose=purpose,
            system=json_system,
            user=user,
            tier=tier,
            max_tokens=max_tokens,
            run_id=run_id,
            use_cache=use_cache,
        )
        try:
            return schema.model_validate(_loads(result.text)), result
        except (ValueError, ValidationError) as first_error:
            repair_user = (
                f"{user}\n\nYour previous reply could not be parsed as JSON matching the "
                f"schema. Error: {first_error}. Reply again with ONLY the corrected JSON object."
            )
            retry = self.complete(
                purpose=purpose,
                system=json_system,
                user=repair_user,
                tier=tier,
                max_tokens=max_tokens,
                run_id=run_id,
                use_cache=False,
            )
            try:
                return schema.model_validate(_loads(retry.text)), retry
            except (ValueError, ValidationError) as exc:
                raise LlmError(f"{purpose.value}: invalid JSON after repair: {exc}") from exc

    # ---- internals -----------------------------------------------

    def _model_for(self, tier: Tier) -> str:
        return self._settings.llm_model_smart if tier == "smart" else self._settings.llm_model_cheap

    def _cost(self, tier: Tier, input_tokens: int, output_tokens: int) -> float:
        # The price table is Anthropic's; an OpenAI-compatible endpoint (often a
        # free tier) is billed elsewhere, so record 0 and let its own quota apply.
        if self._settings.llm_provider != "anthropic":
            return 0.0
        if tier == "smart":
            price_in, price_out = (
                self._settings.llm_price_smart_in,
                self._settings.llm_price_smart_out,
            )
        else:
            price_in, price_out = (
                self._settings.llm_price_cheap_in,
                self._settings.llm_price_cheap_out,
            )
        return input_tokens / 1_000_000 * price_in + output_tokens / 1_000_000 * price_out

    @staticmethod
    def _cache_key(purpose: LlmPurpose, model: str, system: str, user: str) -> str:
        blob = "\x1f".join([purpose.value, model, system, user]).encode("utf-8")
        return hashlib.sha256(blob).hexdigest()

    def _cache_get(self, key: str) -> LlmCacheEntry | None:
        with session_scope() as session:
            entry = session.get(LlmCacheEntry, key)
            if entry is not None:
                session.expunge(entry)
            return entry

    def _cache_put(self, key: str, purpose: LlmPurpose, model: str, raw: RawCompletion) -> None:
        with session_scope() as session:
            if session.get(LlmCacheEntry, key) is not None:
                return
            session.add(
                LlmCacheEntry(
                    key=key,
                    purpose=purpose.value,
                    model=model,
                    response_text=raw.text,
                    input_tokens=raw.input_tokens,
                    output_tokens=raw.output_tokens,
                )
            )

    def _record_call(
        self,
        purpose: LlmPurpose,
        model: str,
        input_tokens: int,
        output_tokens: int,
        run_id: int | None,
        *,
        ok: bool = True,
        cache_hit: bool = False,
        cost: float = 0.0,
        error: str | None = None,
    ) -> None:
        with session_scope() as session:
            session.add(
                LlmCall(
                    run_id=run_id,
                    purpose=purpose,
                    model=model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    cost_eur=cost,
                    cache_hit=cache_hit,
                    ok=ok,
                    error=error,
                )
            )


_OFFLINE_JSON: dict[LlmPurpose, dict[str, Any]] = {
    LlmPurpose.PROFILE_PARSE: {
        "full_name": "Offline Test User",
        "email": "test@example.com",
        "nationality": "German",
        "university": "TU München",
        "program": "M.Sc. Data Engineering",
        "degree_level": "master",
        "current_semester": 3,
        "skills": [
            {
                "name": "Python",
                "category": "technical",
                "proficiency": 4,
                "evidence": "offline stub",
            },
            {"name": "SQL", "category": "technical", "proficiency": 4, "evidence": "offline stub"},
        ],
        "languages": [
            {"lang": "German", "cefr": "C2"},
            {"lang": "English", "cefr": "C1"},
        ],
        "highlights_from_references": ["Reliable and quick to onboard (offline stub)."],
    },
    LlmPurpose.KEYWORD_SUGGEST: {
        "core": ["Werkstudent Data", "Working Student Analytics", "Data Engineering"],
        "adjacent": ["Business Intelligence", "Machine Learning"],
        "tools": ["Python", "SQL", "dbt", "Airflow"],
        "likely_noise": ["Senior", "Vollzeit", "Head of"],
    },
    LlmPurpose.ANALYZE: {
        "must_haves": ["Enrolled student", "Python", "SQL"],
        "nice_haves": ["dbt", "Cloud (AWS/GCP)"],
        "skills": [
            {"name": "Python", "required": True},
            {"name": "SQL", "required": True},
            {"name": "dbt", "required": False},
        ],
        "languages": [
            {"lang": "German", "cefr": "B2", "required": False},
            {"lang": "English", "cefr": "B2", "required": True},
        ],
        "weekly_hours": 20,
        "weekly_hours_basis": "stated",
        "contract_type": "werkstudent",
        "enrollment_required": "yes",
        "application_method": "ats_form",
        "documents_requested": ["cv", "enrollment"],
        "seniority": "student",
        "red_flags": [],
        "source_snippets": {
            "weekly_hours": "20 hours per week during the semester (offline stub).",
            "contract_type": "Werkstudentenstelle (offline stub).",
        },
    },
    LlmPurpose.JUDGE: {
        "holistic_fit": 68,
        "rationale": "Offline stub judgement: solid overlap on core skills; "
        "German level and exact tooling are the main open questions.",
        "missing_qualifications": ["Hands-on dbt experience"],
        "strengths_to_highlight": ["Python + SQL depth", "Current enrolment"],
        "recommendation": "maybe",
    },
    LlmPurpose.COVER_LETTER: {
        "language": "en",
        "recipient": {"company": "The Company"},
        "subject": "Application as Working Student - Offline Test User",
        "salutation": "Dear Hiring Team,",
        "paragraphs": [
            "This letter was produced by FindMyJob's offline stub, so treat the wording "
            "as a placeholder - the layout, editing and DOCX export are what it exercises.",
            "My background in Python and SQL lines up with the core requirements in the "
            "posting, and I am currently enrolled full-time.",
            "I can offer around 20 hours per week during the semester and more during breaks, "
            "and I am available to start immediately.",
            "I would be glad to discuss how I can help - thank you for your time.",
        ],
        "closing": "Kind regards",
        "claims_used": [
            {"claim": "Python and SQL experience", "evidence_from_profile": "skills: Python, SQL"},
            {
                "claim": "Currently enrolled",
                "evidence_from_profile": "M.Sc. Data Engineering, sem 3",
            },
        ],
    },
}


def _offline_completion(purpose: LlmPurpose) -> RawCompletion:
    payload = _OFFLINE_JSON.get(purpose, {})
    text = json.dumps(payload, ensure_ascii=False)
    return RawCompletion(text=text, input_tokens=0, output_tokens=0)


def _loads(text: str) -> Any:
    """Parse JSON, tolerating markdown fences and leading/trailing prose."""
    cleaned = text.strip()
    if cleaned.startswith("```"):
        cleaned = cleaned.split("```", 2)[1]
        if cleaned.lstrip().startswith("json"):
            cleaned = cleaned.lstrip()[4:]
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start != -1 and end != -1 and end > start:
        cleaned = cleaned[start : end + 1]
    return json.loads(cleaned)
