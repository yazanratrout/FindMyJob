"""Pipeline framework and the concrete stages of the daily job."""

from __future__ import annotations

from findmyjob.pipelines.base import Pipeline, PipelineError, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.pipelines.orchestrator import Orchestrator
from findmyjob.pipelines.registry import build_default_orchestrator, default_pipelines

__all__ = [
    "Orchestrator",
    "Pipeline",
    "PipelineContext",
    "PipelineError",
    "PipelineResult",
    "build_default_orchestrator",
    "default_pipelines",
]
