from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel

from findmyjob.models.application import Application
from findmyjob.models.enums import ApplicationStatus
from findmyjob.models.job import Job


class ApplicationRead(BaseModel):
    id: int
    job_id: int
    job_title: str
    company: str
    job_url: str
    apply_url: str | None
    status: ApplicationStatus
    applied_at: datetime | None
    follow_up_at: datetime | None
    outcome_note: str
    documents_used: list[str]
    updated_at: datetime

    @classmethod
    def of(cls, app: Application, job: Job) -> ApplicationRead:
        assert app.id is not None
        return cls(
            id=app.id,
            job_id=app.job_id,
            job_title=job.title,
            company=job.company_name_raw or "unknown",
            job_url=job.url,
            apply_url=job.apply_url,
            status=app.status,
            applied_at=app.applied_at,
            follow_up_at=app.follow_up_at,
            outcome_note=app.outcome_note,
            documents_used=app.documents_used,
            updated_at=app.updated_at,
        )


class ApplicationUpdate(BaseModel):
    status: ApplicationStatus | None = None
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    outcome_note: str | None = None
    documents_used: list[str] | None = None


class ApplicationCreate(BaseModel):
    job_id: int
