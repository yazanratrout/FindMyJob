"""Read / update the singleton AppSettings row."""

from __future__ import annotations

from typing import Any

from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.config import DEFAULT_SOURCES_ENABLED, AppSettings
from findmyjob.services.geocode import Geocoder, geocode_city

log = get_logger("settings")

# Fields the API is allowed to write. Everything else is derived or internal.
WRITABLE_FIELDS: frozenset[str] = frozenset(
    {
        "target_city",
        "radius_km",
        "allow_remote",
        "target_fields",
        "target_titles",
        "keywords_allow",
        "keywords_block",
        "job_types",
        "recency_days",
        "language_max_cefr",
        "language_hard",
        "hours_max",
        "hours_hard",
        "contract_types",
        "contract_type_hard",
        "score_threshold_recommend",
        "score_threshold_maybe",
        "weights",
        "blend_soft_ratio",
        "run_time",
        "run_timezone",
        "notify_channels",
        "notify_email",
        "notify_telegram_chat_id",
        "digest_top_n",
        "cover_letter_language_mode",
        "cover_letter_tone",
        "sources_enabled",
        "eligibility_module_enabled",
        "retention_days",
        "repost_days",
        "onboarding_completed",
    }
)


def get_app_settings(session: Session) -> AppSettings:
    row = session.exec(select(AppSettings).order_by(col(AppSettings.id))).first()
    if row is None:
        row = AppSettings()
        session.add(row)
        session.flush()
    return row


def _validate(row: AppSettings) -> None:
    if not 0.0 <= row.blend_soft_ratio <= 1.0:
        raise ValueError("blend_soft_ratio must be between 0 and 1")
    if row.score_threshold_maybe > row.score_threshold_recommend:
        raise ValueError("score_threshold_maybe cannot exceed score_threshold_recommend")
    if row.radius_km <= 0:
        raise ValueError("radius_km must be positive")
    if row.hours_max <= 0:
        raise ValueError("hours_max must be positive")
    unknown = set(row.sources_enabled) - set(DEFAULT_SOURCES_ENABLED)
    if unknown:
        raise ValueError(f"unknown sources: {sorted(unknown)}")
    hhmm = row.run_time.split(":")
    if len(hhmm) != 2 or not (0 <= int(hhmm[0]) < 24 and 0 <= int(hhmm[1]) < 60):
        raise ValueError("run_time must be HH:MM (24h)")


def update_app_settings(
    session: Session,
    patch: dict[str, Any],
    *,
    geocoder: Geocoder | None = None,
) -> AppSettings:
    row = get_app_settings(session)
    city_before = row.target_city

    for key, value in patch.items():
        if key not in WRITABLE_FIELDS:
            continue
        setattr(row, key, value)

    _validate(row)

    if row.target_city and (row.target_city != city_before or row.target_lat is None):
        coords = geocode_city(session, row.target_city, geocoder=geocoder)
        if coords:
            row.target_lat, row.target_lon = coords

    session.add(row)
    session.flush()
    log.info("settings.updated", keys=sorted(k for k in patch if k in WRITABLE_FIELDS))
    return row
