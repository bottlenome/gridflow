"""Render CLI payloads as plain/json/table strings.

The formatter is intentionally minimalist — no external dependencies — so the
CLI tests stay fast and deterministic.
"""

from __future__ import annotations

import enum
import json
from typing import Any

from gridflow.domain.error import UnsupportedFormatError


class OutputFormat(enum.Enum):
    PLAIN = "plain"
    JSON = "json"
    TABLE = "table"


class OutputFormatter:
    """Render list / dict payloads into a single string."""

    def __init__(self, fmt: OutputFormat = OutputFormat.PLAIN) -> None:
        self._fmt = fmt

    @property
    def format(self) -> OutputFormat:
        return self._fmt

    def render(self, payload: Any) -> str:
        if self._fmt is OutputFormat.JSON:
            return json.dumps(payload, indent=2, sort_keys=True, default=_json_default)
        if self._fmt is OutputFormat.PLAIN:
            return _render_plain(payload)
        if self._fmt is OutputFormat.TABLE:
            return _render_table(payload)
        raise UnsupportedFormatError(f"Unsupported output format: {self._fmt}")


# --------------------------------------------------------------- helpers


def _json_default(obj: Any) -> Any:
    if hasattr(obj, "to_dict"):
        return obj.to_dict()
    if hasattr(obj, "isoformat"):
        return obj.isoformat()
    return str(obj)


def _render_plain(payload: Any) -> str:
    if isinstance(payload, str):
        return payload
    if isinstance(payload, list):
        return "\n".join(_render_plain(p) for p in payload)
    if isinstance(payload, dict):
        return "\n".join(f"{k}: {_render_plain(v)}" for k, v in payload.items())
    return str(payload)


def _render_table(payload: Any) -> str:
    """Render a list of dicts as a fixed-width text table."""
    if not isinstance(payload, list) or not payload:
        return _render_plain(payload)
    rows = [row for row in payload if isinstance(row, dict)]
    if not rows:
        return _render_plain(payload)

    headers: list[str] = []
    for row in rows:
        for key in row:
            if key not in headers:
                headers.append(key)

    widths = {h: max(len(h), *(len(str(row.get(h, ""))) for row in rows)) for h in headers}
    header_line = "  ".join(h.ljust(widths[h]) for h in headers)
    sep_line = "  ".join("-" * widths[h] for h in headers)
    body_lines = ["  ".join(str(row.get(h, "")).ljust(widths[h]) for h in headers) for row in rows]
    return "\n".join([header_line, sep_line, *body_lines])
