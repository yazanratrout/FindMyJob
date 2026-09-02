"""The job-source connector contract.

Every source — an official API or a public ATS endpoint — implements
:class:`JobSource`. A source turns a :class:`SourceQuery` into a list of
:class:`RawJob`. It never touches the database; the ``fetch`` pipeline persists
what it returns.
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from datetime import datetime
from typing import Any, ClassVar

from pydantic import BaseModel, Field

from findmyjob.config import Settings
from findmyjob.services.http import HttpClient


class SourceQuery(BaseModel):
    """What to search for — built from the user's settings."""

    keywords: list[str] = Field(default_factory=list)
    city: str = ""
    lat: float | None = None
    lon: float | None = None
    radius_km: int = 30
    allow_remote: bool = True
    max_age_days: int = 30
    job_types: list[str] = Field(default_factory=list)
    limit_per_source: int = 150


class RawJob(BaseModel):
    """A posting as returned by a source, before normalization/enrichment."""

    source_key: str
    source_job_id: str
    url: str
    apply_url: str | None = None
    title: str
    company_name: str = ""
    location: str | None = None
    is_remote: bool = False
    posted_at: datetime | None = None
    description_text: str | None = None
    description_html: str | None = None
    salary_raw: str | None = None
    extra: dict[str, Any] = Field(default_factory=dict)


class JobSource(ABC):
    #: stable identifier, must match a key in ``AppSettings.sources_enabled``
    key: ClassVar[str]
    display_name: ClassVar[str]
    #: names of ``Settings`` attributes that must be truthy for this source to run
    requires_secrets: ClassVar[tuple[str, ...]] = ()

    def __init__(self, settings: Settings, http: HttpClient) -> None:
        self._settings = settings
        self._http = http

    def is_configured(self) -> bool:
        return all(getattr(self._settings, name, None) for name in self.requires_secrets)

    @abstractmethod
    async def fetch(self, query: SourceQuery) -> list[RawJob]:
        """Return postings matching ``query``. Must not raise for empty results."""
        raise NotImplementedError
