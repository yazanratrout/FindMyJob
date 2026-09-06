"""Deterministic hard filters and the weighted soft score.

Pure functions — no DB, no network. The `prefilter` and `score` pipelines feed
them rows and persist the results.

* **Hard checks** disqualify a job outright, and *only* when the matching
  constraint is marked "hard" in settings. Split into cheap checks (need only
  the `Job` row) and analysis checks (need a `JobAnalysis`).
* **Soft score** is 0-100: each component is 0..1, multiplied by its weight,
  summed and normalized. Weights come from `AppSettings.weights`.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from findmyjob.models.base import utcnow
from findmyjob.models.config import AppSettings
from findmyjob.models.enums import CEFR_ORDER, Decision
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.normalize import fold_accents, location_mentions_city

_STUDENT_SENIORITY = {"student", "entry", "junior"}


@dataclass(slots=True)
class HardResult:
    passed: bool
    failures: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SoftScore:
    score: float
    breakdown: dict[str, dict[str, float]]


# --------------------------------------------------------------------- buckets
def bucket(final_score: float, settings: AppSettings) -> Decision:
    if final_score >= settings.score_threshold_recommend:
        return Decision.RECOMMENDED
    if final_score >= settings.score_threshold_maybe:
        return Decision.MAYBE
    return Decision.ARCHIVED


# ----------------------------------------------------------------- hard checks
def cheap_hard_checks(
    job: Job, settings: AppSettings, *, now: datetime | None = None
) -> HardResult:
    now = now or utcnow()
    failures: list[str] = []

    if job.posted_at is not None:
        age_days = (now - job.posted_at).days
        if age_days > settings.recency_days:
            failures.append("recency")

    haystack = f"{job.title}\n{job.jd_text or ''}".lower()
    for keyword in settings.keywords_block:
        if keyword and keyword.lower() in haystack:
            failures.append(f"blacklist:{keyword.lower()}")
            break

    if not _location_ok(job, settings):
        failures.append("location")

    return HardResult(not failures, failures)


def _location_ok(job: Job, settings: AppSettings) -> bool:
    if job.is_remote and settings.allow_remote:
        return True
    if not settings.target_city or not job.location_raw:
        return True  # nothing to check against / benefit of the doubt
    return location_mentions_city(job.location_raw, settings.target_city)


def _cefr(level: str | None) -> int:
    return CEFR_ORDER.get((level or "").upper(), 0) if level else 0


def analysis_hard_checks(
    analysis: JobAnalysis,
    profile_languages: dict[str, str],
    settings: AppSettings,
) -> HardResult:
    failures: list[str] = []

    if (
        settings.hours_hard
        and analysis.weekly_hours is not None
        and analysis.weekly_hours > settings.hours_max
    ):
        failures.append("hours")

    if settings.language_hard:
        cap = _cefr(settings.language_max_cefr)
        for lang in analysis.languages:
            if not lang.get("required", True):
                continue
            need = _cefr(lang.get("cefr"))
            have = _cefr(profile_languages.get(str(lang.get("lang", "")).lower()))
            if need and need > cap and have < need:
                failures.append(f"language:{str(lang.get('lang', '')).lower()}")

    contract = _contract_str(analysis)
    if contract == "full_time":
        failures.append("job_type")
    elif settings.contract_type_hard and contract not in {*settings.contract_types, "unknown"}:
        failures.append("contract_type")

    return HardResult(not failures, failures)


def _contract_str(analysis: JobAnalysis) -> str:
    value = analysis.contract_type
    return value.value if hasattr(value, "value") else str(value)


# ----------------------------------------------------------------- soft score
def compute_soft_score(
    *,
    job: Job,
    analysis: JobAnalysis,
    profile_skills: list[str],
    profile_languages: dict[str, str],
    settings: AppSettings,
    company_affinity: float,
    now: datetime | None = None,
) -> SoftScore:
    now = now or utcnow()
    components: dict[str, float] = {
        "skills_match": _skills_match(analysis, profile_skills),
        "field_relevance": _field_relevance(job, analysis, settings),
        "language_fit": _language_fit(analysis, profile_languages, settings),
        "hours_fit": _hours_fit(analysis, settings),
        "seniority_fit": _seniority_fit(analysis),
        "recency": _recency(job, settings, now),
        "salary_fit": _salary_fit(analysis),
        "company_affinity": company_affinity,
    }
    weights = {k: float(settings.weights.get(k, 0.0)) for k in components}
    total_w = sum(weights.values()) or 1.0
    weighted = sum(components[k] * weights[k] for k in components)
    breakdown = {
        k: {
            "raw": round(components[k], 3),
            "weight": weights[k],
            "contribution": round(components[k] * weights[k], 3),
        }
        for k in components
    }
    return SoftScore(score=round(100 * weighted / total_w, 1), breakdown=breakdown)


def _tokens(text: str, *, min_len: int = 3) -> set[str]:
    """Word set for overlap comparisons.

    ``min_len`` drops filler; pass 2 where short acronyms carry real meaning
    ("AI", "ML", "BI", "UX") - those are exactly the fields a student targets.
    """
    cleaned = fold_accents(text).lower().replace("/", " ").replace(",", " ")
    return {t.strip("()&.-") for t in cleaned.split() if len(t.strip("()&.-")) >= min_len}


#: two-letter noise that would otherwise slip in once ``min_len`` drops to 2.
_SHORT_STOPWORDS: frozenset[str] = frozenset(
    {"de", "en", "im", "in", "am", "an", "zu", "of", "or", "to", "the", "und", "and", "for"}
)


#: job-type / contract words carry no field signal - they must not let an
#: off-topic posting borrow relevance just because it is a "Werkstudent" role.
_NON_FIELD_WORDS: frozenset[str] = frozenset(
    {
        "werkstudent",
        "werkstudentin",
        "working",
        "student",
        "studentin",
        "students",
        "studentische",
        "hilfskraft",
        "praktikum",
        "praktikant",
        "praktikantin",
        "intern",
        "internship",
        "trainee",
        "minijob",
        "thesis",
        "abschlussarbeit",
        "teilzeit",
        "vollzeit",
        "part",
        "time",
        "full",
        "job",
        "stelle",
        "position",
        "role",
        "bereich",
        "schwerpunkt",
    }
)


def _skills_match(analysis: JobAnalysis, profile_skills: list[str]) -> float:
    skills = analysis.skills
    if not skills:
        return 0.4  # no identifiable skill requirements - a weak signal, not neutral
    have = {s.lower() for s in profile_skills}
    have_tokens = set().union(*(_tokens(s) for s in profile_skills)) if profile_skills else set()
    matched_w = total_w = 0.0
    for skill in skills:
        name = str(skill.get("name", "")).lower()
        weight = 2.0 if skill.get("required") else 1.0
        total_w += weight
        if name in have or _tokens(name) & have_tokens:
            matched_w += weight
    return matched_w / total_w if total_w else 0.5


def _field_relevance(job: Job, analysis: JobAnalysis, settings: AppSettings) -> float:
    """How much this posting is *about* the user's subject - not just a role of the
    right shape.

    Compared against ``target_fields`` and the posting's title / skills /
    requirements. Job-type words are stripped from both sides so an off-field
    "Werkstudent ..." cannot borrow relevance, and short acronyms ("AI", "ML")
    are kept because they are usually the whole point of the search.

    ``keywords_allow`` is deliberately *not* folded in: measured against live
    postings it mostly duplicates the fields, inflating the denominator and
    demoting genuinely on-topic roles.
    """
    noise = _NON_FIELD_WORDS | _SHORT_STOPWORDS
    target = _tokens(" ".join(settings.target_fields), min_len=2) - noise
    if not target:
        return 0.6
    skill_names = " ".join(str(s.get("name", "")) for s in analysis.skills)
    text = (
        _tokens(
            f"{job.title} {skill_names} "
            f"{' '.join(analysis.must_haves)} {' '.join(analysis.nice_haves)}",
            min_len=2,
        )
        - noise
    )
    if not text:
        return 0.35
    overlap = len(text & target) / len(target)
    return max(0.0, min(1.0, 0.12 + overlap * 2.2))


def _language_fit(
    analysis: JobAnalysis, profile_languages: dict[str, str], settings: AppSettings
) -> float:
    required = [lang for lang in analysis.languages if lang.get("required", True)]
    if not required:
        return 1.0
    cap = _cefr(settings.language_max_cefr)
    fits: list[float] = []
    for lang in required:
        need = _cefr(lang.get("cefr")) or cap
        have = _cefr(profile_languages.get(str(lang.get("lang", "")).lower())) or cap
        if have >= need:
            fits.append(1.0)
        elif need - have == 1:
            fits.append(0.5)
        else:
            fits.append(0.15)
    return min(fits)


def _hours_fit(analysis: JobAnalysis, settings: AppSettings) -> float:
    hours = analysis.weekly_hours
    if hours is None or hours <= settings.hours_max:
        return 1.0
    over = hours - settings.hours_max
    return max(0.0, 1.0 - over / 15.0)


def _seniority_fit(analysis: JobAnalysis) -> float:
    seniority = (analysis.seniority or "unknown").lower()
    if seniority in _STUDENT_SENIORITY:
        return 1.0
    if seniority == "mid":
        return 0.4
    return 0.7


def _recency(job: Job, settings: AppSettings, now: datetime) -> float:
    if job.posted_at is None:
        return 0.7
    age = (now - job.posted_at).days
    return max(0.0, 1.0 - age / max(settings.recency_days, 1))


def _salary_fit(analysis: JobAnalysis) -> float:
    return 0.8 if analysis.salary_min or analysis.salary_max else 0.6
