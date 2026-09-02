"""Document upload / listing / download / delete."""

from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter, Depends, File, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse
from sqlmodel import Session

from findmyjob.db import get_session
from findmyjob.models.enums import DocumentType
from findmyjob.schemas.document import DocumentRead
from findmyjob.services.documents import (
    DocumentValidationError,
    delete_document,
    get_document,
    list_documents,
    save_document,
)

router = APIRouter(prefix="/documents", tags=["documents"])


@router.get("", response_model=list[DocumentRead])
def get_documents(session: Session = Depends(get_session)) -> list[DocumentRead]:
    return [DocumentRead.of(d) for d in list_documents(session)]


@router.post("", response_model=DocumentRead, status_code=201)
async def upload_document(
    type: DocumentType = Form(...),
    file: UploadFile = File(...),
    session: Session = Depends(get_session),
) -> DocumentRead:
    content = await file.read()
    try:
        doc = save_document(
            session,
            doc_type=type,
            filename=file.filename or "upload",
            content=content,
        )
    except DocumentValidationError as exc:
        raise HTTPException(status_code=422, detail=str(exc)) from exc
    session.commit()
    session.refresh(doc)
    return DocumentRead.of(doc)


@router.get("/{document_id}/file")
def download_document(document_id: int, session: Session = Depends(get_session)) -> FileResponse:
    doc = get_document(session, document_id)
    if doc is None:
        raise HTTPException(status_code=404, detail="Document not found")
    path = Path(doc.stored_path)
    if not path.exists():
        raise HTTPException(status_code=410, detail="Stored file is missing")
    return FileResponse(path, media_type=doc.mime, filename=doc.filename)


@router.delete("/{document_id}", status_code=204)
def remove_document(document_id: int, session: Session = Depends(get_session)) -> None:
    if not delete_document(session, document_id):
        raise HTTPException(status_code=404, detail="Document not found")
    session.commit()
