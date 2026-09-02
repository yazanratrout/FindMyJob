"""Render a cover letter into a DIN 5008-ish .docx via docxtpl.

The template is generated once (python-docx) into the data dir and cached; it is
plain paragraphs with Jinja tags, so it is safe to regenerate.
"""

from __future__ import annotations

from datetime import date
from pathlib import Path
from typing import Any

from findmyjob.config import get_settings
from findmyjob.llm.cover_letter import CoverLetterResult

_MONTHS_DE = [
    "Januar",
    "Februar",
    "März",
    "April",
    "Mai",
    "Juni",
    "Juli",
    "August",
    "September",
    "Oktober",
    "November",
    "Dezember",
]
_MONTHS_EN = [
    "January",
    "February",
    "March",
    "April",
    "May",
    "June",
    "July",
    "August",
    "September",
    "October",
    "November",
    "December",
]


def template_path() -> Path:
    return get_settings().data_dir / "cover_letter_template.docx"


def ensure_template() -> Path:
    path = template_path()
    if path.exists():
        return path
    from docx import Document
    from docx.enum.text import WD_ALIGN_PARAGRAPH
    from docx.shared import Pt

    doc = Document()
    normal = doc.styles["Normal"]
    normal.font.name = "Calibri"
    normal.font.size = Pt(11)

    doc.add_paragraph("{{ sender_line }}")
    doc.add_paragraph("")
    doc.add_paragraph("{{ recipient.company }}")
    doc.add_paragraph("{{ recipient_line_2 }}")
    doc.add_paragraph("{{ recipient_line_3 }}")
    doc.add_paragraph("{{ recipient_line_4 }}")
    doc.add_paragraph("")
    datep = doc.add_paragraph("{{ city_date }}")
    datep.alignment = WD_ALIGN_PARAGRAPH.RIGHT
    doc.add_paragraph("")
    subj = doc.add_paragraph()
    subj.add_run("{{ subject }}").bold = True
    doc.add_paragraph("")
    doc.add_paragraph("{{ salutation }}")
    doc.add_paragraph("")
    doc.add_paragraph("{%p for para in paragraphs %}")
    doc.add_paragraph("{{ para }}")
    doc.add_paragraph("")
    doc.add_paragraph("{%p endfor %}")
    doc.add_paragraph("{{ closing }}")
    doc.add_paragraph("")
    doc.add_paragraph("{{ sender.name }}")

    path.parent.mkdir(parents=True, exist_ok=True)
    doc.save(str(path))
    return path


def _format_date(today: date, language: str) -> str:
    months = _MONTHS_DE if language == "de" else _MONTHS_EN
    if language == "de":
        return f"{today.day}. {months[today.month - 1]} {today.year}"
    return f"{today.day} {months[today.month - 1]} {today.year}"


def render_cover_letter(
    content: CoverLetterResult,
    sender: dict[str, Any],
    out_path: Path,
    *,
    today: date | None = None,
) -> Path:
    from docxtpl import DocxTemplate

    today = today or date.today()
    recipient = content.recipient
    plz_city = " ".join(p for p in (recipient.postal_code, recipient.city) if p)
    sender_bits = [
        sender.get("name"),
        sender.get("street"),
        " ".join(p for p in (sender.get("postal_code"), sender.get("city")) if p),
        sender.get("email"),
        sender.get("phone"),
    ]
    context = {
        "sender": sender,
        "sender_line": " · ".join(b for b in sender_bits if b),
        "recipient": recipient.model_dump(),
        "recipient_line_2": recipient.name or "",
        "recipient_line_3": recipient.street or "",
        "recipient_line_4": plz_city,
        "city_date": f"{sender.get('city') or ''}, {_format_date(today, content.language)}".lstrip(
            ", "
        ),
        "subject": content.subject,
        "salutation": content.salutation,
        "paragraphs": content.paragraphs,
        "closing": content.closing,
    }

    tpl = DocxTemplate(str(ensure_template()))
    tpl.render(context)
    out_path.parent.mkdir(parents=True, exist_ok=True)
    tpl.save(str(out_path))
    return out_path
