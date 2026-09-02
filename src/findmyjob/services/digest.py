"""Build and read the per-run digest surfaced in the web UI."""

from __future__ import annotations

from sqlalchemy import func
from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.digest import Digest
from findmyjob.models.enums import Decision, JobLifecycle
from findmyjob.models.job import Job, JobScore
from findmyjob.models.run import Run
from findmyjob.services.applications import follow_ups_due
from findmyjob.services.settings import get_app_settings

log = get_logger("digest")


def build_digest(session: Session, run_id: int) -> Digest:
    """Compose (or replace) the digest for a completed run."""
    run = session.get(Run, run_id)
    top_n = get_app_settings(session).digest_top_n

    scores = session.exec(
        select(JobScore, Job)
        .join(Job, col(JobScore.job_id) == col(Job.id))
        .where(
            col(JobScore.run_id) == run_id,
            col(Job.canonical_job_id).is_(None),
            col(Job.lifecycle) == JobLifecycle.ACTIVE,
        )
    ).all()

    by_decision = dict.fromkeys(Decision, 0)
    recommended: list[tuple[JobScore, Job]] = []
    for score, job in scores:
        by_decision[score.decision] = by_decision.get(score.decision, 0) + 1
        if score.decision == Decision.RECOMMENDED:
            recommended.append((score, job))
    recommended.sort(key=lambda pair: pair[0].final_score, reverse=True)

    new_jobs = session.exec(
        select(func.count()).select_from(Job).where(col(Job.first_seen_run_id) == run_id)
    ).one()

    warnings: list[str] = []
    if run is not None:
        if run.budget_exhausted:
            warnings.append("Monthly LLM budget hit — some jobs were not analyzed.")
        for err in run.errors[:5]:
            warnings.append(f"{err.get('pipeline', '?')}: {err.get('message', '')[:120]}")

    items = [
        {
            "job_id": job.id,
            "title": job.title,
            "company": job.company_name_raw or "unknown",
            "final_score": round(score.final_score, 1),
            "decision": score.decision.value,
            "is_new": job.first_seen_run_id == run_id,
        }
        for score, job in recommended[:top_n]
    ]

    summary = {
        "new_jobs": int(new_jobs),
        "recommended": by_decision.get(Decision.RECOMMENDED, 0),
        "maybe": by_decision.get(Decision.MAYBE, 0),
        "archived": by_decision.get(Decision.ARCHIVED, 0),
        "follow_ups_due": len(follow_ups_due(session)),
        "errors": len(run.errors) if run is not None else 0,
        "budget_exhausted": bool(run and run.budget_exhausted),
    }

    existing = session.exec(select(Digest).where(col(Digest.run_id) == run_id)).first()
    digest = existing or Digest(run_id=run_id)
    digest.summary = summary
    digest.items = items
    digest.warnings = warnings
    session.add(digest)
    session.flush()
    log.info("digest.built", run_id=run_id, **summary)
    return digest


def list_digests(session: Session, limit: int = 20) -> list[tuple[Digest, Run]]:
    return list(
        session.exec(
            select(Digest, Run)
            .join(Run, col(Digest.run_id) == col(Run.id))
            .order_by(col(Digest.id).desc())
            .limit(limit)
        ).all()
    )


def get_digest_with_run(session: Session, digest_id: int) -> tuple[Digest, Run] | None:
    digest = session.get(Digest, digest_id)
    if digest is None:
        return None
    run = session.get(Run, digest.run_id)
    assert run is not None
    return digest, run


def unseen_count(session: Session) -> int:
    return int(
        session.exec(
            select(func.count()).select_from(Digest).where(col(Digest.seen).is_(False))
        ).one()
    )


def mark_seen(session: Session, digest_id: int) -> Digest | None:
    digest = session.get(Digest, digest_id)
    if digest is None:
        return None
    digest.seen = True
    session.add(digest)
    session.flush()
    return digest


def mark_all_seen(session: Session) -> int:
    rows = session.exec(select(Digest).where(col(Digest.seen).is_(False))).all()
    for row in rows:
        row.seen = True
        session.add(row)
    session.flush()
    return len(rows)
