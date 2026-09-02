"""Working-day ledger for the (optional) non-EU eligibility module."""

from __future__ import annotations

from datetime import date

from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class EligibilityEntry(TimestampMixin, table=True):
    __tablename__ = "eligibility_entry"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)
    period_start: date
    period_end: date
    day_type: str = "full"  # full | half
    day_count: float = 0.0
    job_id: int | None = Field(default=None, foreign_key="job.id")
    note: str = ""
