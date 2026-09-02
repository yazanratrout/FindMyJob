from datetime import UTC, datetime, timedelta

import httpx
import pytest
import respx
from sqlmodel import Session, select

from findmyjob.config import get_settings
from findmyjob.db import get_engine
from findmyjob.models.enums import PipelineStatus, RunStatus, RunTrigger
from findmyjob.models.job import Job
from findmyjob.models.run import PipelineRun, Run
from findmyjob.pipelines.fetch import FetchPipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.services.http import HttpClient
from findmyjob.services.settings import update_app_settings
from findmyjob.sources.registry import build_sources

pytestmark = [pytest.mark.usefixtures("seeded_session"), pytest.mark.slow]

_ARBEITNOW = "https://www.arbeitnow.com/api/job-board-api"


def _only_arbeitnow(db: Session) -> None:
    update_app_settings(
        db,
        {
            "sources_enabled": {
                k: (k == "arbeitnow") for k in ["ba", "adzuna", "arbeitnow", "themuse"]
            },
            "target_titles": ["Werkstudent"],
        },
    )
    db.commit()


def _board(*slugs: str) -> httpx.Response:
    return httpx.Response(
        200,
        json={
            "data": [
                {
                    "slug": s,
                    "title": "Werkstudent Data",
                    "company_name": "DataCo",
                    "location": "München",
                    "remote": False,
                    "url": f"https://arbeitnow.test/{s}",
                    "description": "<p>Python, SQL.</p>",
                    "tags": [],
                    "created_at": int((datetime.now(UTC) - timedelta(days=2)).timestamp()),
                }
                for s in slugs
            ]
        },
    )


def test_build_sources_skips_unconfigured_and_disabled(db_session: Session):
    from findmyjob.pipelines.context import load_app_settings

    update_app_settings(
        db_session,
        {"sources_enabled": {"ba": True, "adzuna": True, "arbeitnow": False, "themuse": True}},
    )
    db_session.commit()
    app_settings = load_app_settings(db_session)

    http = HttpClient(min_interval_s=0.0)
    keys = {s.key for s in build_sources(get_settings(), app_settings, http)}
    # ba + themuse need no secret; adzuna needs creds (absent); arbeitnow disabled
    assert keys == {"ba", "themuse"}


@respx.mock
async def test_fetch_stores_jobs_and_is_idempotent(db_session: Session):
    _only_arbeitnow(db_session)
    respx.get(_ARBEITNOW).mock(return_value=_board("a", "b", "c"))

    orch = Orchestrator([FetchPipeline()])
    run_id = await orch.execute(trigger=RunTrigger.MANUAL)

    with Session(get_engine()) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.COMPLETED
        jobs = s.exec(select(Job)).all()
        assert {j.source_job_id for j in jobs} == {"a", "b", "c"}
        assert all(j.first_seen_run_id == run_id for j in jobs)
        assert all(j.normalized_title == "werkstudent data" for j in jobs)

    # second run: same postings -> no new rows
    run2 = await orch.execute()
    with Session(get_engine()) as s:
        assert len(s.exec(select(Job)).all()) == 3
        pr = s.exec(select(PipelineRun).where(PipelineRun.run_id == run2)).one()
        assert pr.stats.get("new", 0) == 0
        assert pr.stats["found"] == 3


@respx.mock
async def test_fetch_contains_a_failing_source(db_session: Session):
    update_app_settings(
        db_session,
        {
            "sources_enabled": {
                k: k in ("arbeitnow", "themuse") for k in ["ba", "adzuna", "arbeitnow", "themuse"]
            },
            "target_titles": ["Werkstudent"],
        },
    )
    db_session.commit()

    respx.get(_ARBEITNOW).mock(return_value=_board("ok-1"))
    respx.get("https://www.themuse.com/api/public/jobs").mock(return_value=httpx.Response(500))

    run_id = await Orchestrator([FetchPipeline()]).execute()
    with Session(get_engine()) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.COMPLETED  # critical stage still completed
        pr = s.exec(select(PipelineRun)).one()
        assert pr.status == PipelineStatus.PARTIAL
        assert any(e["scope"] == "source:themuse" for e in pr.errors)
        assert {j.source_job_id for j in s.exec(select(Job)).all()} == {"ok-1"}


@respx.mock
async def test_fetch_with_no_active_sources_completes_clean(db_session: Session):
    update_app_settings(
        db_session,
        {"sources_enabled": dict.fromkeys(["ba", "adzuna", "arbeitnow", "themuse"], False)},
    )
    db_session.commit()

    run_id = await Orchestrator([FetchPipeline()]).execute()
    with Session(get_engine()) as s:
        assert s.get(Run, run_id).status == RunStatus.COMPLETED
        assert s.exec(select(Job)).all() == []
