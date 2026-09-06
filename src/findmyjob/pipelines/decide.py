"""``decide`` — attach the documents checklist to every scored job this run.

Runs last. Deterministic, no LLM. Uses the posting analysis + which document
types the user has uploaded.
"""

from __future__ import annotations

from typing import ClassVar

from sqlmodel import col, select

from findmyjob.models.job import JobScore
from findmyjob.models.profile import Document
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.analyze import current_analysis
from findmyjob.services.documents_needed import compute_documents_needed


class DecidePipeline(Pipeline):
    name: ClassVar[str] = "decide"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        with ctx.session() as session:
            have_types = {d.type.value for d in session.exec(select(Document)).all()}
            # Only jobs still in the running need a documents checklist - a
            # hard-failed job is archived and will never be applied to.
            scores = session.exec(
                select(JobScore).where(
                    col(JobScore.run_id) == ctx.run_id,
                    col(JobScore.hard_pass).is_(True),
                )
            ).all()

            for score in scores:
                try:
                    analysis = current_analysis(session, score.job_id)
                    if analysis is None:
                        res.bump("no_analysis")
                        continue
                    score.documents_needed = compute_documents_needed(analysis, have_types)
                    session.add(score)
                    res.bump("decided")
                except Exception as exc:
                    res.add_error(f"job:{score.job_id}", exc)

        res.finalize_status()
        return res
