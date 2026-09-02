"""Pipeline run: list, detail, trigger, and a polling progress stream."""

from __future__ import annotations

import asyncio
from collections.abc import AsyncIterator

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import StreamingResponse
from sqlmodel import Session

from findmyjob.db import get_session, session_scope
from findmyjob.models.enums import RunStatus, RunTrigger
from findmyjob.schemas.run import (
    LlmUsage,
    RunCreateRequest,
    RunDetail,
    RunSummary,
    StageResult,
)
from findmyjob.services.runs import list_runs, run_detail, start_background_run

router = APIRouter(prefix="/runs", tags=["runs"])


def _detail(session: Session, run_id: int) -> RunDetail:
    data = run_detail(session, run_id)
    if data is None:
        raise HTTPException(status_code=404, detail="run not found")
    return RunDetail(
        run=RunSummary.of(data["run"]),
        stages=[StageResult.of(s) for s in data["stages"]],
        llm=LlmUsage(**data["llm"]),
        errors=data["run"].errors,
    )


@router.get("", response_model=list[RunSummary])
def get_runs(limit: int = 20, session: Session = Depends(get_session)) -> list[RunSummary]:
    return [RunSummary.of(r) for r in list_runs(session, limit=limit)]


@router.get("/{run_id}", response_model=RunDetail)
def get_run(run_id: int, session: Session = Depends(get_session)) -> RunDetail:
    return _detail(session, run_id)


@router.post("", response_model=RunDetail, status_code=202)
async def create_run(body: RunCreateRequest, session: Session = Depends(get_session)) -> RunDetail:
    run_id = start_background_run(
        trigger=RunTrigger.MANUAL, fetch_only=body.fetch_only, no_llm=body.no_llm
    )
    return _detail(session, run_id)


@router.get("/{run_id}/events")
async def run_events(run_id: int) -> StreamingResponse:
    """Server-sent events: emit the run detail every second until it finishes."""

    async def _stream() -> AsyncIterator[str]:
        for _ in range(3600):  # ~1h hard cap
            with session_scope() as session:
                data = run_detail(session, run_id)
                if data is None:
                    yield 'event: error\ndata: {"detail": "run not found"}\n\n'
                    return
                payload = RunDetail(
                    run=RunSummary.of(data["run"]),
                    stages=[StageResult.of(s) for s in data["stages"]],
                    llm=LlmUsage(**data["llm"]),
                    errors=data["run"].errors,
                )
                status = data["run"].status
            yield f"data: {payload.model_dump_json()}\n\n"
            if status in (RunStatus.COMPLETED, RunStatus.FAILED):
                return
            await asyncio.sleep(1.0)

    return StreamingResponse(_stream(), media_type="text/event-stream")
