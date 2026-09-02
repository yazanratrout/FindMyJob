"""Persisting raw postings into the ``job`` table."""

from __future__ import annotations

import hashlib

from sqlmodel import Session, col, select

from findmyjob.models.base import utcnow
from findmyjob.models.job import Job
from findmyjob.normalize import normalize_title
from findmyjob.sources.base import RawJob


def content_hash(text: str) -> str:
    return hashlib.sha256(text.strip().lower().encode("utf-8")).hexdigest()


def _best_text(raw: RawJob) -> str | None:
    if raw.description_text and len(raw.description_text.strip()) >= 40:
        return raw.description_text.strip()
    if raw.description_html:
        from findmyjob.sources._parsing import html_to_text

        text = html_to_text(raw.description_html)
        return text or None
    return raw.description_text or None


def store_raw_job(session: Session, raw: RawJob, *, run_id: int) -> tuple[Job, bool]:
    """Insert or refresh a job by ``(source_key, source_job_id)``.

    Returns ``(job, created)``. Idempotent: a second call only bumps
    ``last_seen_at``.
    """
    existing = session.exec(
        select(Job).where(
            col(Job.source_key) == raw.source_key,
            col(Job.source_job_id) == raw.source_job_id,
        )
    ).first()

    jd_text = _best_text(raw)
    if existing is not None:
        existing.last_seen_at = utcnow()
        if jd_text and not existing.jd_text:
            existing.jd_text = jd_text
            existing.jd_content_hash = content_hash(jd_text)
        session.add(existing)
        return existing, False

    job = Job(
        source_key=raw.source_key,
        source_job_id=raw.source_job_id,
        url=raw.url,
        apply_url=raw.apply_url,
        title=raw.title,
        normalized_title=normalize_title(raw.title),
        company_name_raw=raw.company_name,
        location_raw=raw.location,
        is_remote=raw.is_remote,
        posted_at=raw.posted_at,
        first_seen_run_id=run_id,
        last_seen_at=utcnow(),
        raw_json=raw.model_dump(mode="json"),
        jd_text=jd_text,
        jd_content_hash=content_hash(jd_text) if jd_text else None,
        salary_raw=raw.salary_raw,
    )
    session.add(job)
    session.flush()
    return job, True
