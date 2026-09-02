"""The orchestrator: runs the configured pipelines in order with error isolation.

Responsibilities, and only these:

* open a :class:`Run`, close it with the right status;
* execute each pipeline inside a crash barrier and time it;
* persist a :class:`PipelineRun` row per stage and roll stage stats up onto the run;
* stop early only when a *critical* pipeline fails.

It knows nothing about what any individual pipeline does.
"""

from __future__ import annotations

import time
from collections.abc import Sequence

from findmyjob.db import session_scope
from findmyjob.logging import get_logger
from findmyjob.models.base import utcnow
from findmyjob.models.enums import PipelineStatus, RunStatus, RunTrigger
from findmyjob.models.run import PipelineRun, Run
from findmyjob.pipelines.base import Pipeline, PipelineError, PipelineResult
from findmyjob.pipelines.context import PipelineContext, load_app_settings


class Orchestrator:
    def __init__(self, pipelines: Sequence[Pipeline]) -> None:
        self._pipelines: list[Pipeline] = list(pipelines)
        self._log = get_logger("orchestrator")
        self._validate()

    def _validate(self) -> None:
        seen: set[str] = set()
        for p in self._pipelines:
            if not getattr(p, "name", None):
                raise ValueError(f"Pipeline {p!r} has no name")
            if p.name in seen:
                raise ValueError(f"Duplicate pipeline name: {p.name}")
            seen.add(p.name)

    @property
    def pipeline_names(self) -> list[str]:
        return [p.name for p in self._pipelines]

    async def execute(self, *, trigger: RunTrigger = RunTrigger.MANUAL) -> int:
        """Run the whole sequence. Returns the :class:`Run` id."""
        run_id = self._open_run(trigger)
        log = self._log.bind(run_id=run_id, trigger=trigger.value)
        log.info("run.start", pipelines=self.pipeline_names)

        with session_scope() as session:
            app_settings = load_app_settings(session)

        ctx = PipelineContext(
            run_id=run_id,
            trigger=trigger,
            app_settings=app_settings,
            logger=self._log.bind(run_id=run_id),
        )

        final_status = RunStatus.COMPLETED
        for order, pipeline in enumerate(self._pipelines):
            result = await self._execute_pipeline(pipeline, ctx, order)
            self._persist_pipeline_run(run_id, order, result)
            self._roll_up(run_id, result)

            if result.status is PipelineStatus.FAILED and pipeline.critical:
                log.error("run.aborted", failed_pipeline=pipeline.name)
                final_status = RunStatus.FAILED
                break

        self._close_run(run_id, final_status)
        log.info("run.finished", status=final_status.value)
        return run_id

    # ---- internals ---------------------------------------------------

    async def _execute_pipeline(
        self, pipeline: Pipeline, ctx: PipelineContext, order: int
    ) -> PipelineResult:
        log = self._log.bind(run_id=ctx.run_id, pipeline=pipeline.name, order=order)
        try:
            if not pipeline.should_run(ctx):
                log.info("pipeline.skipped")
                return PipelineResult.skipped(pipeline.name)
        except Exception as exc:
            log.exception("pipeline.should_run_failed")
            return PipelineResult.skipped(pipeline.name, f"should_run raised: {exc}")

        log.info("pipeline.start")
        started = utcnow()
        t0 = time.monotonic()
        try:
            result = await pipeline.run(ctx)
        except Exception as exc:
            log.exception("pipeline.crashed")
            result = PipelineResult(
                name=pipeline.name,
                status=PipelineStatus.FAILED,
                errors=[
                    PipelineError(
                        scope=pipeline.name, message=str(exc), exc_type=type(exc).__name__
                    )
                ],
            )
        result.duration_s = time.monotonic() - t0
        result.started_at = started
        result.finished_at = utcnow()
        result.finalize_status()

        log.info(
            "pipeline.done",
            status=result.status.value,
            duration_s=round(result.duration_s, 3),
            error_count=len(result.errors),
            stats=dict(result.stats),
        )
        return result

    def _open_run(self, trigger: RunTrigger) -> int:
        with session_scope() as session:
            run = Run(trigger=trigger, status=RunStatus.RUNNING)
            session.add(run)
            session.flush()
            run_id = run.id
        assert run_id is not None
        return run_id

    def _persist_pipeline_run(self, run_id: int, order: int, result: PipelineResult) -> None:
        with session_scope() as session:
            session.add(
                PipelineRun(
                    run_id=run_id,
                    name=result.name,
                    order=order,
                    status=result.status,
                    started_at=result.started_at or utcnow(),
                    finished_at=result.finished_at,
                    duration_s=result.duration_s,
                    stats=dict(result.stats),
                    errors=[e.as_dict() for e in result.errors],
                )
            )

    def _roll_up(self, run_id: int, result: PipelineResult) -> None:
        with session_scope() as session:
            run = session.get(Run, run_id)
            if run is None:  # pragma: no cover - defensive
                return
            stats = dict(run.stats)
            for key, value in result.stats.items():
                stats[f"{result.name}.{key}"] = value
            run.stats = stats
            if result.errors:
                new_errors = [{"pipeline": result.name, **e.as_dict()} for e in result.errors]
                run.errors = [*run.errors, *new_errors]
            session.add(run)

    def _close_run(self, run_id: int, status: RunStatus) -> None:
        with session_scope() as session:
            run = session.get(Run, run_id)
            if run is None:  # pragma: no cover - defensive
                return
            run.status = status
            run.finished_at = utcnow()
            session.add(run)
