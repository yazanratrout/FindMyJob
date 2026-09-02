"""Shared FastAPI dependencies."""

from __future__ import annotations

from fastapi import HTTPException, Request

_SESSION_KEY = "authed"


def is_authenticated(request: Request) -> bool:
    return bool(request.session.get(_SESSION_KEY))


def login_session(request: Request) -> None:
    request.session[_SESSION_KEY] = True


def logout_session(request: Request) -> None:
    request.session.pop(_SESSION_KEY, None)


def require_auth(request: Request) -> None:
    """Router dependency: 401 unless the session is authenticated."""
    if not is_authenticated(request):
        raise HTTPException(status_code=401, detail="not authenticated")
