"""Build the set of active job sources from settings + available credentials."""

from __future__ import annotations

from findmyjob.config import Settings
from findmyjob.logging import get_logger
from findmyjob.models.config import AppSettings
from findmyjob.services.http import HttpClient
from findmyjob.sources.api import (
    AdzunaSource,
    ArbeitnowSource,
    BundesagenturSource,
    TheMuseSource,
)
from findmyjob.sources.base import JobSource, SourceQuery

log = get_logger("sources")

# Every known source class. ATS connectors are appended in CP6.
ALL_SOURCE_CLASSES: tuple[type[JobSource], ...] = (
    BundesagenturSource,
    AdzunaSource,
    ArbeitnowSource,
    TheMuseSource,
)


def build_sources(
    process_settings: Settings,
    app_settings: AppSettings,
    http: HttpClient,
) -> list[JobSource]:
    """Instantiate every source that is both enabled and configured."""
    active: list[JobSource] = []
    for cls in ALL_SOURCE_CLASSES:
        if not app_settings.sources_enabled.get(cls.key, True):
            continue
        source = cls(process_settings, http)
        if not source.is_configured():
            log.info("sources.skip_unconfigured", source=cls.key)
            continue
        active.append(source)
    return active


def build_source_query(app_settings: AppSettings) -> SourceQuery:
    keywords = list(
        dict.fromkeys([*app_settings.target_titles, *app_settings.keywords_allow])
    ) or list(app_settings.target_fields)
    return SourceQuery(
        keywords=keywords,
        city=app_settings.target_city,
        lat=app_settings.target_lat,
        lon=app_settings.target_lon,
        radius_km=app_settings.radius_km,
        allow_remote=app_settings.allow_remote,
        max_age_days=app_settings.recency_days,
        job_types=list(app_settings.job_types),
        limit_per_source=150,
    )
