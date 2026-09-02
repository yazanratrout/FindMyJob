import pytest
from sqlmodel import Session, select

from findmyjob.db import get_engine
from findmyjob.models.enums import PipelineStatus, RunStatus, RunTrigger
from findmyjob.models.run import PipelineRun, Run
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.pipelines.orchestrator import Orchestrator

pytestmark = pytest.mark.usefixtures("seeded_session")


class RecordingPipeline(Pipeline):
    name = "recording"

    def __init__(self, name: str, *, found: int = 0):
        self.name = name  # type: ignore[misc]
        self._found = found

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        res.bump("found", self._found)
        return res


class BoomPipeline(Pipeline):
    name = "boom"
    critical = False

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        raise RuntimeError("kaboom")


class CriticalBoomPipeline(Pipeline):
    name = "critical-boom"
    critical = True

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        raise RuntimeError("fatal")


class PartialPipeline(Pipeline):
    name = "partial"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        res.add_error("item:1", ValueError("bad row"))
        return res


async def test_happy_path_records_run_and_pipeline_rows():
    orch = Orchestrator([RecordingPipeline("a", found=3), RecordingPipeline("b", found=2)])
    run_id = await orch.execute(trigger=RunTrigger.MANUAL)

    with Session(get_engine()) as s:
        run = s.get(Run, run_id)
        assert run is not None
        assert run.status == RunStatus.COMPLETED
        assert run.finished_at is not None
        assert run.stats == {"a.found": 3, "b.found": 2}

        prs = s.exec(select(PipelineRun).where(PipelineRun.run_id == run_id)).all()
        assert [p.name for p in prs] == ["a", "b"]
        assert all(p.status == PipelineStatus.OK for p in prs)


async def test_non_critical_failure_is_isolated():
    orch = Orchestrator([BoomPipeline(), RecordingPipeline("after", found=1)])
    run_id = await orch.execute()

    with Session(get_engine()) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.COMPLETED  # run still completes
        assert run.errors and run.errors[0]["pipeline"] == "boom"
        names = [p.name for p in s.exec(select(PipelineRun)).all()]
        assert names == ["boom", "after"]  # later pipeline still ran


async def test_critical_failure_aborts_the_run():
    orch = Orchestrator([CriticalBoomPipeline(), RecordingPipeline("never", found=9)])
    run_id = await orch.execute()

    with Session(get_engine()) as s:
        run = s.get(Run, run_id)
        assert run.status == RunStatus.FAILED
        names = [p.name for p in s.exec(select(PipelineRun)).all()]
        assert names == ["critical-boom"]  # aborted before "never"


async def test_collected_errors_downgrade_status_to_partial():
    orch = Orchestrator([PartialPipeline()])
    await orch.execute()
    with Session(get_engine()) as s:
        pr = s.exec(select(PipelineRun)).one()
        assert pr.status == PipelineStatus.PARTIAL
        assert pr.errors[0]["scope"] == "item:1"


def test_duplicate_pipeline_names_rejected():
    with pytest.raises(ValueError, match="Duplicate"):
        Orchestrator([RecordingPipeline("dup"), RecordingPipeline("dup")])
