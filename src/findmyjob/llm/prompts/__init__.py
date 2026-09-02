"""Prompt templates (Markdown files in this package)."""

from __future__ import annotations

from functools import lru_cache
from importlib import resources


@lru_cache(maxsize=32)
def load_prompt(name: str) -> str:
    """Return the text of ``<name>.md`` from this package."""
    return resources.files(__name__).joinpath(f"{name}.md").read_text("utf-8").strip()
