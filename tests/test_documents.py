import io

import pytest
from docx import Document as DocxDocument
from sqlmodel import Session

from findmyjob.models.enums import DocumentType, ParseStatus
from findmyjob.services.documents import (
    DocumentValidationError,
    delete_document,
    list_documents,
    save_document,
)
from findmyjob.services.profile import get_profile

pytestmark = pytest.mark.usefixtures("seeded_session")


def _docx_bytes(text: str) -> bytes:
    doc = DocxDocument()
    for line in text.splitlines():
        doc.add_paragraph(line)
    buf = io.BytesIO()
    doc.save(buf)
    return buf.getvalue()


def test_save_txt_document_extracts_text(db_session: Session):
    doc = save_document(
        db_session,
        doc_type=DocumentType.REFERENCE,
        filename="ref.txt",
        content=b"Strong analytical skills. Reliable.",
    )
    db_session.commit()
    assert doc.parse_status == ParseStatus.DONE
    assert "analytical" in (doc.extracted_text or "")


def test_save_docx_cv_links_profile(db_session: Session):
    doc = save_document(
        db_session,
        doc_type=DocumentType.CV,
        filename="cv.docx",
        content=_docx_bytes("Yazan\nPython, SQL, Data Science\nTU München"),
    )
    db_session.commit()
    assert doc.parse_status == ParseStatus.DONE
    assert "Data Science" in (doc.extracted_text or "")
    assert get_profile(db_session).cv_document_id == doc.id


def test_reject_unknown_extension(db_session: Session):
    with pytest.raises(DocumentValidationError, match="Unsupported"):
        save_document(db_session, doc_type=DocumentType.OTHER, filename="x.exe", content=b"MZ")


def test_reject_oversized_file(db_session: Session):
    with pytest.raises(DocumentValidationError, match="limit"):
        save_document(
            db_session,
            doc_type=DocumentType.OTHER,
            filename="big.txt",
            content=b"x" * (15 * 1024 * 1024 + 1),
        )


def test_image_upload_is_stored_but_pending_extraction(db_session: Session):
    doc = save_document(
        db_session, doc_type=DocumentType.TRANSCRIPT, filename="scan.png", content=b"\x89PNG\r\n"
    )
    db_session.commit()
    assert doc.parse_status == ParseStatus.PENDING
    assert doc.extracted_text is None


def test_delete_removes_row_and_file(db_session: Session):
    doc = save_document(db_session, doc_type=DocumentType.OTHER, filename="n.txt", content=b"hello")
    db_session.commit()
    from pathlib import Path

    path = Path(doc.stored_path)
    assert path.exists()
    assert delete_document(db_session, doc.id) is True
    db_session.commit()
    assert not path.exists()
    assert list_documents(db_session) == []


def test_upload_endpoint_roundtrip(client):
    resp = client.post(
        "/api/documents",
        data={"type": "cv"},
        files={"file": ("cv.txt", b"Data analyst, Python, Munich", "text/plain")},
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["type"] == "cv"
    assert body["text_chars"] > 0

    listed = client.get("/api/documents").json()
    assert len(listed) == 1

    dl = client.get(f"/api/documents/{body['id']}/file")
    assert dl.status_code == 200
    assert dl.content == b"Data analyst, Python, Munich"

    assert client.delete(f"/api/documents/{body['id']}").status_code == 204
    assert client.get("/api/documents").json() == []


def test_upload_endpoint_rejects_bad_type(client):
    resp = client.post(
        "/api/documents",
        data={"type": "cv"},
        files={"file": ("a.exe", b"nope", "application/octet-stream")},
    )
    assert resp.status_code == 422
