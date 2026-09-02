import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient
from findmyjob.models.digest import Digest
from findmyjob.models.job import Job
from findmyjob.models.run import Run
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.decide import DecidePipeline
from findmyjob.pipelines.judge import JudgePipeline
from findmyjob.pipelines.notify import NotifyPipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline
from findmyjob.services.digest import (
    build_digest,
    mark_all_seen,
    mark_seen,
    unseen_count,
)
from findmyjob.services.settings import update_app_settings

pytestmark = pytest.mark.usefixtures("seeded_session")

ANALYSIS = {
    "skills": [{"name": "Python", "required": True}],
    "languages": [{"lang": "German", "cefr": "B2", "required": True}],
    "weekly_hours": 20,
    "contract_type": "werkstudent",
    "seniority": "student",
    "source_snippets": {},
}
JUDGE = {
    "holistic_fit": 90,
    "rationale": "x",
    "missing_qualifications": [],
    "strengths_to_highlight": ["Python"],
    "recommendation": "apply",
}


def _job(db: Session, sid: str = "s:1") -> int:
    job = Job(
        source_key="s",
        source_job_id=sid,
        url=f"https://x.test/{sid}",
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        company_name_raw="Acme",
        location_raw="München",
        jd_text=(
            "Werkstudent in our data team. You will build and maintain data "
            "pipelines with Python and SQL, 20 Stunden pro Woche, alongside your "
            "studies. Enrolled students only, German B2 required."
        ),
        posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=1),
    )
    db.add(job)
    db.flush()
    return job.id


async def _run() -> int:
    return await Orchestrator(
        [
            PrefilterPipeline(),
            AnalyzePipeline(
                client_factory=lambda: LlmClient(api_fn=scripted_api_fn(json.dumps(ANALYSIS)))
            ),
            ScorePipeline(),
            JudgePipeline(
                client_factory=lambda: LlmClient(api_fn=scripted_api_fn(json.dumps(JUDGE)))
            ),
            DecidePipeline(),
            NotifyPipeline(),
        ]
    ).execute()


async def test_notify_pipeline_builds_a_digest(db_session: Session):
    update_app_settings(
        db_session,
        {
            "target_titles": ["Werkstudent Data"],
            "target_fields": ["Data"],
            "score_threshold_recommend": 30,
            "score_threshold_maybe": 10,
        },
    )
    _job(db_session)
    _job(db_session, "s:2")
    db_session.commit()

    run_id = await _run()
    with Session(get_engine()) as s:
        digest = s.exec(select(Digest).where(Digest.run_id == run_id)).one()
        assert digest.summary["recommended"] >= 1
        assert "new_jobs" in digest.summary
        assert digest.items and digest.items[0]["title"] == "Werkstudent Data"
        assert digest.seen is False


def test_build_digest_records_budget_warning(db_session: Session):
    run = Run(trigger="manual", status="completed")
    run.budget_exhausted = True
    db_session.add(run)
    db_session.flush()
    digest = build_digest(db_session, run.id)
    assert digest.summary["budget_exhausted"] is True
    assert any("budget" in w.lower() for w in digest.warnings)


def test_build_digest_is_idempotent(db_session: Session):
    run = Run(trigger="manual", status="completed")
    db_session.add(run)
    db_session.flush()
    a = build_digest(db_session, run.id)
    b = build_digest(db_session, run.id)
    assert a.id == b.id
    assert len(db_session.exec(select(Digest)).all()) == 1


def test_seen_helpers(db_session: Session):
    run = Run(trigger="manual", status="completed")
    db_session.add(run)
    db_session.flush()
    digest = build_digest(db_session, run.id)
    db_session.commit()

    assert unseen_count(db_session) == 1
    mark_seen(db_session, digest.id)
    assert unseen_count(db_session) == 0

    run2 = Run(trigger="manual", status="completed")
    db_session.add(run2)
    db_session.flush()
    build_digest(db_session, run2.id)
    assert unseen_count(db_session) == 1
    assert mark_all_seen(db_session) == 1
    assert unseen_count(db_session) == 0


def test_digests_api(client, db_session: Session):
    run = Run(trigger="manual", status="completed")
    db_session.add(run)
    db_session.flush()
    build_digest(db_session, run.id)
    db_session.commit()

    listed = client.get("/api/digests").json()
    assert len(listed) == 1
    did = listed[0]["id"]

    assert client.get("/api/digests/unseen-count").json()["count"] == 1
    seen = client.post(f"/api/digests/{did}/seen")
    assert seen.status_code == 200 and seen.json()["seen"] is True
    assert client.get("/api/digests/unseen-count").json()["count"] == 0
