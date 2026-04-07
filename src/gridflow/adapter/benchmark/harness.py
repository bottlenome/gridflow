"""Harness that evaluates metrics against one or more ``ExperimentResult``s."""

from __future__ import annotations

from collections.abc import Iterable
from dataclasses import dataclass, field

from gridflow.adapter.benchmark.metrics import BUILTIN_METRICS, MetricCalculator
from gridflow.domain.error import BenchmarkError
from gridflow.usecase.result import ExperimentResult


@dataclass(frozen=True)
class BenchmarkRunSummary:
    """Metric values computed for a single experiment."""

    experiment_id: str
    values: tuple[tuple[str, float], ...]

    def value(self, name: str) -> float:
        for k, v in self.values:
            if k == name:
                return v
        raise KeyError(name)

    def to_dict(self) -> dict[str, object]:
        return {"experiment_id": self.experiment_id, "values": dict(self.values)}


@dataclass(frozen=True)
class ComparisonReport:
    """Side-by-side diff of metrics across two experiments."""

    baseline_id: str
    candidate_id: str
    diffs: tuple[tuple[str, float, float, float], ...]  # (name, baseline, candidate, delta)

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline_id,
            "candidate": self.candidate_id,
            "metrics": [
                {"name": name, "baseline": base, "candidate": cand, "delta": delta}
                for name, base, cand, delta in self.diffs
            ],
        }


@dataclass
class BenchmarkHarness:
    """Run a fixed set of :class:`MetricCalculator`s over experiment results."""

    metrics: tuple[MetricCalculator, ...] = field(default_factory=lambda: BUILTIN_METRICS)

    def evaluate(self, result: ExperimentResult) -> BenchmarkRunSummary:
        """Compute every configured metric for a single experiment."""
        if not self.metrics:
            raise BenchmarkError("BenchmarkHarness has no metric calculators configured")

        values: list[tuple[str, float]] = []
        for metric in self.metrics:
            values.append((metric.name, float(metric.calculate(result))))
        return BenchmarkRunSummary(
            experiment_id=result.experiment_id,
            values=tuple(values),
        )

    def compare(self, baseline: ExperimentResult, candidate: ExperimentResult) -> ComparisonReport:
        """Compute metrics for both experiments and emit a diff report."""
        base_summary = self.evaluate(baseline)
        cand_summary = self.evaluate(candidate)

        diffs: list[tuple[str, float, float, float]] = []
        base_map = dict(base_summary.values)
        cand_map = dict(cand_summary.values)
        all_names = sorted(set(base_map) | set(cand_map))
        for name in all_names:
            base_value = base_map.get(name, float("nan"))
            cand_value = cand_map.get(name, float("nan"))
            delta = cand_value - base_value
            diffs.append((name, base_value, cand_value, delta))

        return ComparisonReport(
            baseline_id=baseline.experiment_id,
            candidate_id=candidate.experiment_id,
            diffs=tuple(diffs),
        )

    def evaluate_many(self, results: Iterable[ExperimentResult]) -> tuple[BenchmarkRunSummary, ...]:
        return tuple(self.evaluate(r) for r in results)
