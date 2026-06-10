"""Build :class:`ComparisonTable` from on-disk JSON payloads.

Two accepted schemas, auto-detected by :func:`load_comparison_table_json`:

* **Canonical comparison table** (``ComparisonTable.to_dict`` output) -
  ``{"title", "metrics", "rows", ...}``.  Emitted by sweep summaries or
  any external study.
* **Benchmark comparison report** (``ComparisonReport.to_dict`` output) -
  ``{"baseline", "candidate", "metrics": [{name, baseline, candidate,
  delta}]}``.  Written by ``gridflow benchmark --output``.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from gridflow.domain.error import CDLValidationError, ExportError
from gridflow.domain.result.comparison_table import (
    ComparisonTable,
    MethodRow,
    MetricSpec,
    MetricValue,
)


def comparison_table_from_benchmark_report(data: dict[str, Any]) -> ComparisonTable:
    """Map a ``gridflow benchmark`` comparison report onto a ComparisonTable."""
    try:
        baseline = str(data["baseline"])
        candidate = str(data["candidate"])
        metric_entries = list(data["metrics"])
        specs = tuple(
            MetricSpec(name=str(m["name"]), unit="", objective="min")
            for m in metric_entries
        )
        baseline_values = tuple(
            MetricValue(mean=float(m["baseline"])) for m in metric_entries
        )
        candidate_values = tuple(
            MetricValue(mean=float(m["candidate"])) for m in metric_entries
        )
    except (KeyError, TypeError, ValueError) as exc:
        raise ExportError(
            f"benchmark comparison report is malformed: {exc!r}. "
            "Expected the JSON written by `gridflow benchmark --output`."
        ) from exc
    return ComparisonTable(
        title=f"Benchmark comparison: {baseline} vs {candidate}",
        metrics=specs,
        rows=(
            MethodRow(method=baseline, n=1, values=baseline_values),
            MethodRow(method=candidate, n=1, values=candidate_values),
        ),
        conditions=(("baseline", baseline), ("candidate", candidate)),
        highlight=candidate,
    )


def _is_benchmark_report(data: dict[str, Any]) -> bool:
    return "baseline" in data and "candidate" in data and "metrics" in data


def _is_canonical_table(data: dict[str, Any]) -> bool:
    return "rows" in data and "metrics" in data


def load_comparison_table_json(path: Path) -> ComparisonTable:
    """Load a comparison table from JSON, auto-detecting the schema.

    Raises:
        ExportError: If the file is not valid JSON or matches neither
            accepted schema (cause and remedy in the message, QA-9).
    """
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        raise ExportError(f"cannot read comparison JSON from {path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ExportError(
            f"comparison JSON at {path} must be an object, got {type(data).__name__}"
        )
    if _is_benchmark_report(data):
        return comparison_table_from_benchmark_report(data)
    if _is_canonical_table(data):
        try:
            return ComparisonTable.from_dict(data)
        except (KeyError, TypeError, ValueError, CDLValidationError) as exc:
            raise ExportError(f"canonical comparison table at {path} is invalid: {exc}") from exc
    raise ExportError(
        f"unrecognised comparison schema at {path}: expected either a "
        "canonical comparison table ({'title', 'metrics', 'rows'}) or a "
        "`gridflow benchmark --output` report ({'baseline', 'candidate', 'metrics'})."
    )
