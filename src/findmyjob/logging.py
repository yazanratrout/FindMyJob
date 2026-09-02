"""Structured logging setup.

Console output is human-readable; a rotating file handler writes JSON lines to
``<data_dir>/logs/findmyjob.log`` for later inspection.
"""

from __future__ import annotations

import logging
import logging.handlers
import sys
from typing import Any

import structlog

from findmyjob.config import get_settings

_CONFIGURED = False


def configure_logging(*, level: str = "INFO", json_console: bool | None = None) -> None:
    """Idempotently configure stdlib logging + structlog."""
    global _CONFIGURED
    if _CONFIGURED:
        return

    settings = get_settings()
    settings.ensure_dirs()
    use_json_console = settings.is_production if json_console is None else json_console

    timestamper = structlog.processors.TimeStamper(fmt="iso", utc=True)
    shared_processors: list[Any] = [
        structlog.contextvars.merge_contextvars,
        structlog.stdlib.add_log_level,
        structlog.stdlib.add_logger_name,
        timestamper,
        structlog.processors.StackInfoRenderer(),
        structlog.processors.format_exc_info,
    ]

    structlog.configure(
        processors=[
            *shared_processors,
            structlog.stdlib.ProcessorFormatter.wrap_for_formatter,
        ],
        logger_factory=structlog.stdlib.LoggerFactory(),
        wrapper_class=structlog.stdlib.BoundLogger,
        cache_logger_on_first_use=True,
    )

    console_renderer: Any = (
        structlog.processors.JSONRenderer()
        if use_json_console
        else structlog.dev.ConsoleRenderer(colors=sys.stderr.isatty())
    )
    console_handler = logging.StreamHandler(sys.stderr)
    console_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=console_renderer,
        )
    )

    file_handler = logging.handlers.RotatingFileHandler(
        settings.logs_dir / "findmyjob.log",
        maxBytes=5 * 1024 * 1024,
        backupCount=10,
        encoding="utf-8",
    )
    file_handler.setFormatter(
        structlog.stdlib.ProcessorFormatter(
            foreign_pre_chain=shared_processors,
            processor=structlog.processors.JSONRenderer(),
        )
    )

    root = logging.getLogger()
    root.handlers.clear()
    root.addHandler(console_handler)
    root.addHandler(file_handler)
    root.setLevel(level)

    for noisy in ("httpx", "httpcore", "urllib3"):
        logging.getLogger(noisy).setLevel(logging.WARNING)

    _CONFIGURED = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a bound structlog logger, configuring logging on first use."""
    if not _CONFIGURED:
        configure_logging()
    return structlog.stdlib.get_logger(name)
