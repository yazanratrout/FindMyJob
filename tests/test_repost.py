from datetime import timedelta

import pytest
from sqlmodel import Session, select

from findmyjob.models.base import utcnow
from findmyjob.models.enums import Decision, JobLifecycle
from findmyjob.models.job import Job, JobScore
from findmyjob.models.run import Run
from findmyjob.services.jobs import store_raw_job
from findmyjob.sources.base import RawJob

pytestmark = pytest.mark.usefixtures("seeded_session")


def _raw(sid: str = "ba:1") -> RawJob:
    return RawJob(
        source_key="ba",
        source_job_id=sid,
        url="https://x.test/1",
        title="Werkstudent Data",
        company_name="Acme",
        description_text="Python and SQL, ~20h/week during the semester.",
    )


def _run(db: Session) -> int:
    run = Run(trigger="manual", status="completed")
    db.add(run)
    db.flush()
    return run.id


def test_routine_reappearance_is_not_new(db_session: Session):
    run_id = _run(db_session)
    job, new1 = store_raw_job(db_session, _raw(), run_id=run_id)
    db_session.commit()
    assert new1 is True

    seen_before = job.last_seen_at
    job.last_seen_at = utcnow() - timedelta(days=2)  # recent-ish
    db_session.commit()

    _, new2 = store_raw_job(db_session, _raw(), run_id=run_id, repost_days=21)
    db_session.commit()
    assert new2 is False
    assert db_session.get(Job, job.id).last_seen_at > seen_before


def test_stale_duplicate_reappearing_is_treated_as_new(db_session: Session):
    run_id = _run(db_session)
    canonical, _ = store_raw_job(db_session, _raw("ba:canon"), run_id=run_id)
    dupe, _ = store_raw_job(db_session, _raw("adzuna:dupe"), run_id=run_id)
    db_session.flush()
    dupe.canonical_job_id = canonical.id
    dupe.last_seen_at = utcnow() - timedelta(days=40)
    db_session.add(JobScore(job_id=dupe.id, run_id=run_id, decision=Decision.ARCHIVED))
    db_session.commit()

    run2 = _run(db_session)
    refreshed, is_new = store_raw_job(db_session, _raw("adzuna:dupe"), run_id=run2, repost_days=21)
    db_session.commit()

    assert is_new is True
    assert refreshed.canonical_job_id is None
    assert refreshed.lifecycle is JobLifecycle.ACTIVE
    assert refreshed.first_seen_run_id == run2
    assert db_session.exec(select(JobScore).where(JobScore.job_id == dupe.id)).all() == []


def test_dead_job_reappearing_after_window_is_revived(db_session: Session):
    run_id = _run(db_session)
    job, _ = store_raw_job(db_session, _raw("ba:dead"), run_id=run_id)
    db_session.flush()
    job.lifecycle = JobLifecycle.DEAD
    job.last_seen_at = utcnow() - timedelta(days=30)
    db_session.commit()

    _, is_new = store_raw_job(db_session, _raw("ba:dead"), run_id=run_id, repost_days=21)
    db_session.commit()
    assert is_new is True
    assert db_session.get(Job, job.id).lifecycle is JobLifecycle.ACTIVE
