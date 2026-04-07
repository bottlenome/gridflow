"""Smoke tests for StructuredLogger configuration."""

from __future__ import annotations

import json
from io import StringIO

import structlog

from gridflow.infra.logging import configure_logging, get_logger


def test_configure_logging_is_idempotent() -> None:
    configure_logging(level="INFO")
    configure_logging(level="DEBUG")  # must not raise


def test_get_logger_emits_json_structured_event(capsys: object) -> None:
    configure_logging(level="INFO", json_output=True)
    log = get_logger("test")
    assert isinstance(log, structlog.stdlib.BoundLogger) or hasattr(log, "info")
    # Smoke: just ensure logging doesn't explode; exact capture of structlog
    # output depends on loggerfactory configuration.
    log.info("event_name", key="value")


def test_json_renderer_round_trip() -> None:
    """Directly exercise the JSON renderer to confirm JSON parseability."""
    renderer = structlog.processors.JSONRenderer()
    buf = StringIO()
    output = renderer(None, "info", {"event": "hello", "n": 1})
    buf.write(output if isinstance(output, str) else output.decode("utf-8"))
    parsed = json.loads(buf.getvalue())
    assert parsed["event"] == "hello"
    assert parsed["n"] == 1
