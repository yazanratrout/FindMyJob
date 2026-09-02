"""Settings, keyword suggestions and semester terms."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from findmyjob.db import get_session
from findmyjob.llm.client import LlmError
from findmyjob.llm.keyword_suggest import KeywordSuggestions, suggest_keywords
from findmyjob.models.profile import ProfileSkill
from findmyjob.schemas.settings import (
    KeywordSuggestRequest,
    SemesterTermCreate,
    SemesterTermRead,
    SettingsRead,
    SettingsUpdate,
    settings_read,
    term_read,
)
from findmyjob.services.profile import get_profile
from findmyjob.services.semester import add_term, delete_term, list_terms
from findmyjob.services.settings import get_app_settings, update_app_settings

router = APIRouter(tags=["settings"])


@router.get("/settings", response_model=SettingsRead)
def read_settings(session: Session = Depends(get_session)) -> SettingsRead:
    return settings_read(get_app_settings(session))


@router.put("/settings", response_model=SettingsRead)
def write_settings(patch: SettingsUpdate, session: Session = Depends(get_session)) -> SettingsRead:
    try:
        row = update_app_settings(session, patch.model_dump(exclude_unset=True))
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return settings_read(row)


@router.post("/settings/suggest-keywords", response_model=KeywordSuggestions)
def keyword_suggestions(
    body: KeywordSuggestRequest, session: Session = Depends(get_session)
) -> KeywordSuggestions:
    profile = get_profile(session)
    skills = [
        s.name
        for s in session.exec(
            select(ProfileSkill).where(col(ProfileSkill.profile_id) == profile.id)
        ).all()
    ]
    settings = get_app_settings(session)
    try:
        suggestions, _ = suggest_keywords(
            target_fields=body.target_fields or settings.target_fields,
            target_titles=body.target_titles or settings.target_titles,
            skills=skills,
        )
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.commit()
    return suggestions


@router.get("/semester-terms", response_model=list[SemesterTermRead])
def get_terms(session: Session = Depends(get_session)) -> list[SemesterTermRead]:
    return [term_read(t) for t in list_terms(session)]


@router.post("/semester-terms", response_model=SemesterTermRead, status_code=201)
def create_term(
    body: SemesterTermCreate, session: Session = Depends(get_session)
) -> SemesterTermRead:
    try:
        term = add_term(
            session,
            label=body.label,
            lecture_start=body.lecture_start,
            lecture_end=body.lecture_end,
        )
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return term_read(term)


@router.delete("/semester-terms/{term_id}", status_code=204)
def remove_term(term_id: int, session: Session = Depends(get_session)) -> None:
    if not delete_term(session, term_id):
        raise HTTPException(status_code=404, detail="Term not found")
    session.commit()
