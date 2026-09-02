"""``prefilter`` — cheap, deterministic hard filters run before any LLM call.

Checks that need only the `Job` row + settings: recency, blocked keywords,
location. A failure writes a `JobScore` with ``hard_pass=False`` + reasons and
``decision=archived``; ``analyze`` then skips those jobs. Analysis-dependent
hard checks (hours, language, contract) happen later in ``score``.
"""

from __future__ import annotations

from typing import ClassVar

from sqlmodel import col, select

from findmyjob.models.enums import Decision, JobLifecycle
from findmyjob.models.job import Job
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.jobscore import upsert_run_score
from findmyjob.services.scoring import cheap_hard_checks

_MAX_PER_RUN = 5000


class PrefilterPipeline(Pipeline):
    name: ClassVar[str] = "prefilter"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        with ctx.session() as session:
            jobs = session.exec(
                select(Job)
                .where(
                    col(Job.canonical_job_id).is_(None),
                    col(Job.lifecycle) == JobLifecycle.ACTIVE,
                )
                .order_by(col(Job.id))
                .limit(_MAX_PER_RUN)
            ).all()

            for job in jobs:
                assert job.id is not None
                try:
                    hard = cheap_hard_checks(job, ctx.app_settings)
                    score = upsert_run_score(session, job.id, ctx.run_id)
                    score.hard_pass = hard.passed
                    score.hard_failures = hard.failures
                    if not hard.passed:
                        score.decision = Decision.ARCHIVED
                        res.bump("hard_failed")
                    else:
                        res.bump("passed")
                    session.add(score)
                except Exception as exc:
                    res.add_error(f"job:{job.id}", exc)

        res.finalize_status()
        return res
