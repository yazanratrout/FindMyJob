"""Bundesagentur für Arbeit — Jobsuche API.

Public search endpoint; authenticates with a fixed API-key header (documented at
https://jobsuche.api.bund.dev), so no user credentials are required. Largest
coverage for the German market, including Werkstudent roles.
"""

from __future__ import annotations

from typing import Any, ClassVar

from findmyjob.logging import get_logger
from findmyjob.sources._parsing import is_recent, parse_datetime
from findmyjob.sources.base import JobSource, RawJob, SourceQuery

log = get_logger("source.ba")

_SEARCH_URL = "https://rest.arbeitsagentur.de/jobboerse/jobsuche-service/pc/v4/jobs"
_API_KEY = "jobboerse-jobsuche"  # fixed public key, see api.bund.dev
_DETAIL_URL = "https://www.arbeitsagentur.de/jobsuche/jobdetail/{ref}"

# our job types -> BA "arbeitszeit" codes
_ARBEITSZEIT = {"werkstudent": "tz", "student_assistant": "tz", "minijob": "mj"}


class BundesagenturSource(JobSource):
    key: ClassVar[str] = "ba"
    display_name: ClassVar[str] = "Bundesagentur für Arbeit"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        keywords = query.keywords[:6] or ["Werkstudent"]
        arbeitszeit = sorted({_ARBEITSZEIT[jt] for jt in query.job_types if jt in _ARBEITSZEIT})
        seen: set[str] = set()
        jobs: list[RawJob] = []

        for keyword in keywords:
            if len(jobs) >= query.limit_per_source:
                break
            params: dict[str, Any] = {
                "was": keyword,
                "size": 25,
                "page": 1,
                "veroeffentlichtseit": min(query.max_age_days, 100),
            }
            if query.city:
                params["wo"] = query.city
                params["umkreis"] = query.radius_km
            if arbeitszeit:
                params["arbeitszeit"] = ";".join(arbeitszeit)

            payload = await self._http.get_json(
                _SEARCH_URL, params=params, headers={"X-API-Key": _API_KEY}
            )
            for item in payload.get("stellenangebote", []):
                raw = self._to_raw_job(item)
                if raw is None or raw.source_job_id in seen:
                    continue
                if not is_recent(raw.posted_at, query.max_age_days):
                    continue
                seen.add(raw.source_job_id)
                jobs.append(raw)

        return jobs[: query.limit_per_source]

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob | None:
        ref = item.get("refnr")
        title = item.get("titel") or item.get("beruf")
        if not ref or not title:
            return None
        ort = item.get("arbeitsort", {}) or {}
        location = ", ".join(
            part for part in (ort.get("ort"), ort.get("region"), ort.get("land")) if part
        )
        external = item.get("externeUrl")
        return RawJob(
            source_key=self.key,
            source_job_id=str(ref),
            url=external or _DETAIL_URL.format(ref=ref),
            apply_url=external,
            title=title,
            company_name=item.get("arbeitgeber", "") or "",
            location=location or None,
            posted_at=parse_datetime(item.get("aktuelleVeroeffentlichungsdatum")),
            extra={"beruf": item.get("beruf"), "arbeitszeit": item.get("arbeitszeitmodelle")},
        )
