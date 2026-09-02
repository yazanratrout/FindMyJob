import json
from datetime import UTC, datetime, timedelta

import pytest
from sqlmodel import Session, select
from tests.fakes import scripted_api_fn

from findmyjob.config import reset_settings_cache
from findmyjob.db import get_engine
from findmyjob.llm.client import LlmClient
from findmyjob.models.enums import LlmPurpose
from findmyjob.models.job import Job, JobAnalysis
from findmyjob.models.run import LlmCall, Run
from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.services.cost import (
    budget_ok,
    current_month_cost_eur,
    mark_budget_exhausted,
    month_to_date,
    remaining_budget_eur,
)

pytestmark = pytest.mark.usefixtures("seeded_session")


def _call(db: Session, cost: float, purpose=LlmPurpose.ANALYZE, days_ago: int = 0) -> None:
    call = LlmCall(purpose=purpose, model="m", cost_eur=cost, input_tokens=100, output_tokens=50)
    call.created_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(days=days_ago)
    db.add(call)
    db.flush()


def test_current_month_cost_ignores_old_calls(db_session: Session):
    _call(db_session, 1.0)
    _call(db_session, 2.0)
    _call(db_session, 5.0, days_ago=40)  # previous month
    db_session.commit()
    assert current_month_cost_eur(db_session) == pytest.approx(3.0)


def test_remaining_budget_and_ok(db_session: Session, monkeypatch):
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_EUR", "5")
    reset_settings_cache()
    _call(db_session, 3.0)
    db_session.commit()
    assert remaining_budget_eur(db_session) == pytest.approx(2.0)
    assert budget_ok(db_session) is True
    _call(db_session, 2.5)
    db_session.commit()
    assert budget_ok(db_session) is False


def test_month_to_date_shape(db_session: Session):
    _call(db_session, 1.0, purpose=LlmPurpose.ANALYZE)
    _call(db_session, 2.0, purpose=LlmPurpose.JUDGE)
    db_session.commit()
    mtd = month_to_date(db_session)
    assert mtd["cost_eur"] == pytest.approx(3.0)
    assert set(mtd["per_purpose"]) == {"analyze", "judge"}
    assert mtd["projected_month_end_eur"] >= mtd["cost_eur"]


def test_mark_budget_exhausted(db_session: Session):
    run = Run(trigger="manual")
    db_session.add(run)
    db_session.flush()
    mark_budget_exhausted(db_session, run.id)
    db_session.commit()
    assert db_session.get(Run, run.id).budget_exhausted is True


async def test_analyze_stops_when_budget_exhausted(db_session: Session, monkeypatch):
    monkeypatch.setenv("LLM_MONTHLY_BUDGET_EUR", "0.01")
    reset_settings_cache()
    _call(db_session, 0.5)  # already over the 0.01 budget
    job = Job(
        source_key="s",
        source_job_id="1",
        url="https://x.test/1",
        title="Werkstudent Data",
        normalized_title="werkstudent data",
        company_name_raw="Acme",
        jd_text="Werkstudent role with Python and SQL, 20h/week, enrolled.",
    )
    db_session.add(job)
    db_session.commit()

    run_id = await Orchestrator(
        [AnalyzePipeline(client_factory=lambda: LlmClient(api_fn=scripted_api_fn(json.dumps({}))))]
    ).execute()

    with Session(get_engine()) as s:
        assert s.get(Run, run_id).budget_exhausted is True
        assert s.exec(select(JobAnalysis)).all() == []


def test_costs_endpoint(client):
    body = client.get("/api/costs").json()
    assert body["cost_eur"] == 0
    assert "per_purpose" in body and "remaining_eur" in body
