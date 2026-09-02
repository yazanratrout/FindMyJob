"""Pipeline contract.

A *pipeline* is one self-contained stage of the daily job. It reads what it
needs from the database (scoped to the current run where relevant), does its
work, writes its results back to the database, and returns a
:class:`PipelineResult`. Pipelines never import one another — the orchestrator
is the only thing that knows the full sequence.

Design rules for every concrete pipeline:

* Catch per-item errors internally and keep going; report them in
  ``PipelineResult.errors`` and return ``PARTIAL`` rather than raising.
* Only raise for conditions that make the whole stage meaningless.
* Be idempotent: running twice on the same data must not double-write.
* Do the cheap, deterministic work before anything that costs money.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from datetime import datetime
from typing import TYPE_CHECKING, ClassVar

from findmyjob.models.enums import PipelineStatus

if TYPE_CHECKING:
    from findmyjob.pipelines.context import PipelineContext


@dataclass(slots=True)
class PipelineError:
    """A single non-fatal problem encountered while running a pipeline."""

    scope: str  # e.g. "source:adzuna", "job:412"
    message: str
    exc_type: str | None = None

    def as_dict(self) -> dict[str, str | None]:
        return {"scope": self.scope, "message": self.message, "exc_type": self.exc_type}


@dataclass(slots=True)
class PipelineResult:
    name: str
    status: PipelineStatus
    stats: dict[str, int] = field(default_factory=dict)
    errors: list[PipelineError] = field(default_factory=list)
    duration_s: float = 0.0
    started_at: datetime | None = None
    finished_at: datetime | None = None

    @classmethod
    def skipped(cls, name: str, reason: str = "should_run() returned False") -> PipelineResult:
        return cls(
            name=name,
            status=PipelineStatus.SKIPPED,
            stats={},
            errors=[PipelineError(scope=name, message=reason)] if reason else [],
        )

    def add_error(self, scope: str, exc: Exception) -> None:
        self.errors.append(
            PipelineError(scope=scope, message=str(exc), exc_type=type(exc).__name__)
        )

    def bump(self, key: str, amount: int = 1) -> None:
        self.stats[key] = self.stats.get(key, 0) + amount

    def finalize_status(self) -> None:
        """Downgrade OK -> PARTIAL if errors were collected."""
        if self.status is PipelineStatus.OK and self.errors:
            self.status = PipelineStatus.PARTIAL


class Pipeline(ABC):
    """Base class for every processing stage."""

    #: Stable identifier, also used as the ``PipelineRun.name``.
    name: ClassVar[str]
    #: If True, a FAILED result aborts the whole run.
    critical: ClassVar[bool] = False

    def should_run(self, ctx: PipelineContext) -> bool:
        """Return False to skip this pipeline for the current run."""
        return True

    @abstractmethod
    async def run(self, ctx: PipelineContext) -> PipelineResult:
        """Execute the stage. Must not raise for recoverable per-item errors."""
        raise NotImplementedError

    def result(self, status: PipelineStatus = PipelineStatus.OK) -> PipelineResult:
        """Convenience factory for a result tied to this pipeline's name."""
        return PipelineResult(name=self.name, status=status)
