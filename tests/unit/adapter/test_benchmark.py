"""Tests for BenchmarkHarness + metric calculators + ReportGenerator."""

from __future__ import annotations

import json
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.adapter.benchmark import BenchmarkHarness, ReportGenerator
from gridflow.adapter.benchmark.metrics import RuntimeMetric, VoltageDeviationMetric
from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.error import BenchmarkError
from gridflow.domain.result import NodeResult
from gridflow.usecase.result import ExperimentResult


def _result(experiment_id: str, voltages: tuple[float, ...], elapsed: float) -> ExperimentResult:
    meta = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="pack",
        connector="opendss",
    )
    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=meta,
        node_results=(NodeResult(node_id="all", voltages=voltages),),
        elapsed_s=elapsed,
    )


class TestVoltageDeviationMetric:
    def test_zero_for_nominal(self) -> None:
        metric = VoltageDeviationMetric()
        assert metric.calculate(_result("e", (1.0, 1.0, 1.0), 0.5)) == 0.0

    def test_nonzero_for_deviation(self) -> None:
        metric = VoltageDeviationMetric()
        v = metric.calculate(_result("e", (0.9, 1.1), 0.5))
        assert v == pytest.approx(0.1, abs=1e-9)

    def test_empty_returns_zero(self) -> None:
        meta = ExperimentMetadata(
            experiment_id="e",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            scenario_pack_id="p",
            connector="opendss",
        )
        empty = ExperimentResult(experiment_id="e", metadata=meta)
        assert VoltageDeviationMetric().calculate(empty) == 0.0


class TestRuntimeMetric:
    def test_returns_elapsed(self) -> None:
        assert RuntimeMetric().calculate(_result("e", (1.0,), 1.5)) == 1.5


class TestBenchmarkHarness:
    def test_evaluate(self) -> None:
        harness = BenchmarkHarness()
        summary = harness.evaluate(_result("e1", (1.0, 0.98), 0.5))
        names = dict(summary.values)
        assert "voltage_deviation" in names
        assert "runtime" in names
        assert names["runtime"] == 0.5

    def test_compare(self) -> None:
        harness = BenchmarkHarness()
        base = _result("e1", (1.0, 1.0), 1.0)
        cand = _result("e2", (0.9, 1.1), 0.5)
        report = harness.compare(base, cand)
        assert report.baseline_id == "e1"
        assert report.candidate_id == "e2"
        assert len(report.diffs) == 2

    def test_empty_metrics_rejected(self) -> None:
        harness = BenchmarkHarness(metrics=())
        with pytest.raises(BenchmarkError):
            harness.evaluate(_result("e", (1.0,), 0.1))


class TestReportGenerator:
    def test_write_comparison_json(self, tmp_path: Path) -> None:
        harness = BenchmarkHarness()
        report = harness.compare(
            _result("e1", (1.0, 1.0), 1.0),
            _result("e2", (0.9, 1.1), 0.5),
        )
        gen = ReportGenerator()
        target = tmp_path / "reports" / "cmp.json"
        gen.write_comparison(report, target)
        data = json.loads(target.read_text(encoding="utf-8"))
        assert data["baseline"] == "e1"
        assert data["candidate"] == "e2"

    def test_render_comparison_text(self) -> None:
        harness = BenchmarkHarness()
        report = harness.compare(
            _result("e1", (1.0,), 1.0),
            _result("e2", (0.95,), 0.8),
        )
        text = ReportGenerator().render_comparison_text(report)
        assert "e1" in text and "e2" in text
        assert "voltage_deviation" in text


def _vgroup(prefix: str, voltages_per_rep: list[float]) -> list[ExperimentResult]:
    """One-node experiments; voltage_deviation of rep i is |voltages[i] - 1.0|."""
    return [_result(f"{prefix}{i}", (v,), 0.5 + 0.01 * i) for i, v in enumerate(voltages_per_rep)]


class TestCompareGroups:
    """Issue #18: replicate-aware statistical verdict."""

    _voltage_only = None  # sentinel; built per-test to keep metric set controlled

    def _harness(self) -> BenchmarkHarness:
        return BenchmarkHarness(metrics=(VoltageDeviationMetric(),))

    def test_clear_separation_is_significant(self) -> None:
        base = _vgroup("b", [0.90, 0.89, 0.88, 0.87])  # dev ~0.10-0.13
        cand = _vgroup("c", [0.99, 0.98, 0.97, 0.96])  # dev ~0.01-0.04
        report = self._harness().compare_groups(base, cand, seed=1)
        m = report.metrics[0]
        assert m.name == "voltage_deviation"
        assert m.significant is True
        assert m.p_value_adjusted is not None and m.p_value_adjusted < 0.05
        assert m.effect_size is not None
        assert m.baseline_ci is not None and m.candidate_ci is not None
        assert report.any_significant is True

    def test_overlapping_groups_not_significant(self) -> None:
        base = _vgroup("b", [0.95, 0.94, 0.93, 0.92])
        cand = _vgroup("c", [0.945, 0.935, 0.925, 0.915])
        report = self._harness().compare_groups(base, cand, seed=1)
        assert report.metrics[0].significant is False
        assert report.any_significant is False

    def test_insufficient_replicates_guarded(self) -> None:
        # 1 vs 1 — the delta may look big but variance is unknown.
        base = _vgroup("b", [0.90])
        cand = _vgroup("c", [0.99])
        report = self._harness().compare_groups(base, cand)
        m = report.metrics[0]
        assert m.significant is False
        assert "insufficient_replicates" in m.warnings
        assert m.p_value is None

    def test_zero_variance_is_not_significant(self) -> None:
        # The try11 trap: both groups internally constant. Means differ, but
        # there is no run-to-run variation to generalise from.
        base = _vgroup("b", [0.90, 0.90, 0.90])  # dev 0.10 each, variance 0
        cand = _vgroup("c", [0.80, 0.80, 0.80])  # dev 0.20 each, variance 0
        report = self._harness().compare_groups(base, cand)
        m = report.metrics[0]
        assert m.delta != 0.0
        assert m.significant is False
        assert "zero_variance" in m.warnings

    def test_runtime_is_informational_never_significant(self) -> None:
        # Full harness includes runtime; give runtime a clean separation and
        # confirm it is still not called significant.
        base = [_result(f"b{i}", (0.9 - 0.01 * i,), 0.10 + 0.01 * i) for i in range(4)]
        cand = [_result(f"c{i}", (0.99 - 0.01 * i,), 5.00 + 0.01 * i) for i in range(4)]
        report = BenchmarkHarness().compare_groups(base, cand, seed=1)
        runtime = next(m for m in report.metrics if m.name == "runtime")
        assert runtime.informational is True
        assert runtime.significant is False

    def test_to_dict_is_loader_compatible(self) -> None:
        base = _vgroup("b", [0.90, 0.89, 0.88, 0.87])
        cand = _vgroup("c", [0.99, 0.98, 0.97, 0.96])
        report = self._harness().compare_groups(base, cand, seed=1)
        data = report.to_dict()
        entry = data["metrics"][0]
        # Loader contract (#23): baseline/candidate + {side}_ci + objective.
        assert {"baseline", "candidate", "delta", "objective"} <= entry.keys()
        assert "baseline_ci" in entry and "candidate_ci" in entry
        assert {"p_value", "p_value_adjusted", "effect_size", "significant"} <= entry.keys()

    def test_empty_side_rejected(self) -> None:
        with pytest.raises(BenchmarkError):
            self._harness().compare_groups([], _vgroup("c", [0.9, 0.8]))
