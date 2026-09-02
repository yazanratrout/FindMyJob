"""``normalize`` — resolve companies and tidy job fields.

Runs after ``fetch``. For any job not yet linked to a company, match its raw
company name against the registry (creating an inactive "discovered" row when
new). Deterministic, no network, no LLM.
"""

from __future__ import annotations

from typing import ClassVar

from sqlmodel import col, select

from findmyjob.models.job import Job
from findmyjob.normalize import normalize_title
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.jobs import resolve_company

_MAX_PER_RUN = 2000


class NormalizePipeline(Pipeline):
    name: ClassVar[str] = "normalize"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        with ctx.session() as session:
            jobs = session.exec(
                select(Job)
                .where(col(Job.company_id).is_(None))
                .order_by(col(Job.id))
                .limit(_MAX_PER_RUN)
            ).all()

            for job in jobs:
                try:
                    company, created = resolve_company(session, job.company_name_raw)
                    if company is not None:
                        job.company_id = company.id
                        res.bump("linked")
                        if created:
                            res.bump("companies_discovered")
                    if not job.normalized_title:
                        job.normalized_title = normalize_title(job.title)
                    if (
                        not job.is_remote
                        and job.location_raw
                        and "remote" in job.location_raw.lower()
                    ):
                        job.is_remote = True
                    session.add(job)
                except Exception as exc:  # one bad row must not stop the stage
                    res.add_error(f"job:{job.id}", exc)

        res.finalize_status()
        return res
