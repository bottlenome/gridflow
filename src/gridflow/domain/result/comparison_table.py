"""Method-comparison table domain model — paper export input (AS-5).

Architecture: ``docs/architecture/02_architecture_significance.md`` AS-5
(Publication Productivity) requires the Benchmark Harness comparison
output to convert directly into the "Results" table of a paper.  This
module defines the canonical, tool-independent representation of such a
table: methods (rows) x metrics (columns), each cell a mean with an
optional confidence interval.

Producers: BenchmarkHarness comparison reports, sweep summaries, or any
external study that emits the canonical JSON (``to_dict`` schema).
Consumers: :mod:`gridflow.adapter.export.paper` rendering strategies.

All value objects are frozen + hashable per CLAUDE.md §0.1.
"""

from __future__ import annotations

import math
from dataclasses import dataclass
from typing import Any

from gridflow.domain.error import CDLValidationError

_OBJECTIVES = ("min", "max")


@dataclass(frozen=True)
class MetricSpec:
    """One metric column of a comparison table.

    Attributes:
        name: Metric identifier (e.g. ``"commit_drop"``).
        unit: Display unit (e.g. ``"%"``, ``"kW"``); empty for unitless.
        objective: ``"min"`` if lower is better, ``"max"`` if higher is.
    """

    name: str
    unit: str
    objective: str

    def __post_init__(self) -> None:
        if not self.name:
            raise CDLValidationError("MetricSpec.name must be non-empty")
        if self.objective not in _OBJECTIVES:
            raise CDLValidationError(
                f"MetricSpec.objective must be one of {_OBJECTIVES}, got {self.objective!r}"
            )

    def to_dict(self) -> dict[str, object]:
        return {"name": self.name, "unit": self.unit, "objective": self.objective}

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricSpec:
        return cls(
            name=str(data["name"]),
            unit=str(data.get("unit", "")),
            objective=str(data.get("objective", "min")),
        )


@dataclass(frozen=True)
class MetricValue:
    """One cell: mean value with optional confidence interval.

    The CI bounds are either both present or both absent
    (:attr:`has_ci`); a half-specified interval is invalid.
    """

    mean: float
    ci_low: float | None = None
    ci_high: float | None = None

    def __post_init__(self) -> None:
        if (self.ci_low is None) != (self.ci_high is None):
            raise CDLValidationError(
                "MetricValue: ci_low and ci_high must be both present or both absent"
            )
        if (
            self.ci_low is not None
            and self.ci_high is not None
            and not (self.ci_low <= self.mean <= self.ci_high)
        ):
            raise CDLValidationError(
                f"MetricValue: CI [{self.ci_low}, {self.ci_high}] "
                f"must bracket mean {self.mean}"
            )
        if not math.isfinite(self.mean):
            raise CDLValidationError("MetricValue.mean must be finite")

    @property
    def has_ci(self) -> bool:
        return self.ci_low is not None

    def to_dict(self) -> dict[str, object]:
        out: dict[str, object] = {"mean": self.mean}
        if self.ci_low is not None:
            out["ci_low"] = self.ci_low
            out["ci_high"] = self.ci_high
        return out

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MetricValue:
        return cls(
            mean=float(data["mean"]),
            ci_low=None if data.get("ci_low") is None else float(data["ci_low"]),
            ci_high=None if data.get("ci_high") is None else float(data["ci_high"]),
        )


@dataclass(frozen=True)
class MethodRow:
    """One method row: name, sample count and per-metric values."""

    method: str
    n: int
    values: tuple[MetricValue, ...]

    def __post_init__(self) -> None:
        if not self.method:
            raise CDLValidationError("MethodRow.method must be non-empty")
        if self.n < 0:
            raise CDLValidationError("MethodRow.n must be >= 0")

    def to_dict(self) -> dict[str, object]:
        return {
            "method": self.method,
            "n": self.n,
            "values": [v.to_dict() for v in self.values],
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> MethodRow:
        return cls(
            method=str(data["method"]),
            n=int(data.get("n", 0)),
            values=tuple(MetricValue.from_dict(v) for v in data.get("values", ())),
        )


@dataclass(frozen=True)
class ComparisonTable:
    """Methods x metrics comparison — the canonical paper-table model.

    Attributes:
        title: Table title (used for LaTeX caption and figure title).
        metrics: Ordered metric columns.
        rows: One row per method; each row's ``values`` align
            positionally with :attr:`metrics`.
        conditions: Experiment conditions as ordered (key, value) pairs;
            rendered into the caption template (tuple-of-pairs per
            CLAUDE.md §0.1, never a dict).
        highlight: Method name to emphasise as "ours" in rendered
            output; empty string for none.
    """

    title: str
    metrics: tuple[MetricSpec, ...]
    rows: tuple[MethodRow, ...]
    conditions: tuple[tuple[str, str], ...] = ()
    highlight: str = ""

    def __post_init__(self) -> None:
        if not self.metrics:
            raise CDLValidationError("ComparisonTable.metrics must be non-empty")
        for row in self.rows:
            if len(row.values) != len(self.metrics):
                raise CDLValidationError(
                    f"ComparisonTable: row {row.method!r} has {len(row.values)} "
                    f"values but {len(self.metrics)} metrics are declared"
                )
        names = [row.method for row in self.rows]
        if len(names) != len(set(names)):
            raise CDLValidationError("ComparisonTable: duplicate method names in rows")
        if self.highlight and self.highlight not in names:
            raise CDLValidationError(
                f"ComparisonTable.highlight {self.highlight!r} is not a row method"
            )

    def best_method(self, metric_index: int) -> str:
        """Return the method with the best mean for the given metric column."""
        if not self.rows:
            raise CDLValidationError("ComparisonTable.best_method: table has no rows")
        spec = self.metrics[metric_index]
        key = (min if spec.objective == "min" else max)(
            self.rows, key=lambda row: row.values[metric_index].mean
        )
        return key.method

    def to_dict(self) -> dict[str, object]:
        return {
            "title": self.title,
            "metrics": [m.to_dict() for m in self.metrics],
            "rows": [r.to_dict() for r in self.rows],
            "conditions": [[k, v] for k, v in self.conditions],
            "highlight": self.highlight,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> ComparisonTable:
        return cls(
            title=str(data.get("title", "")),
            metrics=tuple(MetricSpec.from_dict(m) for m in data.get("metrics", ())),
            rows=tuple(MethodRow.from_dict(r) for r in data.get("rows", ())),
            conditions=tuple(
                (str(k), str(v)) for k, v in data.get("conditions", ())
            ),
            highlight=str(data.get("highlight", "")),
        )
