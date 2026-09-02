"""In-app run digests (replaces external notifications)."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Query
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.schemas.digest import DigestRead
from findmyjob.services.digest import (
    get_digest_with_run,
    list_digests,
    mark_all_seen,
    mark_seen,
    unseen_count,
)

router = APIRouter(prefix="/digests", tags=["digests"])


@router.get("", response_model=list[DigestRead])
def get_digests(
    limit: int = Query(20, ge=1, le=100), session: Session = Depends(get_session)
) -> list[DigestRead]:
    return [DigestRead.of(d, run) for d, run in list_digests(session, limit=limit)]


@router.get("/unseen-count")
def get_unseen_count(session: Session = Depends(get_session)) -> dict[str, int]:
    return {"count": unseen_count(session)}


@router.post("/seen", status_code=204)
def mark_everything_seen(session: Session = Depends(get_session)) -> None:
    mark_all_seen(session)
    session.commit()


@router.post("/{digest_id}/seen", response_model=DigestRead)
def mark_one_seen(digest_id: int, session: Session = Depends(get_session)) -> DigestRead:
    if mark_seen(session, digest_id) is None:
        raise HTTPException(status_code=404, detail="digest not found")
    session.commit()
    pair = get_digest_with_run(session, digest_id)
    assert pair is not None
    return DigestRead.of(*pair)
