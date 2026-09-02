"""The Muse public API.

Optional key (``THEMUSE_API_KEY``) raises the rate limit but is not required.
The public API filters by location and level only, so keyword and recency
filtering happen on the client.
"""

from __future__ import annotations

from typing import Any, ClassVar

from findmyjob.sources._parsing import (
    html_to_text,
    is_recent,
    matches_any_keyword,
    parse_datetime,
)
from findmyjob.sources.base import JobSource, RawJob, SourceQuery

_URL = "https://www.themuse.com/api/public/jobs"


class TheMuseSource(JobSource):
    key: ClassVar[str] = "themuse"
    display_name: ClassVar[str] = "The Muse"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        params: dict[str, Any] = {"page": 0}
        if self._settings.themuse_api_key:
            params["api_key"] = self._settings.themuse_api_key
        if query.city:
            params["location"] = f"{query.city}, Germany"

        jobs: list[RawJob] = []
        page = 0
        page_cap = 4
        while len(jobs) < query.limit_per_source and page < page_cap:
            params["page"] = page
            payload = await self._http.get_json(_URL, params=params)
            results = payload.get("results", [])
            page_cap = min(int(payload.get("page_count", page_cap)), 4)
            if not results:
                break
            for item in results:
                raw = self._to_raw_job(item, query)
                if raw is not None:
                    jobs.append(raw)
            page += 1

        return jobs[: query.limit_per_source]

    def _to_raw_job(self, item: dict[str, Any], query: SourceQuery) -> RawJob | None:
        job_id, title = item.get("id"), item.get("name")
        if not job_id or not title:
            return None
        text = html_to_text(item.get("contents"))
        if not matches_any_keyword(f"{title}\n{text[:2000]}", query.keywords):
            return None
        posted = parse_datetime(item.get("publication_date"))
        if not is_recent(posted, query.max_age_days):
            return None
        locations = [loc.get("name", "") for loc in item.get("locations", [])]
        is_remote = any("remote" in loc.lower() for loc in locations)
        return RawJob(
            source_key=self.key,
            source_job_id=str(job_id),
            url=(item.get("refs") or {}).get("landing_page", ""),
            title=title,
            company_name=(item.get("company") or {}).get("name", "") or "",
            location=", ".join(loc for loc in locations if loc) or None,
            is_remote=is_remote,
            posted_at=posted,
            description_text=text or None,
            description_html=item.get("contents"),
            extra={"levels": [lvl.get("name") for lvl in item.get("levels", [])]},
        )
