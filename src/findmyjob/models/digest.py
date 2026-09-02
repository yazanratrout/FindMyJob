"""Per-run digest shown in the web UI (no external notifications)."""

from __future__ import annotations

from sqlalchemy import JSON, Column
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class Digest(TimestampMixin, table=True):
    __tablename__ = "digest"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    seen: bool = False

    # {new_jobs, recommended, maybe, archived, follow_ups_due, errors,
    #  budget_exhausted, run_status}
    summary: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # [{job_id, title, company, final_score, decision, is_new}]
    items: list = Field(default_factory=list, sa_column=Column(JSON))
    warnings: list = Field(default_factory=list, sa_column=Column(JSON))
