"""``analyze`` — LLM structured extraction for jobs that survived the filters.

Runs after ``prefilter`` (CP10) so deterministic rejects never reach the model.
Only canonical, active jobs with real description text and no current-version
analysis are processed, capped per run. Results are cached by the LLM client's
content hash, so identical postings across sources cost one call.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from sqlmodel import col, select

from findmyjob.llm.analyzer import ANALYZER_VERSION
from findmyjob.llm.client import LlmClient, LlmError
from findmyjob.models.enums import JobLifecycle
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.analyze import analyze_job
from findmyjob.services.cost import budget_ok, mark_budget_exhausted

_MAX_PER_RUN = 120


class AnalyzePipeline(Pipeline):
    name: ClassVar[str] = "analyze"

    def __init__(self, client_factory: Callable[[], LlmClient] | None = None) -> None:
        self._client_factory = client_factory or LlmClient

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        client = self._client_factory()
        city = ctx.app_settings.target_city

        with ctx.session() as session:
            done = select(JobAnalysis.job_id).where(
                col(JobAnalysis.analyzer_version) == ANALYZER_VERSION
            )
            prefilter_rejected = select(JobScore.job_id).where(
                col(JobScore.run_id) == ctx.run_id,
                col(JobScore.hard_pass).is_(False),
            )
            job_ids = list(
                session.exec(
                    select(Job.id)
                    .where(
                        col(Job.canonical_job_id).is_(None),
                        col(Job.lifecycle) == JobLifecycle.ACTIVE,
                        col(Job.jd_text).is_not(None),
                        col(Job.id).not_in(done),
                        col(Job.id).not_in(prefilter_rejected),
                    )
                    .order_by(col(Job.id))
                    .limit(_MAX_PER_RUN)
                ).all()
            )

        for job_id in job_ids:
            with ctx.session() as session:
                job = session.get(Job, job_id)
                if job is None:
                    continue
                if not budget_ok(session):
                    mark_budget_exhausted(session, ctx.run_id)
                    res.bump("budget_exhausted")
                    break
                try:
                    analysis, llm = analyze_job(
                        session, job, city=city, client=client, run_id=ctx.run_id
                    )
                except LlmError as exc:
                    res.add_error(f"job:{job_id}", exc)
                    continue

                if analysis is None:
                    res.bump("skipped_thin_text")
                elif llm is None:
                    res.bump("already_analyzed")
                else:
                    res.bump("analyzed")
                    if llm.cache_hit:
                        res.bump("cache_hits")

        res.finalize_status()
        return res
