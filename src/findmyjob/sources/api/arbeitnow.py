"""Arbeitnow public job-board API.

Documented public JSON API, Germany-focused, no key. It is a full board with no
server-side query, so we page through it and filter by keyword / recency / city
on the client.
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

_URL = "https://www.arbeitnow.com/api/job-board-api"


class ArbeitnowSource(JobSource):
    key: ClassVar[str] = "arbeitnow"
    display_name: ClassVar[str] = "Arbeitnow"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        params: dict[str, Any] = {"page": 1}

        for _ in range(5):  # hard page cap
            if len(jobs) >= query.limit_per_source:
                break
            payload = await self._http.get_json(_URL, params=params)
            data = payload.get("data", [])
            if not data:
                break
            for item in data:
                raw = self._to_raw_job(item, query)
                if raw is not None:
                    jobs.append(raw)
            next_link = (payload.get("links") or {}).get("next")
            if not next_link:
                break
            params["page"] += 1

        return jobs[: query.limit_per_source]

    def _to_raw_job(self, item: dict[str, Any], query: SourceQuery) -> RawJob | None:
        slug, title = item.get("slug"), item.get("title")
        if not slug or not title:
            return None
        is_remote = bool(item.get("remote"))
        location = item.get("location")
        text = html_to_text(item.get("description"))

        haystack = f"{title}\n{' '.join(item.get('tags') or [])}\n{text[:2000]}"
        if not matches_any_keyword(haystack, query.keywords):
            return None

        posted = parse_datetime(item.get("created_at"))
        if not is_recent(posted, query.max_age_days):
            return None
        if query.city and not is_remote and location and query.city.lower() not in location.lower():
            return None

        return RawJob(
            source_key=self.key,
            source_job_id=str(slug),
            url=item.get("url", ""),
            title=title,
            company_name=item.get("company_name", "") or "",
            location=location,
            is_remote=is_remote,
            posted_at=posted,
            description_text=text or None,
            description_html=item.get("description"),
            extra={"tags": item.get("tags"), "job_types": item.get("job_types")},
        )
