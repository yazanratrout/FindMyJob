"""Adzuna API (country = de).

Free API key (``ADZUNA_APP_ID`` / ``ADZUNA_APP_KEY``). Supports free-text OR
search, a ``where`` + ``distance`` radius, a recency filter and salary data.
"""

from __future__ import annotations

from typing import Any, ClassVar

from findmyjob.sources._parsing import parse_datetime
from findmyjob.sources.base import JobSource, RawJob, SourceQuery

_URL = "https://api.adzuna.com/v1/api/jobs/de/search/{page}"


class AdzunaSource(JobSource):
    key: ClassVar[str] = "adzuna"
    display_name: ClassVar[str] = "Adzuna"
    requires_secrets: ClassVar[tuple[str, ...]] = ("adzuna_app_id", "adzuna_app_key")

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        params: dict[str, Any] = {
            "app_id": self._settings.adzuna_app_id,
            "app_key": self._settings.adzuna_app_key,
            "results_per_page": 50,
            "what_or": " ".join(query.keywords) or "Werkstudent",
            "max_days_old": query.max_age_days,
            "content-type": "application/json",
        }
        if query.city:
            params["where"] = query.city
            params["distance"] = query.radius_km
        if "werkstudent" in query.job_types or "student_assistant" in query.job_types:
            params["contract_time"] = "part_time"

        jobs: list[RawJob] = []
        page = 1
        while len(jobs) < query.limit_per_source and page <= 5:
            payload = await self._http.get_json(_URL.format(page=page), params=params)
            results = payload.get("results", [])
            if not results:
                break
            for item in results:
                raw = self._to_raw_job(item)
                if raw is not None:
                    jobs.append(raw)
            page += 1

        return jobs[: query.limit_per_source]

    def _to_raw_job(self, item: dict[str, Any]) -> RawJob | None:
        job_id = item.get("id")
        title = item.get("title")
        if not job_id or not title:
            return None
        salary_min, salary_max = item.get("salary_min"), item.get("salary_max")
        salary_raw = (
            f"{salary_min:.0f}-{salary_max:.0f} EUR/year" if salary_min and salary_max else None
        )
        return RawJob(
            source_key=self.key,
            source_job_id=str(job_id),
            url=item.get("redirect_url", ""),
            title=title,
            company_name=(item.get("company") or {}).get("display_name", "") or "",
            location=(item.get("location") or {}).get("display_name"),
            posted_at=parse_datetime(item.get("created")),
            description_text=item.get("description"),
            salary_raw=salary_raw,
            extra={"category": (item.get("category") or {}).get("label")},
        )
