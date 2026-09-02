from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select

from findmyjob.models.application import Application, CoverLetter
from findmyjob.models.enums import Decision, JobLifecycle
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.models.run import Run
from findmyjob.services.analyze import ANALYZER_VERSION
from findmyjob.services.backup import backup, list_backups
from findmyjob.services.retention import prune

pytestmark = pytest.mark.usefixtures("seeded_session")

OLD = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=200)


def _job(
    db: Session, sid: str, *, decision=Decision.ARCHIVED, old=True, lifecycle=JobLifecycle.ACTIVE
) -> int:
    job = Job(
        source_key="s",
        source_job_id=sid,
        url=f"u/{sid}",
        title="t",
        normalized_title="t",
        lifecycle=lifecycle,
    )
    db.add(job)
    db.flush()
    if old:
        job.created_at = OLD
    run = Run(trigger="manual", status="completed")
    db.add(run)
    db.flush()
    db.add(JobScore(job_id=job.id, run_id=run.id, decision=decision))
    db.add(JobAnalysis(job_id=job.id, analyzer_version=ANALYZER_VERSION))
    db.flush()
    return job.id


def test_prune_removes_old_archived_unreferenced(db_session: Session):
    archived = _job(db_session, "arch")
    _job(db_session, "rec", decision=Decision.RECOMMENDED)
    _job(db_session, "recent", old=False)
    referenced = _job(db_session, "ref")
    db_session.add(Application(job_id=referenced))
    db_session.commit()

    report = prune(db_session)
    db_session.commit()

    remaining = {j.source_job_id for j in db_session.exec(select(Job)).all()}
    assert "arch" not in remaining
    assert {"rec", "recent", "ref"} <= remaining
    assert report.pruned == 1
    assert db_session.exec(select(JobAnalysis).where(JobAnalysis.job_id == archived)).all() == []


def test_prune_keeps_jobs_with_a_cover_letter(db_session: Session):
    job_id = _job(db_session, "cl")
    db_session.add(CoverLetter(job_id=job_id, content={}, claims_used=[]))
    db_session.commit()
    prune(db_session)
    db_session.commit()
    assert db_session.get(Job, job_id) is not None


def test_backup_writes_and_rotates(db_session: Session):
    now = datetime(2026, 9, 1, 3, 30)
    for i in range(3):
        backup(keep=2, now=now + timedelta(days=i))
    backups = list_backups()
    assert len(backups) == 2  # oldest rotated out
    assert all(b.suffix == ".db" for b in backups)
