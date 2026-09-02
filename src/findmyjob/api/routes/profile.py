"""Profile: read, edit, parse from documents, manage skills."""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, col, select

from findmyjob.db import get_session
from findmyjob.llm.client import LlmError
from findmyjob.models.profile import ProfileSkill
from findmyjob.schemas.profile import (
    ParseResult,
    ProfileRead,
    ProfileUpdate,
    SkillRead,
    SkillWrite,
)
from findmyjob.services.profile import (
    get_profile,
    parse_and_apply,
    set_skills,
    update_profile,
)

router = APIRouter(prefix="/profile", tags=["profile"])


def _skills(session: Session, profile_id: int | None) -> list[ProfileSkill]:
    return list(
        session.exec(
            select(ProfileSkill)
            .where(col(ProfileSkill.profile_id) == profile_id)
            .order_by(col(ProfileSkill.category), col(ProfileSkill.name))
        ).all()
    )


@router.get("", response_model=ProfileRead)
def read_profile(session: Session = Depends(get_session)) -> ProfileRead:
    profile = get_profile(session)
    return ProfileRead.of(profile, _skills(session, profile.id))


@router.put("", response_model=ProfileRead)
def edit_profile(patch: ProfileUpdate, session: Session = Depends(get_session)) -> ProfileRead:
    profile = update_profile(session, patch.model_dump(exclude_unset=True))
    session.commit()
    return ProfileRead.of(profile, _skills(session, profile.id))


@router.post("/parse", response_model=ParseResult)
def parse_profile_from_documents(session: Session = Depends(get_session)) -> ParseResult:
    try:
        profile, result = parse_and_apply(session)
    except ValueError as exc:
        raise HTTPException(status_code=409, detail=str(exc)) from exc
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.commit()
    return ParseResult(
        profile=ProfileRead.of(profile, _skills(session, profile.id)),
        tokens_in=result.input_tokens,
        tokens_out=result.output_tokens,
        cost_eur=result.cost_eur,
        cache_hit=result.cache_hit,
    )


@router.put("/skills", response_model=list[SkillRead])
def replace_skills(
    skills: list[SkillWrite], session: Session = Depends(get_session)
) -> list[SkillRead]:
    rows = set_skills(session, [s.model_dump() for s in skills])
    session.commit()
    return [SkillRead.model_validate(r) for r in rows]
