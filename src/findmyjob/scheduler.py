"""Daily pipeline scheduler.

An in-process APScheduler job fires the full pipeline at ``AppSettings.run_time``
in ``AppSettings.run_timezone``. A missed run (laptop asleep) is coalesced and
fired once on wake within a one-hour grace window. The independent ``launchd``
job in ``deploy/`` is a belt-and-braces fallback for when the server is down;
the orchestrator is idempotent so a double run is cheap (dedup + LLM cache).
"""

from __future__ import annotations

from datetime import datetime
from zoneinfo import ZoneInfo

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger

from findmyjob.db import session_scope
from findmyjob.logging import get_logger
from findmyjob.models.enums import RunTrigger
from findmyjob.services.settings import get_app_settings

log = get_logger("scheduler")

_JOB_ID = "daily-pipeline"
_GRACE_SECONDS = 3600


def parse_run_time(run_time: str) -> tuple[int, int]:
    hour, minute = (int(part) for part in run_time.split(":"))
    if not (0 <= hour < 24 and 0 <= minute < 60):
        raise ValueError(f"invalid run_time {run_time!r}")
    return hour, minute


def next_fire_time(run_time: str, run_timezone: str) -> datetime | None:
    """Compute the next scheduled fire time without a running scheduler (for the CLI)."""
    hour, minute = parse_run_time(run_time)
    tz = ZoneInfo(run_timezone)
    trigger = CronTrigger(hour=hour, minute=minute, timezone=tz)
    nxt: datetime | None = trigger.get_next_fire_time(None, datetime.now(tz))
    return nxt


async def _run_pipeline() -> None:
    from findmyjob.pipelines.registry import build_default_orchestrator

    log.info("scheduler.fire")
    await build_default_orchestrator().execute(trigger=RunTrigger.SCHEDULE)


class PipelineScheduler:
    def __init__(self) -> None:
        self._scheduler = AsyncIOScheduler()

    @property
    def running(self) -> bool:
        return bool(self._scheduler.running)

    def start(self) -> None:
        if self._scheduler.running:
            return
        self._scheduler.start()
        self.reschedule()

    def reschedule(self) -> None:
        with session_scope() as session:
            settings = get_app_settings(session)
            run_time, run_tz = settings.run_time, settings.run_timezone
        hour, minute = parse_run_time(run_time)
        self._scheduler.add_job(
            _run_pipeline,
            CronTrigger(hour=hour, minute=minute, timezone=ZoneInfo(run_tz)),
            id=_JOB_ID,
            replace_existing=True,
            misfire_grace_time=_GRACE_SECONDS,
            coalesce=True,
            max_instances=1,
        )
        log.info(
            "scheduler.rescheduled",
            run_time=run_time,
            timezone=run_tz,
            next_fire=str(self.next_run_time()),
        )

    def next_run_time(self) -> datetime | None:
        job = self._scheduler.get_job(_JOB_ID)
        nxt: datetime | None = job.next_run_time if job else None
        return nxt

    def shutdown(self) -> None:
        if self._scheduler.running:
            self._scheduler.shutdown(wait=False)


_scheduler: PipelineScheduler | None = None


def get_scheduler() -> PipelineScheduler:
    global _scheduler
    if _scheduler is None:
        _scheduler = PipelineScheduler()
    return _scheduler


def maybe_reschedule() -> None:
    """Re-apply the cron trigger if the scheduler is running (called after settings change)."""
    if _scheduler is not None and _scheduler.running:
        _scheduler.reschedule()
