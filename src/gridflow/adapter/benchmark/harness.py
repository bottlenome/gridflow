"""Harness that evaluates metrics against one or more ``ExperimentResult``s."""

from __future__ import annotations

import statistics
from collections.abc import Iterable, Sequence
from dataclasses import dataclass, field

from gridflow.adapter.benchmark import stats
from gridflow.adapter.benchmark.metrics import BUILTIN_METRICS, MetricCalculator
from gridflow.domain.error import BenchmarkError
from gridflow.usecase.result import ExperimentResult

#: Metrics whose value is context, not a claim of merit. A wall-clock ``runtime``
#: difference is environment noise as often as a real speed-up, so it is
#: reported but never asserted "significant" (issue #18). Lower is not
#: automatically "better" for these.
INFORMATIONAL_METRICS: frozenset[str] = frozenset({"runtime"})


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


@dataclass(frozen=True)
class MetricComparison:
    """Statistical comparison of one metric across replicate groups.

    Attributes:
        name: Metric identifier.
        baseline_mean / candidate_mean: Group means.
        delta: ``candidate_mean - baseline_mean``.
        baseline_ci / candidate_ci: Percentile bootstrap CI on each mean, or
            ``None`` when a side has fewer than two replicates.
        effect_size: Cohen's d, or ``None`` when undefined.
        p_value: Permutation p-value for the mean difference (``None`` if the
            test could not run).
        p_value_adjusted: Multiple-comparison-corrected p-value.
        significant: The only field a caller should gate a claim on. True iff
            the corrected p-value clears ``alpha`` *and* the inputs are not
            degenerate *and* the metric is not merely informational.
        informational: Metric excluded from merit judgement (e.g. runtime).
        n_baseline / n_candidate: Replicate counts.
        warnings: Degeneracy reasons (see :func:`stats.is_degenerate`).
    """

    name: str
    baseline_mean: float
    candidate_mean: float
    delta: float
    baseline_ci: tuple[float, float] | None
    candidate_ci: tuple[float, float] | None
    effect_size: float | None
    p_value: float | None
    p_value_adjusted: float | None
    significant: bool
    informational: bool
    n_baseline: int
    n_candidate: int
    warnings: tuple[str, ...]

    def to_dict(self) -> dict[str, object]:
        # Keys mirror the loader contract (issue #23): {side} + {side}_ci so a
        # statistical report round-trips into a paper ComparisonTable with CI
        # intact, plus the full statistical verdict.
        out: dict[str, object] = {
            "name": self.name,
            "baseline": self.baseline_mean,
            "candidate": self.candidate_mean,
            "delta": self.delta,
            "objective": "min",
            "effect_size": self.effect_size,
            "p_value": self.p_value,
            "p_value_adjusted": self.p_value_adjusted,
            "significant": self.significant,
            "informational": self.informational,
            "n_baseline": self.n_baseline,
            "n_candidate": self.n_candidate,
            "warnings": list(self.warnings),
        }
        if self.baseline_ci is not None:
            out["baseline_ci"] = [self.baseline_ci[0], self.baseline_ci[1]]
        if self.candidate_ci is not None:
            out["candidate_ci"] = [self.candidate_ci[0], self.candidate_ci[1]]
        return out


@dataclass(frozen=True)
class StatisticalComparisonReport:
    """Replicate-aware benchmark comparison — the honest-verdict report (#18)."""

    baseline_id: str
    candidate_id: str
    alpha: float
    correction: str
    metrics: tuple[MetricComparison, ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "baseline": self.baseline_id,
            "candidate": self.candidate_id,
            "alpha": self.alpha,
            "correction": self.correction,
            "metrics": [m.to_dict() for m in self.metrics],
        }

    @property
    def any_significant(self) -> bool:
        return any(m.significant for m in self.metrics)


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

    def compare_groups(
        self,
        baseline: Sequence[ExperimentResult],
        candidate: Sequence[ExperimentResult],
        *,
        alpha: float = 0.05,
        correction: str = "holm",
        bootstrap_n: int = 2000,
        seed: int = 0,
    ) -> StatisticalComparisonReport:
        """Compare two *groups* of replicate experiments with a real verdict.

        Each metric gets an effect size, a permutation p-value (corrected for
        multiple metrics), bootstrap CIs on both means, and a ``significant``
        flag that is only ever True when the evidence supports it: the
        corrected p clears ``alpha``, both sides carry ≥2 replicates, the
        within-group variance is non-zero, and the metric is not informational.

        This is the guard the MVP trials lacked — a mean delta of the right
        sign no longer counts as an improvement on its own (issue #18).
        """
        if not self.metrics:
            raise BenchmarkError("BenchmarkHarness has no metric calculators configured")
        if not baseline or not candidate:
            raise BenchmarkError("compare_groups requires at least one experiment on each side")

        def _group_id(group: Sequence[ExperimentResult]) -> str:
            head = group[0].experiment_id
            return f"{head}(+{len(group) - 1})" if len(group) > 1 else head

        base_id = _group_id(baseline)
        cand_id = _group_id(candidate)

        # First pass: per-metric values + raw p-values (correction needs them all).
        raw: list[dict[str, object]] = []
        p_values: list[float] = []
        p_index: list[int] = []  # index into raw for each corrected p-value
        for metric in self.metrics:
            b_vals = [float(metric.calculate(r)) for r in baseline]
            c_vals = [float(metric.calculate(r)) for r in candidate]
            degenerate, reason = stats.is_degenerate(b_vals, c_vals)
            informational = metric.name in INFORMATIONAL_METRICS
            p_value = None if degenerate else stats.permutation_test(b_vals, c_vals, seed=seed)
            entry: dict[str, object] = {
                "name": metric.name,
                "b_vals": b_vals,
                "c_vals": c_vals,
                "degenerate": degenerate,
                "reason": reason,
                "informational": informational,
                "p_value": p_value,
            }
            raw.append(entry)
            # Only non-degenerate, non-informational metrics enter the
            # multiple-comparison family — correcting over metrics we will
            # never call significant only inflates the others' adjusted p.
            if p_value is not None and not informational:
                p_values.append(p_value)
                p_index.append(len(raw) - 1)

        adjusted = stats.adjust_p_values(p_values, method=correction)
        adj_by_raw: dict[int, float] = {p_index[k]: adjusted[k] for k in range(len(adjusted))}

        comparisons: list[MetricComparison] = []
        for i, entry in enumerate(raw):
            b_vals = entry["b_vals"]  # type: ignore[assignment]
            c_vals = entry["c_vals"]  # type: ignore[assignment]
            assert isinstance(b_vals, list) and isinstance(c_vals, list)
            informational = bool(entry["informational"])
            p_value = entry["p_value"]  # type: ignore[assignment]
            p_adj = adj_by_raw.get(i)
            b_mean = statistics.fmean(b_vals)
            c_mean = statistics.fmean(c_vals)
            warnings: list[str] = []
            if entry["reason"]:
                warnings.append(str(entry["reason"]))
            significant = (
                not informational
                and not entry["degenerate"]
                and p_adj is not None
                and p_adj < alpha
            )
            comparisons.append(
                MetricComparison(
                    name=str(entry["name"]),
                    baseline_mean=b_mean,
                    candidate_mean=c_mean,
                    delta=c_mean - b_mean,
                    baseline_ci=stats.mean_ci(b_vals, bootstrap_n=bootstrap_n, seed=seed),
                    candidate_ci=stats.mean_ci(c_vals, bootstrap_n=bootstrap_n, seed=seed),
                    effect_size=stats.cohens_d(b_vals, c_vals),
                    p_value=p_value if isinstance(p_value, float) else None,
                    p_value_adjusted=p_adj,
                    significant=significant,
                    informational=informational,
                    n_baseline=len(b_vals),
                    n_candidate=len(c_vals),
                    warnings=tuple(warnings),
                )
            )

        return StatisticalComparisonReport(
            baseline_id=base_id,
            candidate_id=cand_id,
            alpha=alpha,
            correction=correction,
            metrics=tuple(comparisons),
        )
