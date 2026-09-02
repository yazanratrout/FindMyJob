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


class LlmClient:
    def __init__(
        self,
        *,
        settings: Settings | None = None,
        api_fn: ApiFn | None = None,
    ) -> None:
        self._settings = settings or get_settings()
        self._api_fn = api_fn or _anthropic_call

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
