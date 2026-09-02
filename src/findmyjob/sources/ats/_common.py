"""Shared base + filters for connectors that iterate over curated companies."""

from __future__ import annotations

from typing import ClassVar

from findmyjob.config import Settings
from findmyjob.logging import get_logger
from findmyjob.normalize import fold_accents
from findmyjob.services.http import HttpClient
from findmyjob.sources._parsing import is_recent, matches_any_keyword
from findmyjob.sources.base import CompanyRef, JobSource, RawJob, SourceQuery

log = get_logger("source.ats")

# Common English/German spellings for German cities, so a curated company's
# English-language posting isn't dropped by a German target city (and vice versa).
_CITY_ALIASES: dict[str, set[str]] = {
    "muenchen": {"munich", "muenchen", "munchen", "monaco di baviera"},
    "koeln": {"cologne", "koeln", "koln"},
    "nuernberg": {"nuremberg", "nuernberg"},
    "wien": {"vienna", "wien"},
    "zuerich": {"zurich", "zuerich"},
}


def _city_tokens(city: str) -> set[str]:
    base = fold_accents(city).lower().strip()
    return _CITY_ALIASES.get(base, {base}) if base else set()


# Title cues that mark a student-suitable role, by our job-type vocabulary.
_JOB_TYPE_CUES: dict[str, tuple[str, ...]] = {
    "werkstudent": ("werkstudent", "working student"),
    "student_assistant": ("student assistant", "studentische hilfskraft", "hiwi"),
    "praktikum": ("praktik", "intern", "internship"),
    "thesis": ("thesis", "abschlussarbeit", "bachelorarbeit", "masterarbeit"),
    "minijob": ("minijob", "aushilfe"),
}


def role_is_wanted(title: str, text: str, query: SourceQuery) -> bool:
    """Keep a posting if it matches the user's keywords or a student-role cue."""
    if matches_any_keyword(f"{title}\n{text[:1500]}", query.keywords):
        return True
    cues = tuple(cue for jt in query.job_types for cue in _JOB_TYPE_CUES.get(jt, ()))
    lowered = title.lower()
    return any(cue in lowered for cue in cues)


def location_ok(location: str | None, is_remote: bool, query: SourceQuery) -> bool:
    if is_remote and query.allow_remote:
        return True
    if not query.city or not location:
        return True  # curated company; don't drop on missing location
    loc = fold_accents(location).lower()
    if "remote" in loc:
        return True
    return any(token in loc for token in _city_tokens(query.city))


def keep_posting(raw: RawJob, query: SourceQuery) -> bool:
    return (
        role_is_wanted(raw.title, raw.description_text or "", query)
        and location_ok(raw.location, raw.is_remote, query)
        and is_recent(raw.posted_at, query.max_age_days)
    )


class AtsSource(JobSource):
    """Base for connectors that fan out over curated companies via a public ATS API."""

    #: which ``CompanyRef.ats_type`` this connector handles
    ats_type: ClassVar[str]

    def __init__(self, settings: Settings, http: HttpClient, companies: list[CompanyRef]) -> None:
        super().__init__(settings, http)
        self.companies = [c for c in companies if c.ats_type == self.ats_type and c.ats_slug]

    def is_configured(self) -> bool:
        return bool(self.companies)

    def _keep(self, raw: RawJob, query: SourceQuery) -> bool:
        return keep_posting(raw, query)
