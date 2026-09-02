"""Personio public XML job feed."""

from __future__ import annotations

from typing import ClassVar
from xml.etree import ElementTree

from findmyjob.sources._parsing import html_to_text, parse_datetime
from findmyjob.sources.ats._common import AtsSource
from findmyjob.sources.base import CompanyRef, RawJob, SourceQuery

_URL = "https://{slug}.jobs.personio.de/xml"
_JOB_URL = "https://{slug}.jobs.personio.de/job/{job_id}"


class PersonioSource(AtsSource):
    key: ClassVar[str] = "personio"
    display_name: ClassVar[str] = "Personio"
    ats_type: ClassVar[str] = "personio"

    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        jobs: list[RawJob] = []
        for company in self.companies:
            xml = await self._http.get_text(_URL.format(slug=company.ats_slug))
            try:
                root = ElementTree.fromstring(xml)
            except ElementTree.ParseError:
                continue
            for position in root.iter("position"):
                raw = self._to_raw_job(position, company)
                if raw is not None and self._keep(raw, query):
                    jobs.append(raw)
        return jobs[: query.limit_per_source]

    def _to_raw_job(self, position: ElementTree.Element, company: CompanyRef) -> RawJob | None:
        job_id = position.findtext("id")
        title = position.findtext("name")
        if not job_id or not title:
            return None
        descriptions = "\n".join(
            (d.findtext("value") or "") for d in position.iter("jobDescription")
        )
        return RawJob(
            source_key=self.key,
            source_job_id=f"{company.ats_slug}:{job_id}",
            url=_JOB_URL.format(slug=company.ats_slug, job_id=job_id),
            title=title,
            company_name=company.name,
            location=position.findtext("office"),
            posted_at=parse_datetime(position.findtext("createdAt")),
            description_text=html_to_text(descriptions) or None,
            description_html=descriptions or None,
            extra={
                "ats": "personio",
                "employmentType": position.findtext("employmentType"),
                "category": position.findtext("recruitingCategory"),
            },
        )
