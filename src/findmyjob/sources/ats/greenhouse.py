"""Greenhouse public job-board API."""

from __future__ import annotations

import html
from typing import Any, ClassVar

from findmyjob.sources._parsing import html_to_text, parse_datetime
from findmyjob.sources.ats._common import AtsSource
from findmyjob.sources.base import CompanyRef, RawJob, SourceQuery

_URL = "https://boards-api.greenhouse.io/v1/boards/{slug}/jobs"


class GreenhouseSource(AtsSource):
    key: ClassVar[str] = "greenhouse"
    display_name: ClassVar[str] = "Greenhouse"
    ats_type: ClassVar[str] = "greenhouse"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        async def _one(company: CompanyRef) -> list[RawJob]:
            payload = await self._http.get_json(
                _URL.format(slug=company.ats_slug), params={"content": "true"}
            )
            out = [self._to_raw_job(item, company) for item in payload.get("jobs", [])]
            return [r for r in out if r is not None and self._keep(r, query)]

        return await self._collect(query, _one)

    def _to_raw_job(self, item: dict[str, Any], company: CompanyRef) -> RawJob | None:
        job_id, title = item.get("id"), item.get("title")
        if not job_id or not title:
            return None
        content_html = html.unescape(item.get("content") or "")
        return RawJob(
            source_key=self.key,
            source_job_id=f"{company.ats_slug}:{job_id}",
            url=item.get("absolute_url", ""),
            title=title,
            company_name=company.name,
            location=(item.get("location") or {}).get("name"),
            posted_at=parse_datetime(item.get("updated_at")),
            description_text=html_to_text(content_html) or None,
            description_html=content_html or None,
            extra={"ats": "greenhouse"},
        )
