"""Cover-letter generation, editing and .docx download."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from fastapi.responses import FileResponse
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.llm.client import LlmError
from findmyjob.schemas.cover_letter import (
    CoverLetterRead,
    CoverLetterUpdate,
    RegenerateRequest,
)
from findmyjob.services.cover_letters import (
    CoverLetterError,
    generate,
    get,
    list_for_job,
    regenerate,
    update,
)

router = APIRouter(tags=["cover-letters"])

_DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"


@router.get("/jobs/{job_id}/cover-letters", response_model=list[CoverLetterRead])
def list_job_cover_letters(
    job_id: int, session: Session = Depends(get_session)
) -> list[CoverLetterRead]:
    return [CoverLetterRead.of(c) for c in list_for_job(session, job_id)]


@router.post("/jobs/{job_id}/cover-letter", response_model=CoverLetterRead, status_code=201)
def create_cover_letter(job_id: int, session: Session = Depends(get_session)) -> CoverLetterRead:
    try:
        cover_letter = generate(session, job_id)
    except CoverLetterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.commit()
    return CoverLetterRead.of(cover_letter)


@router.put("/cover-letters/{cover_letter_id}", response_model=CoverLetterRead)
def edit_cover_letter(
    cover_letter_id: int,
    body: CoverLetterUpdate,
    session: Session = Depends(get_session),
) -> CoverLetterRead:
    try:
        cover_letter = update(session, cover_letter_id, body.content)
    except CoverLetterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except ValueError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    return CoverLetterRead.of(cover_letter)


@router.post("/cover-letters/{cover_letter_id}/regenerate", response_model=CoverLetterRead)
def regenerate_cover_letter(
    cover_letter_id: int,
    body: RegenerateRequest,
    session: Session = Depends(get_session),
) -> CoverLetterRead:
    try:
        cover_letter = regenerate(session, cover_letter_id, body.instruction)
    except CoverLetterError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc
    except LlmError as exc:
        raise HTTPException(status_code=502, detail=str(exc)) from exc
    session.commit()
    return CoverLetterRead.of(cover_letter)


@router.get("/cover-letters/{cover_letter_id}/docx")
def download_cover_letter(
    cover_letter_id: int, session: Session = Depends(get_session)
) -> FileResponse:
    cover_letter = get(session, cover_letter_id)
    if cover_letter is None or not cover_letter.docx_path:
        raise HTTPException(status_code=404, detail="cover letter not found")
    path = Path(cover_letter.docx_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="file missing")
    return FileResponse(path, media_type=_DOCX_MIME, filename=path.name)
