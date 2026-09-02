"""Work out which documents an application needs, from the posting analysis."""

from __future__ import annotations

from findmyjob.models.enums import ContractType, DocumentNecessity
from findmyjob.models.job import JobAnalysis

_WERKSTUDENT_LIKE = {
    ContractType.WERKSTUDENT,
    ContractType.MINIJOB,
    ContractType.PRAKTIKUM,
    ContractType.THESIS,
}


def _entry(
    doc_type: str, necessity: DocumentNecessity, reason: str, have: bool
) -> dict[str, object]:
    return {
        "doc_type": doc_type,
        "necessity": necessity.value,
        "reason": reason,
        "have": have,
    }


def compute_documents_needed(
    analysis: JobAnalysis, have_types: set[str]
) -> list[dict[str, object]]:
    requested = " ".join(analysis.documents_requested).lower()
    contract = (
        analysis.contract_type.value
        if hasattr(analysis.contract_type, "value")
        else str(analysis.contract_type)
    )
    items: list[dict[str, object]] = [
        _entry("cv", DocumentNecessity.REQUIRED, "Standard for any application", "cv" in have_types)
    ]

    cover_letter = any(
        t in requested
        for t in ("cover letter", "anschreiben", "motivation", "motivationsschreiben")
    )
    items.append(
        _entry(
            "cover_letter",
            DocumentNecessity.REQUIRED if cover_letter else DocumentNecessity.OPTIONAL,
            "Explicitly requested" if cover_letter else "Not requested — optional but recommended",
            False,
        )
    )

    enrollment_asked = any(
        t in requested
        for t in ("immatrikulation", "enrol", "enroll", "matriculation", "student status")
    )
    if analysis.enrollment_required == "yes" or enrollment_asked:
        necessity = DocumentNecessity.REQUIRED
        reason = "Posting requires proof of current enrolment"
    elif ContractType(contract) in _WERKSTUDENT_LIKE:
        necessity = DocumentNecessity.LIKELY
        reason = "Usually needed to sign a working-student / intern contract"
    else:
        necessity = DocumentNecessity.OPTIONAL
        reason = "Not mentioned"
    items.append(_entry("enrollment", necessity, reason, "enrollment" in have_types))

    transcript_asked = any(
        t in requested for t in ("transcript", "notenspiegel", "grades", "academic record")
    )
    items.append(
        _entry(
            "transcript",
            DocumentNecessity.REQUIRED if transcript_asked else DocumentNecessity.OPTIONAL,
            "Grades / transcript requested" if transcript_asked else "Not requested",
            "transcript" in have_types,
        )
    )

    references_asked = any(
        t in requested for t in ("reference", "zeugnis", "arbeitszeugnis", "recommendation")
    )
    if references_asked:
        items.append(
            _entry(
                "reference",
                DocumentNecessity.REQUIRED,
                "References / work certificates requested",
                "reference" in have_types,
            )
        )

    portfolio_asked = any(
        t in requested
        for t in ("portfolio", "github", "code sample", "work sample", "arbeitsproben")
    )
    if portfolio_asked:
        items.append(
            _entry(
                "portfolio",
                DocumentNecessity.REQUIRED,
                "Portfolio / code samples requested",
                "portfolio" in have_types,
            )
        )

    return items
