from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from findmyjob.models.eligibility import EligibilityEntry


class EligibilityGauge(BaseModel):
    enabled: bool
    applies: bool
    year: int
    days_used: float
    limit_full_days: int
    remaining: float


class EligibilityEntryRead(BaseModel):
    id: int
    period_start: date
    period_end: date
    day_type: str
    day_count: float
    job_id: int | None
    note: str

    @classmethod
    def of(cls, row: EligibilityEntry) -> EligibilityEntryRead:
        assert row.id is not None
        return cls(
            id=row.id,
            period_start=row.period_start,
            period_end=row.period_end,
            day_type=row.day_type,
            day_count=row.day_count,
            job_id=row.job_id,
            note=row.note,
        )


class EligibilityEntryCreate(BaseModel):
    period_start: date
    period_end: date
    day_type: str = "full"
    note: str = ""
