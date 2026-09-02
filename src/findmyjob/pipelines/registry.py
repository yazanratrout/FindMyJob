"""Wiring: the ordered list of pipelines the orchestrator runs.

Add a pipeline here (in the right position) as each checkpoint lands. Nothing
else needs to change — the orchestrator picks up whatever this returns.
"""

from __future__ import annotations

from findmyjob.pipelines.analyze import AnalyzePipeline
from findmyjob.pipelines.base import Pipeline
from findmyjob.pipelines.decide import DecidePipeline
from findmyjob.pipelines.dedup import DedupPipeline
from findmyjob.pipelines.enrich import EnrichPipeline
from findmyjob.pipelines.fetch import FetchPipeline
from findmyjob.pipelines.judge import JudgePipeline
from findmyjob.pipelines.normalize import NormalizePipeline
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.prefilter import PrefilterPipeline
from findmyjob.pipelines.score import ScorePipeline


def default_pipelines(*, fetch_only: bool = False, no_llm: bool = False) -> list[Pipeline]:
    """The daily sequence, in execution order.

    * ``fetch_only`` — just ingest, skip everything downstream.
    * ``no_llm`` — run the deterministic stages only (no ``analyze`` / ``judge``);
      ``score`` still runs on whatever analyses already exist.
    """
    pipelines: list[Pipeline] = [
        FetchPipeline(),
        NormalizePipeline(),
        EnrichPipeline(),
        DedupPipeline(),
        PrefilterPipeline(),
        AnalyzePipeline(),
        ScorePipeline(),
        JudgePipeline(),
        DecidePipeline(),
    ]
    if fetch_only:
        return [pipelines[0]]
    if no_llm:
        llm_stages = {"analyze", "judge"}
        return [p for p in pipelines if p.name not in llm_stages]
    return pipelines


def build_default_orchestrator(*, fetch_only: bool = False, no_llm: bool = False) -> Orchestrator:
    return Orchestrator(default_pipelines(fetch_only=fetch_only, no_llm=no_llm))
