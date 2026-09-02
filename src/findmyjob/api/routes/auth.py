"""Passphrase setup / login / logout."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Request
from pydantic import BaseModel, Field
from sqlmodel import Session

from findmyjob.api.deps import is_authenticated, login_session, logout_session
from findmyjob.db import get_session
from findmyjob.services.auth import (
    AuthError,
    is_configured,
    set_passphrase,
    verify_passphrase,
)

router = APIRouter(prefix="/auth", tags=["auth"])


class PassphraseBody(BaseModel):
    passphrase: str = Field(min_length=1)


class AuthStatus(BaseModel):
    configured: bool
    authenticated: bool


@router.get("/status", response_model=AuthStatus)
def auth_status(request: Request, session: Session = Depends(get_session)) -> AuthStatus:
    return AuthStatus(configured=is_configured(session), authenticated=is_authenticated(request))


@router.post("/setup", response_model=AuthStatus, status_code=201)
def setup(
    body: PassphraseBody, request: Request, session: Session = Depends(get_session)
) -> AuthStatus:
    if is_configured(session):
        raise HTTPException(status_code=409, detail="passphrase already set")
    try:
        set_passphrase(session, body.passphrase)
    except AuthError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    login_session(request)
    return AuthStatus(configured=True, authenticated=True)


@router.post("/login", response_model=AuthStatus)
def login(
    body: PassphraseBody, request: Request, session: Session = Depends(get_session)
) -> AuthStatus:
    if not is_configured(session):
        raise HTTPException(status_code=409, detail="no passphrase set; call /auth/setup")
    if not verify_passphrase(session, body.passphrase):
        raise HTTPException(status_code=401, detail="wrong passphrase")
    session.commit()
    login_session(request)
    return AuthStatus(configured=True, authenticated=True)


@router.post("/logout", status_code=204)
def logout(request: Request) -> None:
    logout_session(request)
