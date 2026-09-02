import json
from datetime import UTC, date, datetime, timedelta

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient
from findmyjob.models.enums import ContractType
from findmyjob.models.job import Job, JobAnalysis, JobScore
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline
from findmyjob.services.eligibility import (
    ANNUAL_FULL_DAYS,
    EligibilityError,
    add_entry,
    days_used,
    disqualifiers,
    gauge,
)
from findmyjob.services.profile import get_profile
from findmyjob.services.semester import add_term
from findmyjob.services.settings import update_app_settings

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]

YEAR = date.today().year


def _analysis(**over) -> JobAnalysis:
    a = JobAnalysis(job_id=1, analyzer_version="t")
    a.contract_type = ContractType.WERKSTUDENT
    a.weekly_hours = 20
    for k, v in over.items():
        setattr(a, k, v)
    return a


def test_days_used_clips_to_year_and_weights_halves(db_session: Session):
    add_entry(
        db_session,
        period_start=date(YEAR, 3, 1),
        period_end=date(YEAR, 3, 10),  # 10 full days
        day_type="full",
    )
    add_entry(
        db_session,
        period_start=date(YEAR, 6, 1),
        period_end=date(YEAR, 6, 10),  # 10 half days -> 5.0
        day_type="half",
    )
    add_entry(
        db_session,
        period_start=date(YEAR - 1, 12, 20),
        period_end=date(YEAR - 1, 12, 31),  # previous year -> ignored
        day_type="full",
    )
    assert days_used(db_session) == pytest.approx(15.0)


def test_add_entry_validates(db_session: Session):
    with pytest.raises(EligibilityError):
        add_entry(db_session, period_start=date(YEAR, 5, 10), period_end=date(YEAR, 5, 1))


def test_gauge_shape(db_session: Session):
    g = gauge(db_session)
    assert g["limit_full_days"] == ANNUAL_FULL_DAYS
    assert g["remaining"] == ANNUAL_FULL_DAYS


def test_disqualifiers_disabled_by_default(db_session: Session):
    assert (
        disqualifiers(
            db_session,
            Job(source_key="s", source_job_id="1", url="u", title="t", normalized_title="t"),
            _analysis(),
        )
        == []
    )


def test_disqualifiers_non_eu_days_exhausted(db_session: Session):
    update_app_settings(db_session, {"eligibility_module_enabled": True})
    p = get_profile(db_session)
    p.is_eu_eea = False
    db_session.add(p)
    add_entry(
        db_session,
        period_start=date(YEAR, 1, 1),
        period_end=date(YEAR, 1, 1) + timedelta(days=ANNUAL_FULL_DAYS),
        day_type="full",
    )
    db_session.commit()

    job = Job(source_key="s", source_job_id="1", url="u", title="t", normalized_title="t")
    codes = disqualifiers(db_session, job, _analysis())
    assert "eligibility:non_eu_days_exhausted" in codes


def test_disqualifiers_enrolment_ending(db_session: Session):
    update_app_settings(db_session, {"eligibility_module_enabled": True})
    p = get_profile(db_session)
    p.enrollment_valid_until = date.today() + timedelta(days=20)
    db_session.add(p)
    db_session.commit()

    job = Job(source_key="s", source_job_id="1", url="u", title="t", normalized_title="t")
    assert "eligibility:enrolment_ending" in disqualifiers(db_session, job, _analysis())


def test_disqualifiers_over_20h_in_term(db_session: Session):
    update_app_settings(db_session, {"eligibility_module_enabled": True})
    add_term(
        db_session,
        label="term",
        lecture_start=date.today() - timedelta(days=10),
        lecture_end=date.today() + timedelta(days=60),
    )
    db_session.commit()

    job = Job(source_key="s", source_job_id="1", url="u", title="t", normalized_title="t")
    codes = disqualifiers(db_session, job, _analysis(weekly_hours=32))
    assert "eligibility:over_20h_in_term" in codes


async def test_score_pipeline_hard_fails_on_eligibility(db_session: Session):
    update_app_settings(
        db_session,
        {
            "eligibility_module_enabled": True,
            "target_titles": ["Werkstudent"],
            "score_threshold_recommend": 20,
            "score_threshold_maybe": 10,
        },
    )
    p = get_profile(db_session)
    p.enrollment_valid_until = date.today() + timedelta(days=15)
    db_session.add(p)
    job = Job(
        source_key="s",
        source_job_id="1",
        url="https://x.test/1",
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        company_name_raw="Acme",
        location_raw="München",
        jd_text=(
            "Werkstudent role. Build data pipelines with Python and SQL, "
            "20 Stunden pro Woche, alongside your studies. Enrolled students."
        ),
        posted_at=datetime.now(UTC).replace(tzinfo=None) - timedelta(days=2),
    )
    db_session.add(job)
    db_session.commit()

    analysis_payload = {
        "skills": [{"name": "Python", "required": True}],
        "contract_type": "werkstudent",
        "weekly_hours": 20,
        "source_snippets": {},
    }
    await Orchestrator(
        [
            PrefilterPipeline(),
            AnalyzePipeline(
                client_factory=lambda: LlmClient(
                    api_fn=scripted_api_fn(json.dumps(analysis_payload))
                )
            ),
            ScorePipeline(),
        ]
    ).execute()

    with Session(get_engine()) as s:
        score = s.exec(select(JobScore)).one()
        assert score.hard_pass is False
        assert any("eligibility:" in f for f in score.hard_failures)


def test_eligibility_api(client, db_session: Session):
    created = client.post(
        "/api/eligibility/entries",
        json={"period_start": f"{YEAR}-03-01", "period_end": f"{YEAR}-03-05", "note": "internship"},
    )
    assert created.status_code == 201
    assert created.json()["day_count"] == 5

    assert len(client.get("/api/eligibility/entries").json()) == 1
    assert client.get("/api/eligibility").json()["days_used"] == 5.0

    eid = created.json()["id"]
    assert client.delete(f"/api/eligibility/entries/{eid}").status_code == 204
    assert client.get("/api/eligibility").json()["days_used"] == 0.0
