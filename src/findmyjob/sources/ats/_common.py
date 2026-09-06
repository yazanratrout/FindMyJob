"""Shared base + filters for connectors that iterate over curated companies."""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from typing import ClassVar

from findmyjob.config import Settings
from findmyjob.logging import get_logger
from findmyjob.normalize import city_tokens, fold_accents
from findmyjob.services.http import HttpClient
from findmyjob.sources._parsing import is_recent, matches_any_keyword
from findmyjob.sources.base import CompanyRef, JobSource, RawJob, SourceQuery

log = get_logger("source.ats")


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
    return any(token in loc for token in city_tokens(query.city))


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

    async def _collect(
        self,
        query: SourceQuery,
        fetch_company: Callable[[CompanyRef], Awaitable[list[RawJob]]],
    ) -> list[RawJob]:
        """Run ``fetch_company`` for each curated company, one bad slug at a time.

        A dead / stale slug (404, a redirect to the vendor's marketing site, a
        429) is logged and skipped - it never fails the connector for the other
        companies.
        """
        jobs: list[RawJob] = []
        for company in self.companies:
            if len(jobs) >= query.limit_per_source:
                break
            try:
                jobs.extend(await fetch_company(company))
            except Exception as exc:  # contain per-company failure
                log.warning(
                    "ats.company_failed",
                    source=self.key,
                    slug=company.ats_slug,
                    error=str(exc),
                )
        return jobs[: query.limit_per_source]
