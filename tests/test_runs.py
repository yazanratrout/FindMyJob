import pytest
from sqlmodel import Session

from findmyjob.db import get_engine
from findmyjob.models.enums import RunStatus, RunTrigger
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.registry import default_pipelines
from findmyjob.services.runs import list_runs, run_detail

pytestmark = pytest.mark.usefixtures("seeded_session")


def test_fetch_only_returns_just_fetch():
    assert [p.name for p in default_pipelines(fetch_only=True)] == ["fetch"]


def test_no_llm_drops_llm_stages():
    names = [p.name for p in default_pipelines(no_llm=True)]
    assert "analyze" not in names and "judge" not in names
    assert "score" in names and "fetch" in names


def test_full_sequence_order():
    assert [p.name for p in default_pipelines()] == [
        "fetch",
        "normalize",
        "enrich",
        "dedup",
        "prefilter",
        "analyze",
        "score",
        "judge",
        "decide",
        "notify",
    ]


async def test_run_detail_and_list():
    run_id = await Orchestrator(default_pipelines(fetch_only=True)).execute(
        trigger=RunTrigger.MANUAL
    )
    with Session(get_engine()) as s:
        detail = run_detail(s, run_id)
        assert detail is not None
        assert detail["run"].status == RunStatus.COMPLETED
        assert [stage.name for stage in detail["stages"]] == ["fetch"]
        assert detail["llm"]["calls"] == 0
        assert [r.id for r in list_runs(s)] == [run_id]

    with Session(get_engine()) as s:
        assert run_detail(s, 9999) is None


def test_runs_api_list_and_detail(client):
    assert client.get("/api/runs").json() == []
    assert client.get("/api/runs/1").status_code == 404


async def test_open_run_then_attach():
    orch = Orchestrator(default_pipelines(fetch_only=True))
    run_id = orch.open_run(RunTrigger.SCHEDULE)
    same = await orch.execute(trigger=RunTrigger.SCHEDULE, run_id=run_id)
    assert same == run_id
    with Session(get_engine()) as s:
        detail = run_detail(s, run_id)
        assert detail["run"].status == RunStatus.COMPLETED
