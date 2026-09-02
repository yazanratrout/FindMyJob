from datetime import datetime
from zoneinfo import ZoneInfo

import pytest

from findmyjob.scheduler import (
    PipelineScheduler,
    next_fire_time,
    parse_run_time,
)
from findmyjob.services.settings import update_app_settings

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_parse_run_time():
    assert parse_run_time("10:00") == (10, 0)
    assert parse_run_time("07:45") == (7, 45)
    with pytest.raises(ValueError, match="invalid run_time"):
        parse_run_time("25:00")


def test_next_fire_time_is_in_the_future_at_the_right_hour():
    nxt = next_fire_time("10:00", "Europe/Berlin")
    assert nxt is not None
    assert nxt > datetime.now(ZoneInfo("Europe/Berlin"))
    assert (nxt.hour, nxt.minute) == (10, 0)


async def test_scheduler_registers_and_reschedules(db_session):
    scheduler = PipelineScheduler()
    scheduler.start()
    try:
        assert scheduler.running
        first = scheduler.next_run_time()
        assert first is not None and (first.hour, first.minute) == (10, 0)

        update_app_settings(db_session, {"run_time": "06:30"})
        db_session.commit()
        scheduler.reschedule()

        second = scheduler.next_run_time()
        assert (second.hour, second.minute) == (6, 30)
    finally:
        scheduler.shutdown()


async def test_maybe_reschedule_is_noop_without_running_scheduler():
    import findmyjob.scheduler as mod

    mod._scheduler = None
    mod.maybe_reschedule()  # must not raise
