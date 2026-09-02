"""Wiring: the ordered list of pipelines the orchestrator runs.

Add a pipeline here (in the right position) as each checkpoint lands. Nothing
else needs to change — the orchestrator picks up whatever this returns.
"""

from __future__ import annotations

from findmyjob.pipelines.base import Pipeline
from findmyjob.pipelines.enrich import EnrichPipeline
from findmyjob.pipelines.fetch import FetchPipeline
from findmyjob.pipelines.normalize import NormalizePipeline
from findmyjob.pipelines.orchestrator import Orchestrator


def default_pipelines() -> list[Pipeline]:
    """The daily sequence, in execution order.

    Target sequence (checkpoint that adds it):
        fetch (CP5) -> normalize (CP7) -> enrich (CP7) -> dedup (CP8)
        -> prefilter (CP10) -> analyze (CP9) -> score (CP10) -> judge (CP11)
        -> decide (CP11) -> notify (CP21)
    """
    return [
        FetchPipeline(),
        NormalizePipeline(),
        EnrichPipeline(),
    ]


def build_default_orchestrator() -> Orchestrator:
    return Orchestrator(default_pipelines())
