"""List job sources and toggle them on/off.

Toggling writes ``AppSettings.sources_enabled`` - the same field the onboarding
wizard and Settings page edit - so there is one source of truth.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel
from sqlmodel import Session

from findmyjob.config import get_settings
from findmyjob.db import get_session
from findmyjob.services.settings import get_app_settings, update_app_settings
from findmyjob.sources.registry import source_catalog

router = APIRouter(prefix="/sources", tags=["sources"])


class SourceInfo(BaseModel):
    key: str
    display_name: str
    enabled: bool
    configured: bool
    requires_secrets: list[str]


class SourceToggle(BaseModel):
    enabled: bool


@router.get("", response_model=list[SourceInfo])
def list_sources(session: Session = Depends(get_session)) -> list[SourceInfo]:
    catalog = source_catalog(get_settings(), get_app_settings(session))
    return [SourceInfo(**entry) for entry in catalog]


@router.put("/{key}", response_model=list[SourceInfo])
def toggle_source(
    key: str, body: SourceToggle, session: Session = Depends(get_session)
) -> list[SourceInfo]:
    settings = get_app_settings(session)
    if key not in settings.sources_enabled:
        raise HTTPException(status_code=404, detail=f"unknown source {key!r}")
    enabled = dict(settings.sources_enabled)
    enabled[key] = body.enabled
    update_app_settings(session, {"sources_enabled": enabled})
    session.commit()
    catalog = source_catalog(get_settings(), get_app_settings(session))
    return [SourceInfo(**entry) for entry in catalog]
