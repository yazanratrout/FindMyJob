"""Small shared helpers for source connectors."""

from __future__ import annotations

from datetime import UTC, datetime

from dateutil import parser as dateparser
from selectolax.parser import HTMLParser


def parse_datetime(value: object) -> datetime | None:
    """Parse an ISO string or a unix timestamp into a naive-UTC datetime."""
    if value is None or value == "":
        return None
    try:
        if isinstance(value, int | float):
            dt = datetime.fromtimestamp(float(value), tz=UTC)
        else:
            dt = dateparser.parse(str(value))
        if dt.tzinfo is not None:
            dt = dt.astimezone(UTC).replace(tzinfo=None)
        return dt
    except (ValueError, OverflowError, TypeError):
        return None


def html_to_text(html: str | None) -> str:
    if not html:
        return ""
    text = HTMLParser(html).text(separator="\n", strip=True)
    lines = [line.strip() for line in text.splitlines()]
    return "\n".join(line for line in lines if line)


def matches_any_keyword(text: str, keywords: list[str]) -> bool:
    """True if *any* keyword appears in text (case-insensitive). Empty list = match all."""
    if not keywords:
        return True
    haystack = text.lower()
    return any(kw.lower() in haystack for kw in keywords if kw)


def is_recent(dt: datetime | None, max_age_days: int) -> bool:
    """True when the posting is within the window, or when the date is unknown."""
    if dt is None:
        return True
    age = datetime.now(UTC).replace(tzinfo=None) - dt
    return age.days <= max_age_days
