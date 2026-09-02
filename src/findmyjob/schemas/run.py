from __future__ import annotations

from datetime import datetime
from typing import Any

from pydantic import BaseModel

from findmyjob.models.enums import PipelineStatus, RunStatus, RunTrigger
from findmyjob.models.run import PipelineRun, Run


class RunSummary(BaseModel):
    id: int
    trigger: RunTrigger
    status: RunStatus
    started_at: datetime
    finished_at: datetime | None
    stats: dict[str, Any]
    error_count: int

    @classmethod
    def of(cls, run: Run) -> RunSummary:
        assert run.id is not None
        return cls(
            id=run.id,
            trigger=run.trigger,
            status=run.status,
            started_at=run.started_at,
            finished_at=run.finished_at,
            stats=run.stats,
            error_count=len(run.errors),
        )


class StageResult(BaseModel):
    name: str
    order: int
    status: PipelineStatus
    duration_s: float
    stats: dict[str, Any]
    error_count: int

    @classmethod
    def of(cls, pr: PipelineRun) -> StageResult:
        return cls(
            name=pr.name,
            order=pr.order,
            status=pr.status,
            duration_s=round(pr.duration_s, 3),
            stats=pr.stats,
            error_count=len(pr.errors),
        )


class LlmUsage(BaseModel):
    calls: int
    cache_hits: int
    input_tokens: int
    output_tokens: int
    cost_eur: float


class RunDetail(BaseModel):
    run: RunSummary
    stages: list[StageResult]
    llm: LlmUsage
    errors: list[dict[str, Any]]


class RunCreateRequest(BaseModel):
    fetch_only: bool = False
    no_llm: bool = False
