import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient
from findmyjob.models.enums import Decision
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline
from findmyjob.services.settings import update_app_settings

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]

ANALYSIS = {
    "must_haves": ["Python"],
    "skills": [{"name": "Python", "required": True}, {"name": "SQL", "required": True}],
    "languages": [{"lang": "German", "cefr": "B2", "required": True}],
    "weekly_hours": 20,
    "contract_type": "werkstudent",
    "seniority": "student",
    "source_snippets": {},
}


def _client() -> LlmClient:
    return LlmClient(api_fn=scripted_api_fn(json.dumps(ANALYSIS)))


def _job(db: Session, *, sid: str, title="Werkstudent Data", loc="München", jd=None) -> int:
    job = Job(
        source_key="s",
        source_job_id=sid,
        url=f"https://x.test/{sid}",
        title=title,
        normalized_title=title.lower(),
        company_name_raw="Acme",
        location_raw=loc,
        jd_text=jd
        or (
            "Werkstudent role in our data team. You will build data pipelines with "
            "Python and SQL, 20 Stunden pro Woche, alongside your studies. Enrolled "
            "students only. German B2 required."
        ),
        posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=3),
    )
    db.add(job)
    db.flush()
    return job.id


async def test_prefilter_marks_blacklisted_job(db_session: Session):
    update_app_settings(db_session, {"keywords_block": ["marketing"]})
    good = _job(db_session, sid="g:1")
    bad = _job(db_session, sid="b:1", title="Werkstudent Marketing")
    db_session.commit()

    await Orchestrator([PrefilterPipeline()]).execute()
    with Session(get_engine()) as s:
        by_job = {sc.job_id: sc for sc in s.exec(select(JobScore)).all()}
        assert by_job[good].hard_pass is True
        assert by_job[bad].hard_pass is False
        assert by_job[bad].decision == Decision.ARCHIVED


async def test_analyze_skips_prefilter_rejects(db_session: Session):
    update_app_settings(db_session, {"keywords_block": ["sales"]})
    _job(db_session, sid="ok:1")
    _job(db_session, sid="no:1", title="Werkstudent Sales")
    db_session.commit()

    orch = Orchestrator([PrefilterPipeline(), AnalyzePipeline(client_factory=_client)])
    await orch.execute()
    with Session(get_engine()) as s:
        analyzed = {a.job_id for a in s.exec(select(JobAnalysis)).all()}
        titles = {s.get(Job, jid).title for jid in analyzed}
        assert "Werkstudent Sales" not in titles
        assert len(analyzed) == 1


async def test_score_produces_decision(db_session: Session):
    update_app_settings(
        db_session,
        {"target_titles": ["Werkstudent Data"], "target_fields": ["Data"]},
    )
    _job(db_session, sid="s:1")
    db_session.commit()

    run_id = await Orchestrator(
        [PrefilterPipeline(), AnalyzePipeline(client_factory=_client), ScorePipeline()]
    ).execute()

    with Session(get_engine()) as s:
        score = s.exec(select(JobScore).where(JobScore.run_id == run_id)).one()
        assert score.hard_pass is True
        assert 0 < score.soft_score <= 100
        assert score.final_score == score.soft_score
        assert score.decision in (Decision.RECOMMENDED, Decision.MAYBE, Decision.ARCHIVED)
        assert set(score.soft_breakdown) == {
            "skills_match",
            "field_relevance",
            "language_fit",
            "hours_fit",
            "seniority_fit",
            "recency",
            "salary_fit",
            "company_affinity",
        }


async def test_score_applies_analysis_hard_check(db_session: Session):
    update_app_settings(db_session, {"hours_hard": True, "hours_max": 20})
    _job(db_session, sid="ft:1")
    db_session.commit()

    full_time = dict(ANALYSIS, weekly_hours=40)
    client = lambda: LlmClient(api_fn=scripted_api_fn(json.dumps(full_time)))  # noqa: E731
    run_id = await Orchestrator(
        [PrefilterPipeline(), AnalyzePipeline(client_factory=client), ScorePipeline()]
    ).execute()

    with Session(get_engine()) as s:
        score = s.exec(select(JobScore).where(JobScore.run_id == run_id)).one()
        assert score.hard_pass is False
        assert "hours" in score.hard_failures
        assert score.decision == Decision.ARCHIVED
