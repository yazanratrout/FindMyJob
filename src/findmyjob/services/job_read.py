"""Read models for the dashboard / job-detail views."""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import func
from sqlmodel import Session, col, select

from findmyjob.llm.analyzer import ANALYZER_VERSION
from findmyjob.models.config import Company
from findmyjob.models.enums import Decision, JobLifecycle, RunStatus
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.models.run import Run


@dataclass(slots=True)
class JobRow:
    job: Job
    score: JobScore
    company: Company | None
    analysis: JobAnalysis | None
    is_new: bool


def _latest_completed_run_id(session: Session) -> int | None:
    run = session.exec(
        select(Run).where(col(Run.status) == RunStatus.COMPLETED).order_by(col(Run.id).desc())
    ).first()
    return run.id if run else None


def _current_analysis(session: Session, job_id: int) -> JobAnalysis | None:
    return session.exec(
        select(JobAnalysis).where(
            col(JobAnalysis.job_id) == job_id,
            col(JobAnalysis.analyzer_version) == ANALYZER_VERSION,
        )
    ).first()


def list_jobs(
    session: Session,
    *,
    buckets: list[Decision] | None = None,
    source: str | None = None,
    search: str | None = None,
    limit: int = 200,
) -> list[JobRow]:
    """Canonical, active jobs with their most recent `JobScore`, ranked by score."""
    latest_score_ids = (
        select(func.max(col(JobScore.id))).group_by(col(JobScore.job_id)).scalar_subquery()
    )
    stmt = (
        select(JobScore, Job)
        .join(Job, col(JobScore.job_id) == col(Job.id))
        .where(
            col(JobScore.id).in_(latest_score_ids),
            col(Job.canonical_job_id).is_(None),
            col(Job.lifecycle) == JobLifecycle.ACTIVE,
        )
    )
    if buckets:
        stmt = stmt.where(col(JobScore.decision).in_(buckets))
    if source:
        stmt = stmt.where(col(Job.source_key) == source)
    if search:
        like = f"%{search.lower()}%"
        stmt = stmt.where(
            func.lower(col(Job.title)).like(like) | func.lower(col(Job.company_name_raw)).like(like)
        )
    stmt = stmt.order_by(col(JobScore.final_score).desc(), col(Job.id).desc()).limit(limit)

    latest_run_id = _latest_completed_run_id(session)
    rows: list[JobRow] = []
    companies: dict[int, Company] = {}
    for score, job in session.exec(stmt).all():
        assert job.id is not None
        company = None
        if job.company_id is not None:
            company = companies.get(job.company_id) or session.get(Company, job.company_id)
            if company is not None:
                companies[job.company_id] = company
        rows.append(
            JobRow(
                job=job,
                score=score,
                company=company,
                analysis=_current_analysis(session, job.id),
                is_new=job.first_seen_run_id == latest_run_id,
            )
        )
    return rows


def get_job_row(session: Session, job_id: int) -> JobRow | None:
    job = session.get(Job, job_id)
    if job is None:
        return None
    score = session.exec(
        select(JobScore).where(col(JobScore.job_id) == job_id).order_by(col(JobScore.id).desc())
    ).first()
    if score is None:
        return None
    company = session.get(Company, job.company_id) if job.company_id else None
    return JobRow(
        job=job,
        score=score,
        company=company,
        analysis=_current_analysis(session, job_id),
        is_new=job.first_seen_run_id == _latest_completed_run_id(session),
    )


def bucket_counts(session: Session) -> dict[str, int]:
    latest_score_ids = (
        select(func.max(col(JobScore.id))).group_by(col(JobScore.job_id)).scalar_subquery()
    )
    rows = session.exec(
        select(JobScore.decision, func.count())
        .join(Job, col(JobScore.job_id) == col(Job.id))
        .where(
            col(JobScore.id).in_(latest_score_ids),
            col(Job.canonical_job_id).is_(None),
            col(Job.lifecycle) == JobLifecycle.ACTIVE,
        )
        .group_by(col(JobScore.decision))
    ).all()
    counts = {d.value: 0 for d in Decision}
    for decision, count in rows:
        counts[decision.value if hasattr(decision, "value") else str(decision)] = count
    return counts
