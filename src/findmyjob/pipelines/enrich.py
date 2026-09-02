"""``enrich`` — fill in thin job descriptions from the posting page.

Runs after ``normalize``. For active jobs whose ``jd_text`` is missing or short,
fetch the posting URL (robots-aware, rate-limited), extract the main content and
merge any ``JobPosting`` JSON-LD. Dead links are marked ``lifecycle=dead``.
No LLM.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from sqlalchemy import func, or_
from sqlmodel import col, select

from findmyjob.models.enums import JobLifecycle
from findmyjob.models.job import Job
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.enrich import enrich_url
from findmyjob.services.http import HttpClient
from findmyjob.services.jobs import content_hash
from findmyjob.sources.robots import RobotsCache

_MIN_CHARS = 400
_MAX_PER_RUN = 200


class EnrichPipeline(Pipeline):
    name: ClassVar[str] = "enrich"

    def __init__(self, http_factory: Callable[[], HttpClient] | None = None) -> None:
        self._http_factory = http_factory or HttpClient

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()

        with ctx.session() as session:
            rows = session.exec(
                select(Job.id, Job.url)
                .where(
                    col(Job.lifecycle) == JobLifecycle.ACTIVE,
                    or_(
                        col(Job.jd_text).is_(None),
                        func.length(col(Job.jd_text)) < _MIN_CHARS,
                    ),
                    col(Job.url) != "",
                )
                .order_by(col(Job.id))
                .limit(_MAX_PER_RUN)
            ).all()

        targets: list[tuple[int, str]] = [(r[0], r[1]) for r in rows if r[0] is not None and r[1]]
        if not targets:
            return res

        async with self._http_factory() as http:
            robots = RobotsCache(http)
            for job_id, url in targets:
                try:
                    outcome = await enrich_url(http, robots, url)
                except Exception as exc:  # contain per-job failure
                    res.add_error(f"job:{job_id}", exc)
                    continue

                if outcome.robots_blocked:
                    res.bump("robots_blocked")
                    continue
                if outcome.fetched:
                    res.bump("fetched")

                with ctx.session() as session:
                    job = session.get(Job, job_id)
                    if job is None:
                        continue
                    if outcome.dead:
                        job.lifecycle = JobLifecycle.DEAD
                        res.bump("dead")
                    elif outcome.text and len(outcome.text) > len(job.jd_text or ""):
                        job.jd_text = outcome.text
                        job.jd_content_hash = content_hash(outcome.text)
                        res.bump("enriched")
                    session.add(job)

        res.finalize_status()
        return res
