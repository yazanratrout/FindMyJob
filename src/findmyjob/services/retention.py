"""Prune old, archived, unreferenced jobs to keep the database small."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime, timedelta

from sqlmodel import Session, col, delete, select

from findmyjob.logging import get_logger
from findmyjob.models.application import Application, CoverLetter
from findmyjob.models.base import utcnow
from findmyjob.models.enums import Decision, JobLifecycle
from findmyjob.models.job import Job, JobAnalysis, JobEmbedding, JobScore
from findmyjob.services.settings import get_app_settings

log = get_logger("retention")


@dataclass(slots=True)
class PruneReport:
    considered: int
    pruned: int
    kept_referenced: int


def _referenced_job_ids(session: Session) -> set[int]:
    ids: set[int] = set()
    ids.update(session.exec(select(col(Application.job_id))).all())
    ids.update(session.exec(select(col(CoverLetter.job_id))).all())
    return ids


def prunable_job_ids(session: Session, cutoff: datetime) -> list[int]:
    referenced = _referenced_job_ids(session)
    has_duplicates = set(
        session.exec(
            select(col(Job.canonical_job_id)).where(col(Job.canonical_job_id).is_not(None))
        ).all()
    )

    candidates = session.exec(
        select(Job).where(
            col(Job.canonical_job_id).is_(None),
            col(Job.created_at) < cutoff,
        )
    ).all()

    prunable: list[int] = []
    for job in candidates:
        if job.id is None or job.id in referenced or job.id in has_duplicates:
            continue
        latest = session.exec(
            select(JobScore).where(col(JobScore.job_id) == job.id).order_by(col(JobScore.id).desc())
        ).first()
        if (
            job.lifecycle == JobLifecycle.DEAD
            or latest is None
            or latest.decision == Decision.ARCHIVED
        ):
            prunable.append(job.id)
    return prunable


def prune(session: Session, *, now: datetime | None = None) -> PruneReport:
    now = now or utcnow()
    retention_days = get_app_settings(session).retention_days
    cutoff = now - timedelta(days=retention_days)

    ids = prunable_job_ids(session, cutoff)
    if ids:
        session.exec(delete(JobEmbedding).where(col(JobEmbedding.job_id).in_(ids)))
        session.exec(delete(JobAnalysis).where(col(JobAnalysis.job_id).in_(ids)))
        session.exec(delete(JobScore).where(col(JobScore.job_id).in_(ids)))
        session.exec(delete(Job).where(col(Job.id).in_(ids)))
        session.flush()

    total_old = session.exec(select(Job).where(col(Job.created_at) < cutoff)).all()
    report = PruneReport(
        considered=len(total_old) + len(ids),
        pruned=len(ids),
        kept_referenced=len(_referenced_job_ids(session)),
    )
    log.info("retention.pruned", pruned=report.pruned, cutoff=str(cutoff))
    return report
