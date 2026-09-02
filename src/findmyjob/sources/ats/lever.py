"""Lever public postings API."""

from __future__ import annotations

from typing import Any, ClassVar

from findmyjob.sources._parsing import html_to_text, parse_datetime
from findmyjob.sources.ats._common import AtsSource
from findmyjob.sources.base import CompanyRef, RawJob, SourceQuery

_URL = "https://api.lever.co/v0/postings/{slug}"


class LeverSource(AtsSource):
    key: ClassVar[str] = "lever"
    display_name: ClassVar[str] = "Lever"
    ats_type: ClassVar[str] = "lever"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        for company in self.companies:
            payload = await self._http.get_json(
                _URL.format(slug=company.ats_slug), params={"mode": "json"}
            )
            for item in payload if isinstance(payload, list) else []:
                raw = self._to_raw_job(item, company)
                if raw is not None and self._keep(raw, query):
                    jobs.append(raw)
        return jobs[: query.limit_per_source]

    def _to_raw_job(self, item: dict[str, Any], company: CompanyRef) -> RawJob | None:
        job_id, title = item.get("id"), item.get("text")
        if not job_id or not title:
            return None
        categories = item.get("categories") or {}
        return RawJob(
            source_key=self.key,
            source_job_id=f"{company.ats_slug}:{job_id}",
            url=item.get("hostedUrl", ""),
            apply_url=item.get("applyUrl"),
            title=title,
            company_name=company.name,
            location=categories.get("location"),
            posted_at=parse_datetime(item.get("createdAt")),
            description_text=item.get("descriptionPlain") or html_to_text(item.get("description")),
            description_html=item.get("description"),
            extra={
                "ats": "lever",
                "team": categories.get("team"),
                "commitment": categories.get("commitment"),
            },
        )
