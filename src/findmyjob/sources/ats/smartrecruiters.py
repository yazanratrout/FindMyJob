"""SmartRecruiters public posting API."""

from __future__ import annotations

from typing import Any, ClassVar

from findmyjob.sources._parsing import parse_datetime
from findmyjob.sources.ats._common import AtsSource
from findmyjob.sources.base import CompanyRef, RawJob, SourceQuery

_URL = "https://api.smartrecruiters.com/v1/companies/{slug}/postings"


class SmartRecruitersSource(AtsSource):
    key: ClassVar[str] = "smartrecruiters"
    display_name: ClassVar[str] = "SmartRecruiters"
    ats_type: ClassVar[str] = "smartrecruiters"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        async def _one(company: CompanyRef) -> list[RawJob]:
            found: list[RawJob] = []
            offset = 0
            for _ in range(4):
                payload = await self._http.get_json(
                    _URL.format(slug=company.ats_slug),
                    params={"limit": 100, "offset": offset},
                )
                content = payload.get("content", [])
                for item in content:
                    raw = self._to_raw_job(item, company)
                    if raw is not None and self._keep(raw, query):
                        found.append(raw)
                if len(content) < 100:
                    break
                offset += 100
            return found

        return await self._collect(query, _one)

    def _to_raw_job(self, item: dict[str, Any], company: CompanyRef) -> RawJob | None:
        job_id, title = item.get("id"), item.get("name")
        if not job_id or not title:
            return None
        location = item.get("location") or {}
        loc_str = ", ".join(
            p for p in (location.get("city"), location.get("region"), location.get("country")) if p
        )
        return RawJob(
            source_key=self.key,
            source_job_id=f"{company.ats_slug}:{job_id}",
            url=item.get("ref") or item.get("applyUrl") or "",
            title=title,
            company_name=company.name,
            location=loc_str or None,
            is_remote=bool(location.get("remote")),
            posted_at=parse_datetime(item.get("releasedDate")),
            extra={"ats": "smartrecruiters"},
        )
