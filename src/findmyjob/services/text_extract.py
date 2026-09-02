"""Plain-text extraction from uploaded documents.

Supported without an LLM: PDF (``pdfplumber``), DOCX (``python-docx``), and
plain text. Image-only PDFs / scans have no text layer to read; they are stored
with ``parse_status = pending`` and an empty ``extracted_text``. A Claude-vision
OCR fallback for those is a planned enhancement, not part of v1 - the profile
parser still runs on whatever other documents provide text.
"""

from __future__ import annotations

from pathlib import Path

MIME_BY_SUFFIX: dict[str, str] = {
    ".pdf": "application/pdf",
    ".docx": "application/vnd.openxmlformats-officedocument.wordprocessingml.document",
    ".txt": "text/plain",
    ".md": "text/plain",
    ".png": "image/png",
    ".jpg": "image/jpeg",
    ".jpeg": "image/jpeg",
}

TEXT_MIMES = {"text/plain"}
PDF_MIME = "application/pdf"
DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
IMAGE_MIMES = {"image/png", "image/jpeg"}


class UnsupportedDocument(ValueError):
    """Raised when a document's type cannot be handled at all."""


def _extract_pdf(path: Path) -> str:
    import pdfplumber

    parts: list[str] = []
    with pdfplumber.open(path) as pdf:
        for page in pdf.pages:
            parts.append(page.extract_text() or "")
    return "\n\n".join(p.strip() for p in parts if p.strip())


def _extract_docx(path: Path) -> str:
    from docx import Document as DocxDocument

    doc = DocxDocument(str(path))
    lines = [p.text for p in doc.paragraphs]
    for table in doc.tables:
        for row in table.rows:
            lines.append(" | ".join(cell.text for cell in row.cells))
    return "\n".join(line for line in lines if line.strip())


def extract_text(path: Path, mime: str) -> str:
    """Best-effort text layer. Returns ``""`` for images (handled later by the LLM)."""
    if mime in TEXT_MIMES:
        return path.read_text("utf-8", errors="replace").strip()
    if mime == PDF_MIME:
        return _extract_pdf(path)
    if mime == DOCX_MIME:
        return _extract_docx(path)
    if mime in IMAGE_MIMES:
        return ""
    raise UnsupportedDocument(f"Cannot extract text from mime {mime!r}")
