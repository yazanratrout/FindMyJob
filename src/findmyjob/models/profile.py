"""User profile, skills and uploaded documents.

We deliberately avoid ORM ``Relationship`` fields: the app is pipeline-heavy and
passes data across session boundaries, so explicit queries are clearer and avoid
lazy-loading surprises.
"""

from __future__ import annotations

from datetime import date, datetime

from sqlalchemy import JSON, Column
from sqlmodel import Field

from findmyjob.models.base import TimestampMixin, utcnow
from findmyjob.models.enums import DegreeLevel, DocumentType, ParseStatus, SkillCategory


class Profile(TimestampMixin, table=True):
    """The single user of this installation."""

    __tablename__ = "profile"

    id: int | None = Field(default=None, primary_key=True)

    full_name: str = ""
    email: str = ""
    phone: str = ""
    street: str = ""
    postal_code: str = ""
    city: str = ""
    country: str = ""
    nationality: str = ""
    is_eu_eea: bool = True

    university: str = ""
    program: str = ""
    degree_level: DegreeLevel | None = None
    current_semester: int | None = None
    enrollment_valid_until: date | None = None
    expected_graduation: date | None = None

    # Logical pointer only (no FK — avoids a profile<->document constraint cycle).
    cv_document_id: int | None = Field(default=None)

    # Full structured parse of the CV (+ supporting docs) produced by the LLM.
    structured_json: dict = Field(default_factory=dict, sa_column=Column(JSON))
    # Fields the user has hand-edited; the parser must not overwrite these.
    locked_fields: list[str] = Field(default_factory=list, sa_column=Column(JSON))
    # A cover letter the user wrote themselves, used as a style exemplar.
    voice_sample_text: str = ""


class ProfileSkill(TimestampMixin, table=True):
    __tablename__ = "profile_skill"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)

    name: str
    category: SkillCategory = SkillCategory.TECHNICAL
    proficiency: int = Field(default=3, ge=1, le=5)
    years: float | None = None
    source: str = "cv"  # cv | manual | transcript
    evidence: str = ""


class Document(TimestampMixin, table=True):
    __tablename__ = "document"

    id: int | None = Field(default=None, primary_key=True)
    profile_id: int = Field(foreign_key="profile.id", index=True)

    type: DocumentType
    filename: str
    stored_path: str
    mime: str
    size_bytes: int

    extracted_text: str | None = None
    parsed_json: dict | None = Field(default=None, sa_column=Column(JSON))
    parse_status: ParseStatus = ParseStatus.PENDING
    parse_error: str | None = None

    uploaded_at: datetime = Field(default_factory=utcnow)
