from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from findmyjob.models.enums import DegreeLevel, SkillCategory
from findmyjob.models.profile import Profile, ProfileSkill


class SkillRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    name: str
    category: SkillCategory
    proficiency: int
    years: float | None
    source: str
    evidence: str


class SkillWrite(BaseModel):
    name: str
    category: SkillCategory = SkillCategory.TECHNICAL
    proficiency: int = Field(default=3, ge=1, le=5)
    years: float | None = None
    evidence: str = ""


class ProfileRead(BaseModel):
    id: int
    full_name: str
    email: str
    phone: str
    street: str
    postal_code: str
    city: str
    country: str
    nationality: str
    is_eu_eea: bool
    university: str
    program: str
    degree_level: DegreeLevel | None
    current_semester: int | None
    enrollment_valid_until: date | None
    expected_graduation: date | None
    voice_sample_text: str
    locked_fields: list[str]
    has_structured_parse: bool
    skills: list[SkillRead]

    @classmethod
    def of(cls, profile: Profile, skills: list[ProfileSkill]) -> ProfileRead:
        assert profile.id is not None
        return cls(
            id=profile.id,
            full_name=profile.full_name,
            email=profile.email,
            phone=profile.phone,
            street=profile.street,
            postal_code=profile.postal_code,
            city=profile.city,
            country=profile.country,
            nationality=profile.nationality,
            is_eu_eea=profile.is_eu_eea,
            university=profile.university,
            program=profile.program,
            degree_level=profile.degree_level,
            current_semester=profile.current_semester,
            enrollment_valid_until=profile.enrollment_valid_until,
            expected_graduation=profile.expected_graduation,
            voice_sample_text=profile.voice_sample_text,
            locked_fields=profile.locked_fields,
            has_structured_parse=bool(profile.structured_json),
            skills=[SkillRead.model_validate(s) for s in skills],
        )


class ProfileUpdate(BaseModel):
    """All optional — only provided fields are changed (and then locked)."""

    full_name: str | None = None
    email: str | None = None
    phone: str | None = None
    street: str | None = None
    postal_code: str | None = None
    city: str | None = None
    country: str | None = None
    nationality: str | None = None
    is_eu_eea: bool | None = None
    university: str | None = None
    program: str | None = None
    degree_level: DegreeLevel | None = None
    current_semester: int | None = None
    voice_sample_text: str | None = None


class ParseResult(BaseModel):
    profile: ProfileRead
    tokens_in: int
    tokens_out: int
    cost_eur: float
    cache_hit: bool
