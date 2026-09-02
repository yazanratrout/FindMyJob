"""Pipeline run bookkeeping: the orchestrator run, per-pipeline results, LLM calls."""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin, utcnow
from findmyjob.models.enums import (
    LlmPurpose,
    PipelineStatus,
    RunStatus,
    RunTrigger,
)


class Run(TimestampMixin, table=True):
    """One end-to-end execution of the orchestrator."""

    __tablename__ = "run"

    id: int | None = Field(default=None, primary_key=True)
    trigger: RunTrigger
    status: RunStatus = RunStatus.RUNNING
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None

    stats: dict = Field(default_factory=dict, sa_column=Column(JSON))
    errors: list = Field(default_factory=list, sa_column=Column(JSON))

    input_tokens: int = 0
    output_tokens: int = 0
    cost_eur: float = 0.0
    budget_exhausted: bool = False


class PipelineRun(TimestampMixin, table=True):
    """Result of a single pipeline within a :class:`Run`."""

    __tablename__ = "pipeline_run"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int = Field(foreign_key="run.id", index=True)
    name: str
    order: int
    status: PipelineStatus
    started_at: datetime = Field(default_factory=utcnow)
    finished_at: datetime | None = None
    duration_s: float = 0.0
    stats: dict = Field(default_factory=dict, sa_column=Column(JSON))
    errors: list = Field(default_factory=list, sa_column=Column(JSON))


class LlmCall(TimestampMixin, table=True):
    __tablename__ = "llm_call"

    id: int | None = Field(default=None, primary_key=True)
    run_id: int | None = Field(default=None, foreign_key="run.id", index=True)
    purpose: LlmPurpose
    model: str
    input_tokens: int = 0
    output_tokens: int = 0
    cost_eur: float = 0.0
    cache_hit: bool = False
    ok: bool = True
    error: str | None = None
