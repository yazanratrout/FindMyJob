import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session
from tests.fakes import scripted_api_fn

from findmyjob.llm.client import LlmClient
from findmyjob.models.job import Job
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.decide import DecidePipeline
from findmyjob.pipelines.judge import JudgePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline
from findmyjob.services.settings import update_app_settings

pytestmark = pytest.mark.usefixtures("seeded_session")

ANALYSIS = {
    "must_haves": ["Python"],
    "skills": [{"name": "Python", "required": True}, {"name": "SQL", "required": True}],
    "languages": [{"lang": "German", "cefr": "B2", "required": True}],
    "weekly_hours": 20,
    "contract_type": "werkstudent",
    "enrollment_required": "yes",
    "documents_requested": ["CV", "cover letter"],
    "salary_min": 20,
    "salary_max": 22,
    "salary_currency": "EUR",
    "salary_period": "hour",
    "seniority": "student",
    "source_snippets": {},
}
JUDGE = {
    "holistic_fit": 85,
    "rationale": "Great match.",
    "missing_qualifications": ["no dbt"],
    "strengths_to_highlight": ["3y Python", "SQL", "pipelines"],
    "recommendation": "apply",
}


def _seed_scored_job(db: Session) -> int:
    update_app_settings(
        db,
        {
            "target_titles": ["Werkstudent Data"],
            "target_fields": ["Data"],
            "score_threshold_recommend": 40,
            "score_threshold_maybe": 20,
        },
    )
    job = Job(
        source_key="ba",
        source_job_id="1",
        url="https://x.test/1",
        title="Werkstudent Data Science",
        normalized_title="werkstudent data science",
        company_name_raw="Acme",
        location_raw="München",
        jd_text=(
            "Werkstudent role. Build data pipelines with Python and SQL, "
            "20 Stunden pro Woche. Enrolled students only. German B2."
        ),
        posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
    )
    db.add(job)
    db.commit()
    return job.id


async def _run_pipeline() -> None:
    await Orchestrator(
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
        ]
    ).execute()


async def test_jobs_list_and_detail(client, db_session: Session):
    job_id = _seed_scored_job(db_session)
    await _run_pipeline()

    listed = client.get("/api/jobs?bucket=all").json()
    assert listed["counts"]  # bucket counts present
    card = next(j for j in listed["jobs"] if j["id"] == job_id)
    assert card["company"] == "Acme"
    assert card["final_score"] > 0
    assert card["decision"] in ("recommended", "maybe", "archived")
    assert card["salary"] == "20-22 EUR/hour"
    assert "3y Python" in card["strengths"]

    detail = client.get(f"/api/jobs/{job_id}").json()
    assert detail["rationale"] == "Great match."
    assert set(detail["soft_breakdown"]) >= {"skills_match", "language_fit"}
    docs = {d["doc_type"]: d for d in detail["documents_needed"]}
    assert docs["cover_letter"]["necessity"] == "required"
    assert detail["jd_text"]


async def test_jobs_detail_404_for_unscored(client, db_session: Session):
    job = Job(
        source_key="s",
        source_job_id="x",
        url="u",
        title="t",
        normalized_title="t",
    )
    db_session.add(job)
    db_session.commit()
    assert client.get(f"/api/jobs/{job.id}").status_code == 404


def test_jobs_requires_auth(unauth_client):
    assert unauth_client.get("/api/jobs").status_code == 401
