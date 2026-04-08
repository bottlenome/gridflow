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
