"""Structured logging built on ``structlog`` with JSON Lines output.

Usage::

    from gridflow.infra.logging import configure_logging, get_logger

    configure_logging(level="INFO")
    log = get_logger(__name__)
    log.info("pack_registered", pack_id="ieee13@1.0.0")

Configuration is idempotent — calling :func:`configure_logging` multiple times
is safe, which matters for test harnesses that reconfigure between cases.
"""

from __future__ import annotations

import logging
import sys
from typing import Any

import structlog

_configured = False


def configure_logging(*, level: str = "INFO", json_output: bool = True) -> None:
    """Configure the global ``structlog`` + stdlib ``logging`` stack.

    Log records go to **stderr** to keep stdout free for CLI command output
    (JSON payloads must be parseable by downstream consumers).

    Args:
        level: Standard logging level name.
        json_output: ``True`` (default) emits JSON Lines; ``False`` uses
            ``structlog``'s human-readable ``ConsoleRenderer``.
    """
    global _configured

    numeric_level = getattr(logging, level.upper(), logging.INFO)
    logging.basicConfig(
        format="%(message)s",
        stream=sys.stderr,
        level=numeric_level,
        force=True,
    )

    renderer: Any = structlog.processors.JSONRenderer() if json_output else structlog.dev.ConsoleRenderer()

    structlog.configure(
        processors=[
            structlog.contextvars.merge_contextvars,
            structlog.processors.add_log_level,
            structlog.processors.TimeStamper(fmt="iso", utc=True),
            structlog.processors.StackInfoRenderer(),
            structlog.processors.format_exc_info,
            renderer,
        ],
        wrapper_class=structlog.make_filtering_bound_logger(numeric_level),
        logger_factory=structlog.PrintLoggerFactory(file=sys.stderr),
        cache_logger_on_first_use=True,
    )
    _configured = True


def get_logger(name: str | None = None) -> structlog.stdlib.BoundLogger:
    """Return a structlog BoundLogger, configuring lazily if needed."""
    if not _configured:
        configure_logging()
    return structlog.get_logger(name)  # type: ignore[no-any-return]
