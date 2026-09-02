"""``notify`` — build the in-app digest for this run. No external notifications.

Runs last. Non-critical: a digest failure never affects the pipeline outcome.
"""

from __future__ import annotations

from typing import ClassVar

from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.digest import build_digest


class NotifyPipeline(Pipeline):
    name: ClassVar[str] = "notify"

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        with ctx.session() as session:
            digest = build_digest(session, ctx.run_id)
            res.stats["recommended"] = digest.summary.get("recommended", 0)
            res.stats["new_jobs"] = digest.summary.get("new_jobs", 0)
        return res
