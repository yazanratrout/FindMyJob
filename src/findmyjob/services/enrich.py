"""Fetch a job posting page and extract its full description."""

from __future__ import annotations

import asyncio
from dataclasses import dataclass

import httpx
import trafilatura

from findmyjob.services.http import HttpClient
from findmyjob.sources._parsing import html_to_text, parse_datetime
from findmyjob.sources.jsonld import extract_job_postings
from findmyjob.sources.robots import RobotsCache

_DEAD_STATUS = {403, 404, 410}


@dataclass(slots=True)
class EnrichOutcome:
    text: str | None = None
    posted_at_hint: str | None = None
    salary_hint: str | None = None
    dead: bool = False
    robots_blocked: bool = False
    fetched: bool = False


def _extract_main_text(html: str) -> str:
    extracted = trafilatura.extract(
        html, include_comments=False, include_tables=True, favor_recall=True
    )
    return (extracted or "").strip()


async def enrich_url(http: HttpClient, robots: RobotsCache, url: str) -> EnrichOutcome:
    if not url:
        return EnrichOutcome()
    if not await robots.allowed(url):
        return EnrichOutcome(robots_blocked=True)

    try:
        html = await http.get_text(url)
    except httpx.HTTPStatusError as exc:
        return EnrichOutcome(dead=exc.response.status_code in _DEAD_STATUS)
    except httpx.HTTPError:
        return EnrichOutcome()

    main_text = await asyncio.to_thread(_extract_main_text, html)

    jsonld_text = ""
    posted_hint = salary_hint = None
    postings = extract_job_postings(html)
    if postings:
        posting = postings[0]
        jsonld_text = html_to_text(posting.get("description"))
        if parse_datetime(posting.get("datePosted")):
            posted_hint = str(posting.get("datePosted"))
        base_salary = posting.get("baseSalary")
        if isinstance(base_salary, dict):
            value = base_salary.get("value")
            if isinstance(value, dict):
                salary_hint = (
                    " ".join(
                        str(value.get(k))
                        for k in ("minValue", "maxValue", "unitText")
                        if value.get(k) is not None
                    )
                    or None
                )

    best = max((main_text, jsonld_text), key=len)
    return EnrichOutcome(
        text=best or None,
        posted_at_hint=posted_hint,
        salary_hint=salary_hint,
        dead=False,
        fetched=True,
    )
