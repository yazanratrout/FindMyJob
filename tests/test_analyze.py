import json

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.analyzer import ANALYZER_VERSION, analyze_posting
from findmyjob.llm.client import LlmClient
from findmyjob.models.enums import ContractType, JobLifecycle
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.services.analyze import analyze_job

pytestmark = pytest.mark.usefixtures("seeded_session")

ANALYSIS = {
    "must_haves": ["enrolled student", "Python"],
    "nice_haves": ["dbt"],
    "skills": [{"name": "Python", "required": True}, {"name": "SQL", "required": False}],
    "languages": [{"lang": "German", "cefr": "B2", "required": True}],
    "weekly_hours": 20,
    "weekly_hours_basis": "stated",
    "contract_type": "werkstudent",
    "enrollment_required": "yes",
    "english_only": False,
    "application_method": "ats_form",
    "documents_requested": ["CV", "Immatrikulationsbescheinigung"],
    "seniority": "student",
    "red_flags": [],
    "source_snippets": {"weekly_hours": "20 Stunden/Woche"},
}
JD = "We are looking for a Werkstudent. 20 Stunden/Woche. Enrolled students only. Python and SQL."


def _client(*payloads: dict) -> LlmClient:
    return LlmClient(api_fn=scripted_api_fn(*[json.dumps(p) for p in payloads]))


def _job(db: Session, *, sid: str = "s:1", jd: str = JD, canonical: bool = True) -> int:
    job = Job(
        source_key="s",
        source_job_id=sid,
        url=f"https://x.test/{sid}",
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        company_name_raw="Acme",
        jd_text=jd,
        canonical_job_id=None if canonical else 1,
    )
    db.add(job)
    db.flush()
    return job.id


def test_analyze_posting_parses_result():
    result, _ = analyze_posting(
        title="Werkstudent Data",
        company="Acme",
        city="München",
        jd_text=JD,
        client=_client(ANALYSIS),
    )
    assert result.weekly_hours == 20
    assert result.enrollment_required == "yes"
    assert [s.name for s in result.skills] == ["Python", "SQL"]


def test_analyze_job_persists_and_is_idempotent(db_session: Session):
    job_id = _job(db_session)
    db_session.commit()

    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        analysis, llm = analyze_job(s, job, city="München", client=_client(ANALYSIS))
        s.commit()
        assert llm is not None
        assert analysis.analyzer_version == ANALYZER_VERSION
        assert analysis.contract_type == ContractType.WERKSTUDENT
        assert analysis.weekly_hours == 20

    with Session(get_engine()) as s:
        job = s.get(Job, job_id)
        again, llm2 = analyze_job(s, job, city="München", client=_client(ANALYSIS))
        assert llm2 is None  # already analyzed, no LLM call
        assert again.id == analysis.id


async def test_pipeline_analyzes_only_eligible_jobs(db_session: Session):
    good = _job(db_session, sid="good:1")
    thin = _job(db_session, sid="thin:1", jd="too short")
    dupe = _job(db_session, sid="dupe:1", canonical=False)
    db_session.commit()

    await Orchestrator(
        [AnalyzePipeline(client_factory=lambda: _client(ANALYSIS, ANALYSIS, ANALYSIS))]
    ).execute()

    with Session(get_engine()) as s:
        analyzed_ids = {a.job_id for a in s.exec(select(JobAnalysis)).all()}
        assert analyzed_ids == {good}
        assert s.get(Job, thin) is not None and thin not in analyzed_ids
        assert dupe not in analyzed_ids


async def test_pipeline_skips_dead_jobs(db_session: Session):
    job_id = _job(db_session)
    db_session.get(Job, job_id).lifecycle = JobLifecycle.DEAD
    db_session.commit()

    await Orchestrator([AnalyzePipeline(client_factory=lambda: _client(ANALYSIS))]).execute()
    with Session(get_engine()) as s:
        assert s.exec(select(JobAnalysis)).all() == []


async def test_identical_postings_hit_the_cache(db_session: Session):
    _job(db_session, sid="a:1")
    _job(db_session, sid="b:1")  # same title/company/jd -> same prompt
    db_session.commit()

    shared = _client(ANALYSIS)  # one scripted response, reused
    run_id = await Orchestrator([AnalyzePipeline(client_factory=lambda: shared)]).execute()

    with Session(get_engine()) as s:
        from findmyjob.models.run import PipelineRun

        pr = s.exec(select(PipelineRun).where(PipelineRun.run_id == run_id)).one()
        assert pr.stats["analyzed"] == 2
        assert pr.stats.get("cache_hits") == 1
        assert len(s.exec(select(JobAnalysis)).all()) == 2
