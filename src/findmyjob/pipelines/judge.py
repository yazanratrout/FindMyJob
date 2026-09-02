"""``judge`` — LLM holistic fit, blended into the final score.

Runs after ``score``. Only for jobs that passed every hard filter and scored
within reach of the "maybe" threshold — a clear reject is not worth a smart-model
call. Writes the holistic score + rationale onto the run's ``JobScore`` and
recomputes ``final_score`` / ``decision``.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from sqlmodel import col, select

from findmyjob.llm.client import LlmClient, LlmError
from findmyjob.llm.judge import judge_fit
from findmyjob.models.job import JobScore
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.analyze import current_analysis
from findmyjob.services.cost import budget_ok, mark_budget_exhausted
from findmyjob.services.profile import profile_summary_text
from findmyjob.services.scoring import bucket

_JUDGE_MARGIN = 10


class JudgePipeline(Pipeline):
    name: ClassVar[str] = "judge"

    def __init__(self, client_factory: Callable[[], LlmClient] | None = None) -> None:
        self._client_factory = client_factory or LlmClient

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        client = self._client_factory()
        settings = ctx.app_settings
        floor = settings.score_threshold_maybe - _JUDGE_MARGIN

        with ctx.session() as session:
            profile_summary = profile_summary_text(session)
            score_ids = list(
                session.exec(
                    select(JobScore.id).where(
                        col(JobScore.run_id) == ctx.run_id,
                        col(JobScore.hard_pass).is_(True),
                        col(JobScore.soft_score) >= floor,
                    )
                ).all()
            )

        ratio = settings.blend_soft_ratio
        for score_id in score_ids:
            with ctx.session() as session:
                score = session.get(JobScore, score_id)
                if score is None:
                    continue
                if not budget_ok(session):
                    mark_budget_exhausted(session, ctx.run_id)
                    res.bump("budget_exhausted")
                    break
                analysis = current_analysis(session, score.job_id)
                if analysis is None:
                    res.bump("no_analysis")
                    continue
                try:
                    judged, llm = judge_fit(
                        profile_summary=profile_summary,
                        analysis=analysis.raw_json,
                        soft_breakdown=score.soft_breakdown,
                        client=client,
                        run_id=ctx.run_id,
                    )
                except LlmError as exc:
                    res.add_error(f"job:{score.job_id}", exc)
                    continue

                score.llm_holistic = float(judged.holistic_fit)
                score.llm_rationale = judged.rationale
                score.missing_qualifications = judged.missing_qualifications
                score.strengths_to_highlight = judged.strengths_to_highlight
                score.final_score = round(
                    ratio * score.soft_score + (1 - ratio) * judged.holistic_fit, 1
                )
                score.decision = bucket(score.final_score, settings)
                session.add(score)
                res.bump("judged")
                res.bump(f"decision.{score.decision.value}")
                if llm.cache_hit:
                    res.bump("cache_hits")

        res.finalize_status()
        return res
