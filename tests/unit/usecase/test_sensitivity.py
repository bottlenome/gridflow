"""Tests for :class:`SensitivityAnalyzer` — REQ-F-016 / 03b §3.7."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import (
    NodeResult,
    SensitivityResult,
    VoltageSensitivityMatrix,
)
from gridflow.domain.util.params import as_params
from gridflow.usecase.result import ExperimentResult
from gridflow.usecase.sensitivity import (
    SensitivityAnalysisError,
    SensitivityAnalyzer,
)

# Module-level metric the plugin loader can find.


class _ThresholdedFraction:
    """Fraction of voltages below ``voltage_low`` — same as test_evaluation.py
    fixture but kept here for module locality."""

    name = "thresholded_fraction"
    unit = "ratio"

    def __init__(self, *, voltage_low: float = 0.95) -> None:
        self.voltage_low = voltage_low

    def calculate(self, result: ExperimentResult) -> float:
        voltages = tuple(v for nr in result.node_results for v in nr.voltages)
        if not voltages:
            return 0.0
        return sum(1 for v in voltages if v < self.voltage_low) / len(voltages)


def _make_experiment(
    experiment_id: str,
    voltages: tuple[float, ...],
    *,
    pv_bus: object | None = None,
    pv_kw: float = 0.0,
) -> ExperimentResult:
    parameters: dict[str, object] = {}
    if pv_bus is not None:
        parameters["pv_bus"] = pv_bus
    if pv_kw:
        parameters["pv_kw"] = pv_kw
    meta = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="base@1.0.0",
        connector="fake",
        parameters=as_params(parameters),
    )
    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=meta,
        steps=(),
        node_results=(NodeResult(node_id="net", voltages=voltages),),
        metrics=(),
        elapsed_s=0.1,
    )


PLUGIN_SPEC = f"{_ThresholdedFraction.__module__}:_ThresholdedFraction"


class TestSensitivityResult:
    def test_basic_shape(self) -> None:
        sr = SensitivityResult(
            feeder_id="f",
            parameter_name="voltage_low",
            parameter_values=(0.9, 0.95),
            metric_name="m",
            metric_values=(0.1, 0.3),
        )
        assert sr.parameter_values == (0.9, 0.95)
        assert sr.metric_values == (0.1, 0.3)
        assert sr.confidence_lower == ()
        assert sr.confidence_upper == ()

    def test_length_mismatch_rejected(self) -> None:
        with pytest.raises(Exception, match="metric_values"):
            SensitivityResult(
                feeder_id="f",
                parameter_name="x",
                parameter_values=(0.9, 0.95),
                metric_name="m",
                metric_values=(0.1,),
            )

    def test_to_dict_roundtrip_shape(self) -> None:
        sr = SensitivityResult(
            feeder_id="f",
            parameter_name="x",
            parameter_values=(0.9,),
            metric_name="m",
            metric_values=(0.1,),
        )
        d = sr.to_dict()
        assert d["parameter_values"] == [0.9]
        assert d["metric_values"] == [0.1]


class TestVoltageSensitivityMatrix:
    def test_square_matrix_ok(self) -> None:
        vsm = VoltageSensitivityMatrix(
            bus_ids=("a", "b"),
            matrix=((1.0, 0.0), (0.5, 1.0)),
            max_singular_value=1.5,
        )
        assert vsm.bus_ids == ("a", "b")
        assert vsm.matrix[1][0] == 0.5

    def test_non_square_rejected(self) -> None:
        with pytest.raises(Exception, match="matrix"):
            VoltageSensitivityMatrix(
                bus_ids=("a", "b"),
                matrix=((1.0,), (1.0,)),
                max_singular_value=0.0,
            )


class TestSensitivityAnalyzerAnalyze:
    def test_threshold_curve_monotone(self) -> None:
        # Voltages = (0.92, 0.94, 0.96, 0.98). Fraction below threshold T:
        #   T=0.93 → 1/4
        #   T=0.95 → 2/4
        #   T=0.97 → 3/4
        exp = _make_experiment("e1", (0.92, 0.94, 0.96, 0.98))
        analyzer = SensitivityAnalyzer()
        result = analyzer.analyze(
            experiments=[exp],
            parameter_name="voltage_low",
            parameter_grid=[0.93, 0.95, 0.97],
            metric_plugin=PLUGIN_SPEC,
            feeder_id="ieee13",
        )
        assert result.feeder_id == "ieee13"
        assert result.parameter_name == "voltage_low"
        assert result.parameter_values == (0.93, 0.95, 0.97)
        assert result.metric_name == "thresholded_fraction"
        assert result.metric_values == pytest.approx((0.25, 0.5, 0.75))

    def test_empty_experiments_rejected(self) -> None:
        with pytest.raises(SensitivityAnalysisError, match="experiments"):
            SensitivityAnalyzer().analyze(
                experiments=[],
                parameter_name="voltage_low",
                parameter_grid=[0.9],
                metric_plugin=PLUGIN_SPEC,
            )

    def test_empty_parameter_grid_rejected(self) -> None:
        exp = _make_experiment("e1", (0.95,))
        with pytest.raises(SensitivityAnalysisError, match="parameter_grid"):
            SensitivityAnalyzer().analyze(
                experiments=[exp],
                parameter_name="voltage_low",
                parameter_grid=[],
                metric_plugin=PLUGIN_SPEC,
            )

    def test_parameter_in_base_kwargs_rejected(self) -> None:
        exp = _make_experiment("e1", (0.95,))
        with pytest.raises(SensitivityAnalysisError, match="must not also appear"):
            SensitivityAnalyzer().analyze(
                experiments=[exp],
                parameter_name="voltage_low",
                parameter_grid=[0.9, 0.95],
                metric_plugin=PLUGIN_SPEC,
                metric_kwargs_base={"voltage_low": 0.95},
            )

    def test_bootstrap_emits_ci_bounds(self) -> None:
        exps = [_make_experiment(f"e{i}", (0.92, 0.94, 0.96)) for i in range(5)]
        result = SensitivityAnalyzer().analyze(
            experiments=exps,
            parameter_name="voltage_low",
            parameter_grid=[0.93, 0.95],
            metric_plugin=PLUGIN_SPEC,
            bootstrap_n=20,
            bootstrap_seed=42,
        )
        # Same data → identical metric per resample → CI collapses to point.
        assert result.confidence_lower == pytest.approx(result.metric_values)
        assert result.confidence_upper == pytest.approx(result.metric_values)


class TestAnalyzeVoltageMatrix:
    def test_baseline_required(self) -> None:
        # All experiments have pv_kw > 0 → no baseline → reject.
        e1 = _make_experiment("e1", (1.0, 1.0), pv_bus=0, pv_kw=100.0)
        with pytest.raises(SensitivityAnalysisError, match="baseline"):
            SensitivityAnalyzer().analyze_voltage_matrix(experiments=[e1])

    def test_dv_dp_estimated_from_baseline_diff(self) -> None:
        # Baseline V = (1.00, 1.00); injecting 100 kW at bus 0 yields
        # voltages (1.05, 1.02). Expected sensitivity column 0 = (0.0005, 0.0002).
        baseline = _make_experiment("base", (1.00, 1.00), pv_bus=0, pv_kw=0.0)
        injected = _make_experiment("inj", (1.05, 1.02), pv_bus=0, pv_kw=100.0)
        vsm = SensitivityAnalyzer().analyze_voltage_matrix(experiments=[baseline, injected])
        assert vsm.bus_ids == ("bus_0", "bus_1")
        # Column 0 (injection at bus 0): row 0 = 0.0005, row 1 = 0.0002.
        assert vsm.matrix[0][0] == pytest.approx(0.0005)
        assert vsm.matrix[1][0] == pytest.approx(0.0002)
        # Column 1 untouched (no injection at bus 1) → all zeros.
        assert vsm.matrix[0][1] == pytest.approx(0.0)
        assert vsm.matrix[1][1] == pytest.approx(0.0)
        # Largest singular value is positive (matrix is non-zero).
        assert vsm.max_singular_value > 0.0

    def test_non_integer_pv_bus_rejected(self) -> None:
        baseline = _make_experiment("base", (1.0,), pv_kw=0.0)
        injected = _make_experiment("inj", (1.05,), pv_bus="loadbus", pv_kw=100.0)
        with pytest.raises(SensitivityAnalysisError, match="integer pv_bus"):
            SensitivityAnalyzer().analyze_voltage_matrix(experiments=[baseline, injected])
