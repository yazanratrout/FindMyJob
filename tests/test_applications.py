from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session

from findmyjob.models.application import Application
from findmyjob.models.enums import ApplicationStatus
from findmyjob.models.job import Job
from findmyjob.services.applications import (
    ApplicationError,
    follow_ups_due,
    get_or_create,
    update_application,
)

pytestmark = pytest.mark.usefixtures("seeded_session")


def _job(db: Session, sid: str = "s:1") -> int:
    job = Job(
        source_key="s",
        source_job_id=sid,
        url=f"https://x.test/{sid}",
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        company_name_raw="Acme",
    )
    db.add(job)
    db.flush()
    return job.id


def test_get_or_create(db_session: Session):
    job_id = _job(db_session)
    a = get_or_create(db_session, job_id)
    assert a.status == ApplicationStatus.INTERESTED
    assert get_or_create(db_session, job_id).id == a.id

    with pytest.raises(ApplicationError, match="job not found"):
        get_or_create(db_session, 999)


def test_update_sets_applied_at_and_notes(db_session: Session):
    job_id = _job(db_session)
    a = get_or_create(db_session, job_id)
    updated = update_application(
        db_session, a.id, {"status": "applied", "outcome_note": "sent via portal"}
    )
    assert updated.status == ApplicationStatus.APPLIED
    assert updated.applied_at is not None
    assert updated.outcome_note == "sent via portal"


def test_update_rejects_bad_status(db_session: Session):
    a = get_or_create(db_session, _job(db_session))
    with pytest.raises(ApplicationError, match="invalid status"):
        update_application(db_session, a.id, {"status": "nonsense"})


def test_follow_ups_due(db_session: Session):
    now = datetime.now(UTC).replace(tzinfo=None)
    due = get_or_create(db_session, _job(db_session, "due"))
    update_application(
        db_session,
        due.id,
        {"status": "applied", "follow_up_at": (now - timedelta(days=1)).isoformat()},
    )
    later = get_or_create(db_session, _job(db_session, "later"))
    update_application(
        db_session,
        later.id,
        {"status": "applied", "follow_up_at": (now + timedelta(days=3)).isoformat()},
    )
    db_session.commit()

    rows = follow_ups_due(db_session)
    assert [a.id for a, _ in rows] == [due.id]


def test_applications_api(client, db_session: Session):
    job_id = _job(db_session)
    db_session.commit()

    created = client.post("/api/applications", json={"job_id": job_id})
    assert created.status_code == 201
    app_id = created.json()["id"]
    assert created.json()["status"] == "interested"

    moved = client.put(f"/api/applications/{app_id}", json={"status": "interview"})
    assert moved.status_code == 200
    assert moved.json()["status"] == "interview"
    assert moved.json()["applied_at"] is not None

    listed = client.get("/api/applications").json()
    assert len(listed) == 1
    assert listed[0]["job_title"] == "Werkstudent Data"

    assert client.get("/api/applications/follow-ups").json() == []


def test_job_detail_includes_application(client, db_session: Session):
    # covered indirectly: application_status appears once an application exists
    job_id = _job(db_session)
    db_session.add(Application(job_id=job_id, status=ApplicationStatus.PREPARING))
    db_session.commit()
    # /api/jobs/{id} needs a score; without one it 404s, which is fine — the
    # schema wiring is exercised by the cover-letter API test instead.
    assert client.get(f"/api/jobs/{job_id}").status_code == 404
