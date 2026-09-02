"""Application status tracking."""

from __future__ import annotations

from datetime import UTC, datetime
from typing import Any

from sqlmodel import Session, col, select

from findmyjob.models.application import Application
from findmyjob.models.base import utcnow
from findmyjob.models.enums import ApplicationStatus
from findmyjob.models.job import Job


class ApplicationError(ValueError):
    """Invalid application request."""


_APPLIED_AT_STATUSES = {
    ApplicationStatus.APPLIED,
    ApplicationStatus.INTERVIEW,
    ApplicationStatus.OFFER,
}


def list_applications(session: Session) -> list[tuple[Application, Job]]:
    return list(
        session.exec(
            select(Application, Job)
            .join(Job, col(Application.job_id) == col(Job.id))
            .order_by(col(Application.updated_at).desc())
        ).all()
    )


def get_or_create(session: Session, job_id: int) -> Application:
    if session.get(Job, job_id) is None:
        raise ApplicationError("job not found")
    app = session.exec(select(Application).where(col(Application.job_id) == job_id)).first()
    if app is None:
        app = Application(job_id=job_id, status=ApplicationStatus.INTERESTED)
        session.add(app)
        session.flush()
    return app


def update_application(session: Session, application_id: int, patch: dict[str, Any]) -> Application:
    app = session.get(Application, application_id)
    if app is None:
        raise ApplicationError("application not found")

    if "status" in patch:
        try:
            new_status = ApplicationStatus(patch["status"])
        except ValueError as exc:
            raise ApplicationError(f"invalid status: {patch['status']}") from exc
        app.status = new_status
        if new_status in _APPLIED_AT_STATUSES and app.applied_at is None:
            app.applied_at = utcnow()

    for field in ("outcome_note",):
        if field in patch:
            setattr(app, field, patch[field] or "")
    if "documents_used" in patch:
        app.documents_used = list(patch["documents_used"] or [])
    for field in ("applied_at", "follow_up_at"):
        if field in patch:
            value = patch[field]
            setattr(app, field, datetime.fromisoformat(value) if value else None)

    session.add(app)
    session.flush()
    return app


def follow_ups_due(session: Session) -> list[tuple[Application, Job]]:
    now = datetime.now(UTC).replace(tzinfo=None)
    return list(
        session.exec(
            select(Application, Job)
            .join(Job, col(Application.job_id) == col(Job.id))
            .where(
                col(Application.follow_up_at).is_not(None),
                col(Application.follow_up_at) <= now,
                col(Application.status).in_(
                    [ApplicationStatus.APPLIED, ApplicationStatus.INTERVIEW]
                ),
            )
            .order_by(col(Application.follow_up_at))
        ).all()
    )


def application_for_job(session: Session, job_id: int) -> Application | None:
    return session.exec(select(Application).where(col(Application.job_id) == job_id)).first()
