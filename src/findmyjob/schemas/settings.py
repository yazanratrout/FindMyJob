from __future__ import annotations

from datetime import date

from pydantic import BaseModel, ConfigDict, Field

from findmyjob.models.config import AppSettings, SemesterTerm
from findmyjob.models.enums import CoverLetterLanguageMode


class SettingsRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    target_city: str
    target_lat: float | None
    target_lon: float | None
    radius_km: int
    allow_remote: bool
    target_fields: list[str]
    target_titles: list[str]
    keywords_allow: list[str]
    keywords_block: list[str]
    job_types: list[str]
    recency_days: int
    language_max_cefr: str
    language_hard: bool
    hours_max: int
    hours_hard: bool
    contract_types: list[str]
    contract_type_hard: bool
    score_threshold_recommend: int
    score_threshold_maybe: int
    weights: dict[str, float]
    blend_soft_ratio: float
    run_time: str
    run_timezone: str
    notify_channels: list[str]
    notify_email: str | None
    notify_telegram_chat_id: str | None
    digest_top_n: int
    cover_letter_language_mode: CoverLetterLanguageMode
    cover_letter_tone: str
    sources_enabled: dict[str, bool]
    eligibility_module_enabled: bool
    retention_days: int
    repost_days: int
    onboarding_completed: bool


class SettingsUpdate(BaseModel):
    """All optional; only provided keys are written."""

    model_config = ConfigDict(extra="forbid")

    target_city: str | None = None
    radius_km: int | None = Field(default=None, gt=0)
    allow_remote: bool | None = None
    target_fields: list[str] | None = None
    target_titles: list[str] | None = None
    keywords_allow: list[str] | None = None
    keywords_block: list[str] | None = None
    job_types: list[str] | None = None
    recency_days: int | None = Field(default=None, gt=0)
    language_max_cefr: str | None = None
    language_hard: bool | None = None
    hours_max: int | None = Field(default=None, gt=0)
    hours_hard: bool | None = None
    contract_types: list[str] | None = None
    contract_type_hard: bool | None = None
    score_threshold_recommend: int | None = Field(default=None, ge=0, le=100)
    score_threshold_maybe: int | None = Field(default=None, ge=0, le=100)
    weights: dict[str, float] | None = None
    blend_soft_ratio: float | None = Field(default=None, ge=0, le=1)
    run_time: str | None = None
    run_timezone: str | None = None
    notify_channels: list[str] | None = None
    notify_email: str | None = None
    notify_telegram_chat_id: str | None = None
    digest_top_n: int | None = Field(default=None, ge=1, le=50)
    cover_letter_language_mode: CoverLetterLanguageMode | None = None
    cover_letter_tone: str | None = None
    sources_enabled: dict[str, bool] | None = None
    eligibility_module_enabled: bool | None = None
    retention_days: int | None = Field(default=None, gt=0)
    repost_days: int | None = Field(default=None, gt=0)
    onboarding_completed: bool | None = None


class KeywordSuggestRequest(BaseModel):
    target_fields: list[str] = Field(default_factory=list)
    target_titles: list[str] = Field(default_factory=list)


class SemesterTermRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)
    id: int
    label: str
    lecture_start: date
    lecture_end: date


class SemesterTermCreate(BaseModel):
    label: str
    lecture_start: date
    lecture_end: date


def settings_read(row: AppSettings) -> SettingsRead:
    return SettingsRead.model_validate(row)


def term_read(row: SemesterTerm) -> SemesterTermRead:
    return SemesterTermRead.model_validate(row)
