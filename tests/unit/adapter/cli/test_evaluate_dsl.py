"""Tests for the inline-DSL parsers used by ``gridflow evaluate``."""

from __future__ import annotations

import pytest

from gridflow.adapter.cli.evaluate_dsl import (
    EvaluateDSLError,
    parse_metric_spec,
    parse_parameter_sweep,
)


class TestParseMetricSpec:
    def test_builtin_only(self) -> None:
        spec = parse_metric_spec("voltage_deviation")
        assert spec.name == "voltage_deviation"
        assert spec.plugin is None
        assert spec.kwargs == ()

    def test_plugin_no_kwargs(self) -> None:
        spec = parse_metric_spec("hc:my_pkg.mymod:HostingCapacityMetric")
        assert spec.name == "hc"
        assert spec.plugin == "my_pkg.mymod:HostingCapacityMetric"
        assert spec.kwargs == ()

    def test_plugin_with_kwargs(self) -> None:
        spec = parse_metric_spec("hc:my_pkg.mymod:HostingCapacityMetric(voltage_low=0.95,voltage_high=1.05)")
        assert spec.name == "hc"
        assert spec.plugin == "my_pkg.mymod:HostingCapacityMetric"
        # Sorted, with float coercion.
        assert dict(spec.kwargs) == {"voltage_high": 1.05, "voltage_low": 0.95}

    def test_kwargs_coerce_int_and_bool(self) -> None:
        spec = parse_metric_spec("m:pkg:M(n=3,enabled=true,label=foo)")
        kw = dict(spec.kwargs)
        assert kw["n"] == 3
        assert kw["enabled"] is True
        assert kw["label"] == "foo"

    def test_empty_spec_rejected(self) -> None:
        with pytest.raises(EvaluateDSLError, match="empty"):
            parse_metric_spec("")

    def test_paren_without_close_rejected(self) -> None:
        with pytest.raises(EvaluateDSLError, match="closing"):
            parse_metric_spec("hc:pkg:Cls(k=1")

    def test_kwargs_missing_equals_rejected(self) -> None:
        with pytest.raises(EvaluateDSLError, match="missing '='"):
            parse_metric_spec("hc:pkg:Cls(novalue)")

    def test_builtin_with_kwargs_rejected(self) -> None:
        with pytest.raises(EvaluateDSLError, match="cannot carry kwargs"):
            parse_metric_spec("voltage_deviation(low=0.9)")


class TestParseParameterSweep:
    def test_basic_grid(self) -> None:
        sweep = parse_parameter_sweep("voltage_low:0.90:0.95:11")
        assert sweep.kwarg_name == "voltage_low"
        assert sweep.start == pytest.approx(0.90)
        assert sweep.stop == pytest.approx(0.95)
        assert sweep.n_points == 11
        grid = sweep.grid()
        assert len(grid) == 11
        assert grid[0] == pytest.approx(0.90)
        assert grid[-1] == pytest.approx(0.95)

    def test_n_points_minimum_two(self) -> None:
        with pytest.raises(ValueError, match="n_points"):
            parse_parameter_sweep("kw:0.0:1.0:1")

    def test_stop_must_exceed_start(self) -> None:
        with pytest.raises(ValueError, match="stop"):
            parse_parameter_sweep("kw:1.0:1.0:5")

    def test_part_count_validated(self) -> None:
        with pytest.raises(EvaluateDSLError, match="expected"):
            parse_parameter_sweep("kw:0:1")
