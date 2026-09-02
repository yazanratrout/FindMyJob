"""Thumbs-up / thumbs-down feedback on scored jobs.

One row per job (upsert). Consumed by :mod:`findmyjob.services.calibration` to
correlate score components with what the user actually liked.
"""

from __future__ import annotations

from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.feedback import JobFeedback
from findmyjob.models.job import Job

log = get_logger("feedback")

VERDICTS: frozenset[str] = frozenset({"up", "down"})


class FeedbackError(ValueError):
    """Invalid feedback request."""


def get_feedback(session: Session, job_id: int) -> JobFeedback | None:
    return session.exec(select(JobFeedback).where(col(JobFeedback.job_id) == job_id)).first()


def set_feedback(session: Session, job_id: int, verdict: str, note: str = "") -> JobFeedback:
    if verdict not in VERDICTS:
        raise FeedbackError(f"verdict must be one of {sorted(VERDICTS)}")
    if session.get(Job, job_id) is None:
        raise FeedbackError("job not found")

    row = get_feedback(session, job_id)
    if row is None:
        row = JobFeedback(job_id=job_id, verdict=verdict, note=note or "")
        session.add(row)
    else:
        row.verdict = verdict
        row.note = note or ""
        session.add(row)
    session.flush()
    log.info("feedback.set", job_id=job_id, verdict=verdict)
    return row


def clear_feedback(session: Session, job_id: int) -> bool:
    row = get_feedback(session, job_id)
    if row is None:
        return False
    session.delete(row)
    session.flush()
    log.info("feedback.cleared", job_id=job_id)
    return True
