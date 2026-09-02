"""Extract schema.org ``JobPosting`` data from company career pages.

For curated companies with no known ATS. We only read pages the site's
``robots.txt`` allows, identify ourselves, and rate-limit. Coverage is
best-effort — many index pages carry no per-job structured data.
"""

from __future__ import annotations

import json
from typing import Any, ClassVar

from selectolax.parser import HTMLParser

from findmyjob.config import Settings
from findmyjob.logging import get_logger
from findmyjob.services.http import HttpClient
from findmyjob.sources._parsing import html_to_text, parse_datetime
from findmyjob.sources.ats._common import keep_posting
from findmyjob.sources.base import CompanyRef, JobSource, RawJob, SourceQuery
from findmyjob.sources.robots import RobotsCache

log = get_logger("source.jsonld")


def _collect_job_postings(data: Any) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for node in data if isinstance(data, list) else [data]:
        if not isinstance(node, dict):
            continue
        if "@graph" in node:
            out.extend(_collect_job_postings(node["@graph"]))
        types = node.get("@type")
        type_list = types if isinstance(types, list) else [types]
        if "JobPosting" in type_list:
            out.append(node)
    return out


def extract_job_postings(html_text: str) -> list[dict[str, Any]]:
    postings: list[dict[str, Any]] = []
    for script in HTMLParser(html_text).css('script[type="application/ld+json"]'):
        raw = script.text() or ""
        try:
            postings.extend(_collect_job_postings(json.loads(raw)))
        except (json.JSONDecodeError, ValueError):
            continue
    return postings


class JsonLdSource(JobSource):
    key: ClassVar[str] = "jsonld"
    display_name: ClassVar[str] = "Career-page JobPosting data"

    def __init__(self, settings: Settings, http: HttpClient, companies: list[CompanyRef]) -> None:
        super().__init__(settings, http)
        self.companies = [c for c in companies if c.ats_type == "none" and c.careers_url]
        self._robots = RobotsCache(http)

    def is_configured(self) -> bool:
        return bool(self.companies)

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        for company in self.companies:
            url = company.careers_url or ""
            if not await self._robots.allowed(url):
                log.info("jsonld.robots_blocked", company=company.name, url=url)
                continue
            try:
                html_text = await self._http.get_text(url)
            except Exception as exc:  # page moved / down — skip this company
                log.info("jsonld.fetch_failed", company=company.name, error=str(exc))
                continue
            for posting in extract_job_postings(html_text):
                raw = self._to_raw_job(posting, company, url)
                if raw is not None and keep_posting(raw, query):
                    jobs.append(raw)
        return jobs[: query.limit_per_source]

    def _to_raw_job(
        self, posting: dict[str, Any], company: CompanyRef, page_url: str
    ) -> RawJob | None:
        title = posting.get("title")
        if not title:
            return None
        url = posting.get("url") or posting.get("@id") or page_url
        identifier = posting.get("identifier")
        if isinstance(identifier, dict):
            identifier = identifier.get("value")
        job_id = str(identifier or url)

        org = posting.get("hiringOrganization")
        org_name = org.get("name") if isinstance(org, dict) else None

        location = None
        job_location = posting.get("jobLocation")
        if isinstance(job_location, list) and job_location:
            job_location = job_location[0]
        if isinstance(job_location, dict):
            address = job_location.get("address", {})
            if isinstance(address, dict):
                location = address.get("addressLocality") or address.get("addressRegion")

        return RawJob(
            source_key=self.key,
            source_job_id=job_id,
            url=str(url),
            title=str(title),
            company_name=org_name or company.name,
            location=location,
            is_remote="TELECOMMUTE" in str(posting.get("jobLocationType", "")).upper(),
            posted_at=parse_datetime(posting.get("datePosted")),
            description_text=html_to_text(posting.get("description")) or None,
            description_html=posting.get("description"),
            extra={"ats": "jsonld", "employmentType": posting.get("employmentType")},
        )
