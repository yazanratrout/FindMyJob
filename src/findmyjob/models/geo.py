"""Cached geocoding results (city name -> coordinates)."""

from __future__ import annotations

from sqlmodel import Field

from findmyjob.models.base import TimestampMixin


class GeocodeCache(TimestampMixin, table=True):
    __tablename__ = "geocode_cache"

    query: str = Field(primary_key=True)
    lat: float | None = None
    lon: float | None = None
