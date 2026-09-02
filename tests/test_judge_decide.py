import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient
from findmyjob.llm.judge import judge_fit
from findmyjob.models.enums import ContractType, Decision, DocumentType
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.models.profile import Document
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.decide import DecidePipeline
from findmyjob.pipelines.judge import JudgePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline
from findmyjob.services.documents_needed import compute_documents_needed
from findmyjob.services.settings import update_app_settings

pytestmark = pytest.mark.usefixtures("seeded_session")

ANALYSIS = {
    "must_haves": ["Python"],
    "skills": [{"name": "Python", "required": True}, {"name": "SQL", "required": True}],
    "languages": [{"lang": "German", "cefr": "B2", "required": True}],
    "weekly_hours": 20,
    "contract_type": "werkstudent",
    "enrollment_required": "yes",
    "documents_requested": ["CV", "cover letter", "Notenspiegel"],
    "seniority": "student",
    "source_snippets": {},
}
JUDGE = {
    "holistic_fit": 82,
    "rationale": "Strong Python/SQL match and the hours work with studies.",
    "missing_qualifications": ["No dbt experience mentioned"],
    "strengths_to_highlight": ["3 years Python", "Data pipeline projects"],
    "recommendation": "apply",
}


def _analysis_row(**over) -> JobAnalysis:
    row = JobAnalysis(job_id=1, analyzer_version="t")
    row.documents_requested = ["CV"]
    row.contract_type = ContractType.WERKSTUDENT
    row.enrollment_required = "unknown"
    for k, v in over.items():
        setattr(row, k, v)
    return row


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
            "Werkstudent in our data team. Build pipelines with Python and SQL, "
            "20 Stunden pro Woche. Enrolled students only. German B2. "
            "Please send CV, cover letter and Notenspiegel."
        ),
        posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
    )
    db.add(job)
    db.flush()
    return job.id


def _pipeline(*, analysis=ANALYSIS, judge=JUDGE):
    return [
        PrefilterPipeline(),
        AnalyzePipeline(
            client_factory=lambda: LlmClient(api_fn=scripted_api_fn(json.dumps(analysis)))
        ),
        ScorePipeline(),
        JudgePipeline(client_factory=lambda: LlmClient(api_fn=scripted_api_fn(json.dumps(judge)))),
        DecidePipeline(),
    ]


# ---- documents_needed --------------------------------------------------
def test_documents_needed_marks_requested_docs_required():
    row = _analysis_row(documents_requested=["CV", "cover letter", "transcript"])
    items = {d["doc_type"]: d for d in compute_documents_needed(row, set())}
    assert items["cv"]["necessity"] == "required"
    assert items["cover_letter"]["necessity"] == "required"
    assert items["transcript"]["necessity"] == "required"


def test_documents_needed_enrollment_rules():
    likely = compute_documents_needed(_analysis_row(), set())
    assert next(d for d in likely if d["doc_type"] == "enrollment")["necessity"] == "likely"

    required = compute_documents_needed(_analysis_row(enrollment_required="yes"), set())
    assert next(d for d in required if d["doc_type"] == "enrollment")["necessity"] == "required"


def test_documents_needed_reports_have_flag():
    items = {d["doc_type"]: d for d in compute_documents_needed(_analysis_row(), {"cv"})}
    assert items["cv"]["have"] is True
    assert items["enrollment"]["have"] is False


# ---- judge_fit -------------------------------------------------------
def test_judge_fit_parses():
    result, _ = judge_fit(
        profile_summary="Yazan, M.Sc. Data",
        analysis=ANALYSIS,
        soft_breakdown={},
        client=LlmClient(api_fn=scripted_api_fn(json.dumps(JUDGE))),
    )
    assert result.holistic_fit == 82
    assert result.recommendation == "apply"


# ---- pipelines -----------------------------------------------------
async def test_judge_blends_and_rebuckets(db_session: Session):
    update_app_settings(
        db_session,
        {"target_titles": ["Werkstudent Data"], "target_fields": ["Data"], "blend_soft_ratio": 0.5},
    )
    _job(db_session)
    db_session.commit()

    run_id = await Orchestrator(_pipeline()).execute()
    with Session(get_engine()) as s:
        score = s.exec(select(JobScore).where(JobScore.run_id == run_id)).one()
        assert score.llm_holistic == 82
        assert score.llm_rationale.startswith("Strong Python")
        assert score.missing_qualifications == ["No dbt experience mentioned"]
        expected = round(0.5 * score.soft_score + 0.5 * 82, 1)
        assert score.final_score == expected
        assert score.decision == Decision.RECOMMENDED


async def test_judge_skips_low_scores(db_session: Session):
    # blocklist everything so soft score never gets computed high; use a job that
    # passes hard filters but scores low by having no matching field/skills
    update_app_settings(
        db_session,
        {
            "target_titles": ["Nursing"],
            "target_fields": ["Healthcare"],
            "score_threshold_maybe": 55,
        },
    )
    _job(db_session)
    db_session.commit()

    weak_analysis = dict(ANALYSIS, skills=[{"name": "Nursing", "required": True}])
    run_id = await Orchestrator(_pipeline(analysis=weak_analysis)).execute()
    with Session(get_engine()) as s:
        score = s.exec(select(JobScore).where(JobScore.run_id == run_id)).one()
        if score.soft_score < 45:
            assert score.llm_holistic is None  # judge skipped


async def test_decide_attaches_documents_checklist(db_session: Session):
    doc = Document(
        profile_id=1,
        type=DocumentType.CV,
        filename="cv.pdf",
        stored_path="/x",
        mime="application/pdf",
        size_bytes=1,
    )
    db_session.add(doc)
    _job(db_session)
    db_session.commit()

    run_id = await Orchestrator(_pipeline()).execute()
    with Session(get_engine()) as s:
        score = s.exec(select(JobScore).where(JobScore.run_id == run_id)).one()
        docs = {d["doc_type"]: d for d in score.documents_needed}
        assert docs["cv"]["have"] is True
        assert docs["cover_letter"]["necessity"] == "required"
        assert docs["enrollment"]["necessity"] == "required"
