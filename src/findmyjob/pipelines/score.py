"""``score`` — analysis-dependent hard checks + the weighted soft score.

Runs after ``analyze``. For every job that passed ``prefilter`` this run and now
has a current analysis: apply the hard checks that needed the analysis (hours /
language / contract), then compute the 0-100 soft score and a provisional
decision. ``judge`` + ``decide`` (CP11) refine ``final_score`` and ``decision``.
"""

from __future__ import annotations

from typing import ClassVar

from sqlmodel import col, select

from findmyjob.models.enums import Decision
from findmyjob.models.job import Job, JobScore
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.analyze import current_analysis
from findmyjob.services.eligibility import disqualifiers as eligibility_disqualifiers
from findmyjob.services.jobscore import (
    company_affinity,
    profile_language_levels,
    profile_skill_names,
)
from findmyjob.services.scoring import (
    analysis_hard_checks,
    bucket,
    compute_soft_score,
)


class ScorePipeline(Pipeline):
    name: ClassVar[str] = "score"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        settings = ctx.app_settings

        with ctx.session() as session:
            skills = profile_skill_names(session)
            languages = profile_language_levels(session)

            scores = session.exec(
                select(JobScore).where(
                    col(JobScore.run_id) == ctx.run_id,
                    col(JobScore.hard_pass).is_(True),
                )
            ).all()

            for score in scores:
                try:
                    job = session.get(Job, score.job_id)
                    analysis = current_analysis(session, score.job_id)
                    if job is None or analysis is None:
                        res.bump("no_analysis")
                        continue

                    hard = analysis_hard_checks(analysis, languages, settings)
                    elig = eligibility_disqualifiers(session, job, analysis)
                    if not hard.passed or elig:
                        score.hard_pass = False
                        score.hard_failures = [
                            *score.hard_failures,
                            *hard.failures,
                            *elig,
                        ]
                        score.decision = Decision.ARCHIVED
                        session.add(score)
                        res.bump("hard_failed_analysis")
                        if elig:
                            res.bump("hard_failed_eligibility")
                        continue

                    soft = compute_soft_score(
                        job=job,
                        analysis=analysis,
                        profile_skills=skills,
                        profile_languages=languages,
                        settings=settings,
                        company_affinity=company_affinity(session, job.company_id),
                    )
                    score.soft_score = soft.score
                    score.soft_breakdown = soft.breakdown
                    score.final_score = soft.score  # judge (CP11) will blend
                    score.decision = bucket(soft.score, settings)
                    session.add(score)
                    res.bump("scored")
                    res.bump(f"decision.{score.decision.value}")
                except Exception as exc:
                    res.add_error(f"job:{score.job_id}", exc)

        res.finalize_status()
        return res
