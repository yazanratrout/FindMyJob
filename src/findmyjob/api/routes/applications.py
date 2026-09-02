"""Application tracker."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.schemas.application import (
    ApplicationCreate,
    ApplicationRead,
    ApplicationUpdate,
)
from findmyjob.services.applications import (
    ApplicationError,
    follow_ups_due,
    get_or_create,
    list_applications,
    update_application,
)

router = APIRouter(prefix="/applications", tags=["applications"])


@router.get("", response_model=list[ApplicationRead])
def get_applications(session: Session = Depends(get_session)) -> list[ApplicationRead]:
    return [ApplicationRead.of(a, j) for a, j in list_applications(session)]


@router.get("/follow-ups", response_model=list[ApplicationRead])
def get_follow_ups(session: Session = Depends(get_session)) -> list[ApplicationRead]:
    return [ApplicationRead.of(a, j) for a, j in follow_ups_due(session)]


@router.post("", response_model=ApplicationRead, status_code=201)
def create_application(
    body: ApplicationCreate, session: Session = Depends(get_session)
) -> ApplicationRead:
    try:
        app = get_or_create(session, body.job_id)
    except ApplicationError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    session.commit()
    session.refresh(app)
    from findmyjob.models.job import Job

    job = session.get(Job, app.job_id)
    assert job is not None
    return ApplicationRead.of(app, job)


@router.put("/{application_id}", response_model=ApplicationRead)
def edit_application(
    application_id: int,
    body: ApplicationUpdate,
    session: Session = Depends(get_session),
) -> ApplicationRead:
    try:
        app = update_application(
            session, application_id, body.model_dump(exclude_unset=True, mode="json")
        )
    except ApplicationError as exc:
        status = 404 if "not found" in str(exc) else 422
        raise HTTPException(status_code=status, detail=str(exc)) from exc
    session.commit()
    from findmyjob.models.job import Job

    job = session.get(Job, app.job_id)
    assert job is not None
    return ApplicationRead.of(app, job)
