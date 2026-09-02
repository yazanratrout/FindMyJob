"""Text normalization helpers shared by seeding, dedup and matching."""

from __future__ import annotations

import re
import unicodedata

_LEGAL_SUFFIXES = (
    "gmbh and co kg",
    "gmbh and co. kg",
    "gmbh & co. kg",
    "gmbh & co kg",
    "gmbh",
    "mbh",
    "ag",
    "se",
    "kgaa",
    "kg",
    "e.v.",
    "ev",
    "ug haftungsbeschraenkt",
    "ug",
    "inc.",
    "inc",
    "ltd.",
    "ltd",
    "llc",
    "plc",
)

_GENDER_MARKERS = re.compile(
    r"\(\s*[mwfdxa]\s*(?:[/|\\]\s*[mwfdxa]\s*){1,3}\)",
    flags=re.IGNORECASE,
)
_WHITESPACE = re.compile(r"\s+")
_NON_ALNUM = re.compile(r"[^a-z0-9]+")


def fold_accents(text: str) -> str:
    replacements = {"ä": "ae", "ö": "oe", "ü": "ue", "ß": "ss"}
    for src, dst in replacements.items():
        text = text.replace(src, dst).replace(src.upper(), dst)
    decomposed = unicodedata.normalize("NFKD", text)
    return "".join(ch for ch in decomposed if not unicodedata.combining(ch))


def normalize_company_name(name: str) -> str:
    """Lowercase, de-accent, drop legal suffixes, collapse to a stable key."""
    base = fold_accents(name).lower().strip()
    base = base.replace("&", " and ")
    for suffix in _LEGAL_SUFFIXES:
        if base.endswith(" " + suffix):
            base = base[: -len(suffix)].strip(" ,-")
    base = _NON_ALNUM.sub(" ", base)
    return _WHITESPACE.sub(" ", base).strip()


def normalize_title(title: str) -> str:
    """Lowercase, de-accent, remove gender markers, collapse whitespace."""
    base = _GENDER_MARKERS.sub(" ", title)
    base = fold_accents(base).lower()
    base = base.replace("*", " ").replace(":", " ").replace("/", " ")
    base = _NON_ALNUM.sub(" ", base)
    return _WHITESPACE.sub(" ", base).strip()


def slugify(text: str) -> str:
    return _NON_ALNUM.sub("-", fold_accents(text).lower()).strip("-")


# Common EN/DE spellings for cities, so an English posting isn't dropped by a
# German target city (and vice versa).
_CITY_ALIASES: dict[str, set[str]] = {
    "muenchen": {"munich", "muenchen", "munchen"},
    "koeln": {"cologne", "koeln", "koln"},
    "nuernberg": {"nuremberg", "nuernberg"},
    "wien": {"vienna", "wien"},
    "zuerich": {"zurich", "zuerich"},
}


def city_tokens(city: str) -> set[str]:
    base = fold_accents(city).lower().strip()
    return _CITY_ALIASES.get(base, {base}) if base else set()


def location_mentions_city(location: str | None, city: str) -> bool:
    """True if a free-text location string plausibly refers to ``city`` (or is remote)."""
    if not city:
        return True
    if not location:
        return False
    loc = fold_accents(location).lower()
    if "remote" in loc:
        return True
    return any(token in loc for token in city_tokens(city))
