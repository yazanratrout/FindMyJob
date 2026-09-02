"""Liveness / readiness endpoint."""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import text
from sqlmodel import Session

from findmyjob import __version__
from findmyjob.db import get_session

router = APIRouter(tags=["meta"])


@router.get("/health")
def health(session: Session = Depends(get_session)) -> dict[str, object]:
    try:
        session.exec(text("SELECT 1"))  # type: ignore[call-overload]
        db_ok = True
    except Exception:
        db_ok = False
    return {
        "status": "ok" if db_ok else "degraded",
        "version": __version__,
        "db_ok": db_ok,
    }
