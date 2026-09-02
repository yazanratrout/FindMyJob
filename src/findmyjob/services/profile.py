"""Profile access + the CV-parse merge logic.

The installation has exactly one profile. The LLM parser fills it in; the user
can override any field afterwards. Overridden ("locked") fields are never
touched by a subsequent re-parse.
"""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, col, delete, select

from findmyjob.llm.client import LlmResult
from findmyjob.llm.profile_parser import ParsedProfile, parse_profile
from findmyjob.logging import get_logger
from findmyjob.models.enums import DegreeLevel, DocumentType, SkillCategory
from findmyjob.models.profile import Document, Profile, ProfileSkill

log = get_logger("profile")

# ParsedProfile attr -> Profile attr, for the flat scalar fields.
_SCALAR_MAP: dict[str, str] = {
    "full_name": "full_name",
    "email": "email",
    "phone": "phone",
    "nationality": "nationality",
    "university": "university",
    "program": "program",
    "current_semester": "current_semester",
    "enrollment_valid_until": "enrollment_valid_until",
    "expected_graduation": "expected_graduation",
}
_ADDRESS_MAP: dict[str, str] = {
    "street": "street",
    "postal_code": "postal_code",
    "city": "city",
    "country": "country",
}


def get_profile(session: Session) -> Profile:
    profile = session.exec(select(Profile).order_by(col(Profile.id))).first()
    if profile is None:
        profile = Profile()
        session.add(profile)
        session.flush()
    return profile


def profile_summary_text(session: Session) -> str:
    """A compact plain-text profile for LLM prompts (judge, cover letter)."""
    profile = get_profile(session)
    skills = session.exec(
        select(ProfileSkill).where(col(ProfileSkill.profile_id) == profile.id)
    ).all()
    tech = [s.name for s in skills if s.category != SkillCategory.LANGUAGE][:20]
    langs = [
        f"{s.name} ({s.evidence.replace('CEFR', '').strip() or 'B1'})"
        for s in skills
        if s.category == SkillCategory.LANGUAGE
    ]
    lines = [
        f"Name: {profile.full_name or 'n/a'}",
        f"Studies: {profile.program or 'n/a'} at {profile.university or 'n/a'}"
        + (f", semester {profile.current_semester}" if profile.current_semester else ""),
        f"Degree level: {profile.degree_level.value if profile.degree_level else 'n/a'}",
        f"Enrolled until: {profile.enrollment_valid_until or 'n/a'}; "
        f"expected graduation: {profile.expected_graduation or 'n/a'}",
        f"Nationality: {profile.nationality or 'n/a'} "
        f"(EU/EEA: {'yes' if profile.is_eu_eea else 'no'})",
        f"Skills: {', '.join(tech) or 'n/a'}",
        f"Languages: {', '.join(langs) or 'n/a'}",
    ]
    highlights = profile.structured_json.get("highlights_from_references", [])
    if highlights:
        lines.append("Reference highlights: " + " | ".join(highlights[:3]))
    return "\n".join(lines)


def collect_document_sections(session: Session) -> dict[str, str]:
    """Group uploaded document text by kind for the parser."""
    docs = session.exec(select(Document)).all()
    sections: dict[str, list[str]] = {}
    label_by_type = {
        DocumentType.CV: "cv",
        DocumentType.TRANSCRIPT: "transcript",
        DocumentType.ENROLLMENT: "enrollment certificate",
        DocumentType.REFERENCE: "reference letter",
        DocumentType.PORTFOLIO: "portfolio",
        DocumentType.OTHER: "other document",
    }
    for doc in docs:
        if not doc.extracted_text:
            continue
        sections.setdefault(label_by_type[doc.type], []).append(doc.extracted_text)
    return {label: "\n\n---\n\n".join(texts) for label, texts in sections.items()}


def _coerce_degree(value: str | None) -> DegreeLevel | None:
    try:
        return DegreeLevel(value) if value else None
    except ValueError:
        return None


def _coerce_category(value: str) -> SkillCategory:
    try:
        return SkillCategory(value)
    except ValueError:
        return SkillCategory.TECHNICAL


def apply_parsed_profile(session: Session, parsed: ParsedProfile) -> Profile:
    """Merge parser output into the profile, honouring locked fields."""
    profile = get_profile(session)
    locked = set(profile.locked_fields)

    for src_attr, dst_attr in _SCALAR_MAP.items():
        if dst_attr in locked:
            continue
        value = getattr(parsed, src_attr)
        if value not in (None, ""):
            setattr(profile, dst_attr, value)

    for src_attr, dst_attr in _ADDRESS_MAP.items():
        if dst_attr in locked:
            continue
        value = getattr(parsed.address, src_attr)
        if value:
            setattr(profile, dst_attr, value)

    if "degree_level" not in locked and (deg := _coerce_degree(parsed.degree_level)):
        profile.degree_level = deg
    if "is_eu_eea" not in locked and parsed.is_eu_eea is not None:
        profile.is_eu_eea = parsed.is_eu_eea

    profile.structured_json = parsed.model_dump(mode="json")

    # Replace CV-sourced skills; keep anything the user added manually.
    session.exec(
        delete(ProfileSkill).where(
            col(ProfileSkill.profile_id) == profile.id,
            col(ProfileSkill.source) == "cv",
        )
    )
    existing_manual = {
        s.name.lower()
        for s in session.exec(
            select(ProfileSkill).where(col(ProfileSkill.profile_id) == profile.id)
        ).all()
    }
    for skill in parsed.skills:
        if skill.name.lower() in existing_manual:
            continue
        session.add(
            ProfileSkill(
                profile_id=profile.id,
                name=skill.name,
                category=_coerce_category(skill.category),
                proficiency=skill.proficiency,
                years=skill.years,
                source="cv",
                evidence=skill.evidence,
            )
        )
    for lang in parsed.languages:
        if lang.lang.lower() in existing_manual:
            continue
        session.add(
            ProfileSkill(
                profile_id=profile.id,
                name=lang.lang,
                category=SkillCategory.LANGUAGE,
                proficiency=3,
                source="cv",
                evidence=f"CEFR {lang.cefr}",
            )
        )

    session.add(profile)
    session.flush()
    log.info("profile.parsed_applied", locked=sorted(locked), skills=len(parsed.skills))
    return profile


def parse_and_apply(
    session: Session, *, client: Any = None, run_id: int | None = None
) -> tuple[Profile, LlmResult]:
    sections = collect_document_sections(session)
    if not sections:
        raise ValueError("No document text to parse. Upload a CV first.")
    parsed, result = parse_profile(sections, client=client, run_id=run_id)
    profile = apply_parsed_profile(session, parsed)
    return profile, result


def update_profile(session: Session, patch: dict[str, Any]) -> Profile:
    """Apply user edits and lock every field they touched."""
    profile = get_profile(session)
    locked = set(profile.locked_fields)
    editable = (
        set(_SCALAR_MAP.values())
        | set(_ADDRESS_MAP.values())
        | {
            "degree_level",
            "is_eu_eea",
            "voice_sample_text",
        }
    )
    for key, value in patch.items():
        if key not in editable:
            continue
        if key == "degree_level":
            value = _coerce_degree(value)
        setattr(profile, key, value)
        if key != "voice_sample_text":
            locked.add(key)
    profile.locked_fields = sorted(locked)
    session.add(profile)
    session.flush()
    return profile


def set_skills(session: Session, skills: list[dict[str, Any]]) -> list[ProfileSkill]:
    """Replace the entire skill list with a user-provided one (source='manual')."""
    profile = get_profile(session)
    session.exec(delete(ProfileSkill).where(col(ProfileSkill.profile_id) == profile.id))
    rows: list[ProfileSkill] = []
    for item in skills:
        row = ProfileSkill(
            profile_id=profile.id,
            name=item["name"],
            category=_coerce_category(item.get("category", "technical")),
            proficiency=int(item.get("proficiency", 3)),
            years=item.get("years"),
            source="manual",
            evidence=item.get("evidence", ""),
        )
        session.add(row)
        rows.append(row)
    session.flush()
    return rows
