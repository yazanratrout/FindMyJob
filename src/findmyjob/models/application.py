"""Application tracking and generated cover letters."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin
from findmyjob.models.enums import ApplicationStatus


class Application(TimestampMixin, table=True):
    __tablename__ = "application"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True, unique=True)
    status: ApplicationStatus = ApplicationStatus.INTERESTED
    applied_at: datetime | None = None
    follow_up_at: datetime | None = None
    outcome_note: str = ""
    documents_used: list[str] = Field(default_factory=list, sa_column=Column(JSON))


class CoverLetter(TimestampMixin, table=True):
    __tablename__ = "cover_letter"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True)
    application_id: int | None = Field(default=None, foreign_key="application.id")
    version: int = 1
    language: str = "de"
    tone: str = "formal"

    content: dict = Field(default_factory=dict, sa_column=Column(JSON))
    claims_used: list[dict] = Field(default_factory=list, sa_column=Column(JSON))
    docx_path: str | None = None
    user_edited: bool = False
