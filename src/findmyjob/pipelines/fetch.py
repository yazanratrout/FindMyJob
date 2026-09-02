"""``fetch`` — query every active job source and persist new postings.

Critical: if this fails entirely there is nothing for the rest of the run to do.
A single source failing is contained (recorded, other sources continue).
"""

from __future__ import annotations

from collections.abc import Callable
from typing import ClassVar

from findmyjob.config import get_settings
from findmyjob.pipelines.base import Pipeline, PipelineResult
from findmyjob.pipelines.context import PipelineContext
from findmyjob.services.companies import company_refs
from findmyjob.services.http import HttpClient
from findmyjob.services.jobs import store_raw_job
from findmyjob.sources.registry import build_source_query, build_sources


class FetchPipeline(Pipeline):
    name: ClassVar[str] = "fetch"
    critical: ClassVar[bool] = True

    def __init__(self, http_factory: Callable[[], HttpClient] | None = None) -> None:
        self._http_factory = http_factory or HttpClient

    async def run(self, ctx: PipelineContext) -> PipelineResult:
        res = self.result()
        query = build_source_query(ctx.app_settings)
        log = ctx.bind(pipeline=self.name)

        with ctx.session() as session:
            companies = company_refs(session)

        async with self._http_factory() as http:
            sources = build_sources(get_settings(), ctx.app_settings, http, companies)
            res.stats["sources_active"] = len(sources)
            if not sources:
                log.warning("fetch.no_sources")
                return res

            for source in sources:
                try:
                    raw_jobs = await source.fetch(query)
                except Exception as exc:  # contain per-source failure
                    log.warning("fetch.source_failed", source=source.key, error=str(exc))
                    res.add_error(f"source:{source.key}", exc)
                    continue

                res.stats[f"found.{source.key}"] = len(raw_jobs)
                created = 0
                with ctx.session() as session:
                    for raw in raw_jobs:
                        try:
                            _, is_new = store_raw_job(session, raw, run_id=ctx.run_id)
                            created += int(is_new)
                        except Exception as exc:  # one bad posting must not stop the source
                            res.add_error(f"job:{source.key}:{raw.source_job_id}", exc)
                res.bump("found", len(raw_jobs))
                res.bump("new", created)
                log.info("fetch.source_done", source=source.key, found=len(raw_jobs), new=created)

        res.finalize_status()
        return res
