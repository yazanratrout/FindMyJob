"""Read helpers + background trigger for pipeline runs."""

from __future__ import annotations

import asyncio
from typing import Any

from sqlmodel import Session, col, select

from findmyjob.db import session_scope
from findmyjob.logging import get_logger
from findmyjob.models.enums import RunStatus, RunTrigger
from findmyjob.models.run import LlmCall, PipelineRun, Run
from findmyjob.pipelines.registry import build_default_orchestrator

log = get_logger("runs")

# Keep a reference so background tasks aren't garbage-collected mid-run.
_running: set[asyncio.Task[int]] = set()


def list_runs(session: Session, limit: int = 20) -> list[Run]:
    return list(session.exec(select(Run).order_by(col(Run.id).desc()).limit(limit)).all())


def run_detail(session: Session, run_id: int) -> dict[str, Any] | None:
    run = session.get(Run, run_id)
    if run is None:
        return None
    stages = session.exec(
        select(PipelineRun)
        .where(col(PipelineRun.run_id) == run_id)
        .order_by(col(PipelineRun.order))
    ).all()
    calls = session.exec(select(LlmCall).where(col(LlmCall.run_id) == run_id)).all()
    return {
        "run": run,
        "stages": stages,
        "llm": {
            "calls": len(calls),
            "cache_hits": sum(1 for c in calls if c.cache_hit),
            "input_tokens": sum(c.input_tokens for c in calls),
            "output_tokens": sum(c.output_tokens for c in calls),
            "cost_eur": round(sum(c.cost_eur for c in calls), 4),
        },
    }


def start_background_run(
    *, trigger: RunTrigger = RunTrigger.MANUAL, fetch_only: bool = False, no_llm: bool = False
) -> int:
    """Open a run row now, execute the pipeline in the background, return the id."""
    orchestrator = build_default_orchestrator(fetch_only=fetch_only, no_llm=no_llm)
    run_id = orchestrator.open_run(trigger)

    async def _execute() -> int:
        try:
            return await orchestrator.execute(trigger=trigger, run_id=run_id)
        except Exception:  # pragma: no cover - defensive; orchestrator is crash-safe
            log.exception("runs.background_failed", run_id=run_id)
            with session_scope() as session:
                run = session.get(Run, run_id)
                if run is not None:
                    run.status = RunStatus.FAILED
                    session.add(run)
            return run_id

    task = asyncio.create_task(_execute())
    _running.add(task)
    task.add_done_callback(_running.discard)
    return run_id
