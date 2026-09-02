"""Best-effort city -> (lat, lon) lookup via OpenStreetMap Nominatim.

Results are cached in the database. A failure is never fatal: the caller keeps
whatever coordinates it had (possibly none) and radius filtering degrades to a
name match until the next successful lookup.
"""

from __future__ import annotations

from collections.abc import Callable

import httpx
from sqlmodel import Session, col, select

from findmyjob.logging import get_logger
from findmyjob.models.geo import GeocodeCache
from findmyjob.normalize import slugify

log = get_logger("geocode")

_USER_AGENT = "FindMyJob/0.1 (personal job search)"
Geocoder = Callable[[str], tuple[float, float] | None]


def _nominatim_lookup(query: str) -> tuple[float, float] | None:
    resp = httpx.get(
        "https://nominatim.openstreetmap.org/search",
        params={"q": query, "format": "json", "limit": 1},
        headers={"User-Agent": _USER_AGENT},
        timeout=10.0,
    )
    resp.raise_for_status()
    data = resp.json()
    if not data:
        return None
    return float(data[0]["lat"]), float(data[0]["lon"])


def geocode_city(
    session: Session,
    city: str,
    *,
    geocoder: Geocoder | None = None,
) -> tuple[float, float] | None:
    geocoder = geocoder or _nominatim_lookup
    key = slugify(city)
    if not key:
        return None

    cached = session.exec(select(GeocodeCache).where(col(GeocodeCache.query) == key)).first()
    if cached is not None:
        if cached.lat is not None and cached.lon is not None:
            return (cached.lat, cached.lon)
        return None

    try:
        coords = geocoder(city)
    except Exception as exc:  # network / parse — degrade gracefully
        log.warning("geocode.failed", city=city, error=str(exc))
        return None

    lat, lon = coords if coords else (None, None)
    session.add(GeocodeCache(query=key, lat=lat, lon=lon))
    session.flush()
    return coords
