"""Enumerations shared across models and pipelines."""

from __future__ import annotations

from enum import StrEnum


class DocumentType(StrEnum):
    CV = "cv"
    ENROLLMENT = "enrollment"
    TRANSCRIPT = "transcript"
    REFERENCE = "reference"
    PORTFOLIO = "portfolio"
    OTHER = "other"


class ParseStatus(StrEnum):
    PENDING = "pending"
    DONE = "done"
    FAILED = "failed"


class SkillCategory(StrEnum):
    LANGUAGE = "language"
    TECHNICAL = "technical"
    TOOL = "tool"
    DOMAIN = "domain"
    SOFT = "soft"


class JobType(StrEnum):
    WERKSTUDENT = "werkstudent"
    PRAKTIKUM = "praktikum"
    THESIS = "thesis"
    MINIJOB = "minijob"
    STUDENT_ASSISTANT = "student_assistant"


class ContractType(StrEnum):
    WERKSTUDENT = "werkstudent"
    PRAKTIKUM = "praktikum"
    THESIS = "thesis"
    MINIJOB = "minijob"
    PART_TIME = "part_time"
    FULL_TIME = "full_time"
    UNKNOWN = "unknown"


class AtsType(StrEnum):
    GREENHOUSE = "greenhouse"
    LEVER = "lever"
    PERSONIO = "personio"
    SMARTRECRUITERS = "smartrecruiters"
    ASHBY = "ashby"
    NONE = "none"


class CompanyOrigin(StrEnum):
    SEED = "seed"
    USER = "user"
    DISCOVERED = "discovered"


class RunTrigger(StrEnum):
    SCHEDULE = "schedule"
    MANUAL = "manual"


class RunStatus(StrEnum):
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"


class PipelineStatus(StrEnum):
    OK = "ok"
    PARTIAL = "partial"
    FAILED = "failed"
    SKIPPED = "skipped"


class JobLifecycle(StrEnum):
    ACTIVE = "active"
    STALE = "stale"
    DEAD = "dead"


class Decision(StrEnum):
    RECOMMENDED = "recommended"
    MAYBE = "maybe"
    ARCHIVED = "archived"


class DocumentNecessity(StrEnum):
    REQUIRED = "required"
    LIKELY = "likely"
    OPTIONAL = "optional"


class ApplicationStatus(StrEnum):
    INTERESTED = "interested"
    PREPARING = "preparing"
    APPLIED = "applied"
    INTERVIEW = "interview"
    OFFER = "offer"
    REJECTED = "rejected"
    WITHDRAWN = "withdrawn"


class CefrLevel(StrEnum):
    A1 = "A1"
    A2 = "A2"
    B1 = "B1"
    B2 = "B2"
    C1 = "C1"
    C2 = "C2"
    NATIVE = "native"


class DegreeLevel(StrEnum):
    BACHELOR = "bachelor"
    MASTER = "master"
    PHD = "phd"


class LlmPurpose(StrEnum):
    PROFILE_PARSE = "profile_parse"
    KEYWORD_SUGGEST = "keyword_suggest"
    ANALYZE = "analyze"
    JUDGE = "judge"
    COVER_LETTER = "cover_letter"


class CoverLetterLanguageMode(StrEnum):
    MATCH_POSTING = "match_posting"
    ALWAYS_DE = "always_de"
    ALWAYS_EN = "always_en"


CEFR_ORDER: dict[str, int] = {
    CefrLevel.A1: 1,
    CefrLevel.A2: 2,
    CefrLevel.B1: 3,
    CefrLevel.B2: 4,
    CefrLevel.C1: 5,
    CefrLevel.C2: 6,
    CefrLevel.NATIVE: 7,
}
