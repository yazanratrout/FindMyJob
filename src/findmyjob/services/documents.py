"""Document storage: validate, persist to disk, extract a text layer."""

from __future__ import annotations

import uuid
from pathlib import Path

from sqlmodel import Session, col, select

from findmyjob.config import get_settings
from findmyjob.logging import get_logger
from findmyjob.models.enums import DocumentType, ParseStatus
from findmyjob.models.profile import Document
from findmyjob.services.profile import get_profile
from findmyjob.services.text_extract import MIME_BY_SUFFIX, extract_text

log = get_logger("documents")

MAX_BYTES = 15 * 1024 * 1024
ALLOWED_SUFFIXES = set(MIME_BY_SUFFIX)


class DocumentValidationError(ValueError):
    """Upload rejected before anything was written to disk."""


def _validate(filename: str, size: int) -> str:
    suffix = Path(filename).suffix.lower()
    if suffix not in ALLOWED_SUFFIXES:
        raise DocumentValidationError(
            f"Unsupported file type {suffix!r}. Allowed: {sorted(ALLOWED_SUFFIXES)}"
        )
    if size <= 0:
        raise DocumentValidationError("Empty file.")
    if size > MAX_BYTES:
        raise DocumentValidationError(f"File is {size} bytes; limit is {MAX_BYTES}.")
    return MIME_BY_SUFFIX[suffix]


def save_document(
    session: Session,
    *,
    doc_type: DocumentType,
    filename: str,
    content: bytes,
) -> Document:
    """Validate, store on disk under the profile's folder, and record the row."""
    mime = _validate(filename, len(content))
    profile = get_profile(session)
    assert profile.id is not None

    dest_dir = get_settings().documents_dir / str(profile.id)
    dest_dir.mkdir(parents=True, exist_ok=True)
    suffix = Path(filename).suffix.lower()
    stored_path = dest_dir / f"{uuid.uuid4().hex}{suffix}"
    stored_path.write_bytes(content)

    doc = Document(
        profile_id=profile.id,
        type=doc_type,
        filename=filename,
        stored_path=str(stored_path),
        mime=mime,
        size_bytes=len(content),
    )

    try:
        text = extract_text(stored_path, mime)
        doc.extracted_text = text or None
        doc.parse_status = ParseStatus.DONE if text else ParseStatus.PENDING
    except Exception as exc:  # never fail the upload over a bad text layer
        doc.parse_status = ParseStatus.FAILED
        doc.parse_error = str(exc)
        log.warning("documents.extract_failed", filename=filename, error=str(exc))

    session.add(doc)
    session.flush()
    if doc_type == DocumentType.CV:
        profile.cv_document_id = doc.id
        session.add(profile)
    log.info("documents.saved", id=doc.id, type=doc_type.value, bytes=len(content))
    return doc


def list_documents(session: Session) -> list[Document]:
    return list(session.exec(select(Document).order_by(col(Document.uploaded_at).desc())).all())


def get_document(session: Session, document_id: int) -> Document | None:
    return session.get(Document, document_id)


def delete_document(session: Session, document_id: int) -> bool:
    doc = session.get(Document, document_id)
    if doc is None:
        return False
    path = Path(doc.stored_path)
    if path.exists():
        path.unlink()
    profile = get_profile(session)
    if profile.cv_document_id == doc.id:
        profile.cv_document_id = None
        session.add(profile)
    session.delete(doc)
    log.info("documents.deleted", id=document_id)
    return True
