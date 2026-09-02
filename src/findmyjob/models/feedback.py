"""User thumbs-up/down on a recommendation, used for score calibration."""

from __future__ import annotations

from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class JobFeedback(TimestampMixin, table=True):
    __tablename__ = "job_feedback"

    id: int | None = Field(default=None, primary_key=True)
    job_id: int = Field(foreign_key="job.id", index=True, unique=True)
    verdict: str  # "up" | "down"
    note: str = ""
