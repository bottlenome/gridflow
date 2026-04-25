"""Tests for ``Evaluator`` and ``EvaluationPlan`` — §5.1.1 Option B.

Drives the post-processing ``gridflow evaluate`` flow: load a set of
already-simulated ExperimentResults, apply one or more metrics
(built-in or plugin with per-spec kwargs), and emit an
EvaluationResult carrying per-experiment metric values.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import NodeResult
from gridflow.usecase.evaluation import (
    EvaluationPlan,
    EvaluationResult,
    Evaluator,
    MetricSpec,
    ResultLoader,
    metric_spec_from_dict,
)
from gridflow.usecase.result import ExperimentResult

# ----------------------------------------------------------------- fakes


def _make_experiment_result(experiment_id: str, voltages: tuple[float, ...]) -> ExperimentResult:
    meta = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="base@1.0.0",
        connector="fake",
    )
    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=meta,
        steps=(),
        node_results=(NodeResult(node_id="n", voltages=voltages),),
        metrics=(),
        elapsed_s=0.1,
    )


class _InMemoryLoader(ResultLoader):
    """Loader that maps a synthetic path string to a pre-built result."""

    def __init__(self, mapping: dict[Path, ExperimentResult]) -> None:
        self._mapping = mapping

    def load(self, path: Path) -> ExperimentResult:
        return self._mapping[path]


# A threshold-parameterised metric — exactly the research use case
# motivating §5.1.1. Two instances with different ``voltage_low`` must
# coexist in one EvaluationPlan under different names.
class _ThresholdedFraction:
    """Fraction of voltages below ``voltage_low`` (a stand-in HCA metric)."""

    name = "thresholded_fraction"
    unit = "ratio"

    def __init__(self, *, voltage_low: float = 0.95) -> None:
        self.voltage_low = voltage_low

    def calculate(self, result: ExperimentResult) -> float:
        voltages = tuple(v for nr in result.node_results for v in nr.voltages)
        if not voltages:
            return 0.0
        return sum(1 for v in voltages if v < self.voltage_low) / len(voltages)


# ----------------------------------------------------------------- MetricSpec


class TestMetricSpec:
    def test_basic_construction(self) -> None:
        spec = MetricSpec(name="voltage_deviation")
        assert spec.name == "voltage_deviation"
        assert spec.plugin is None
        assert spec.kwargs == ()

    def test_with_plugin_and_kwargs(self) -> None:
        spec = MetricSpec(
            name="hc_090",
            plugin="mod:Cls",
            kwargs=(("voltage_low", 0.90),),
        )
        assert spec.plugin == "mod:Cls"
        assert dict(spec.kwargs) == {"voltage_low": 0.90}

    def test_empty_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            MetricSpec(name="")

    def test_is_hashable(self) -> None:
        spec = MetricSpec(name="m", plugin="mod:C", kwargs=(("k", 1),))
        assert len({spec, spec}) == 1

    def test_to_dict_roundtrip(self) -> None:
        spec = MetricSpec(name="hc", plugin="mod:C", kwargs=(("k", 0.9),))
        d = spec.to_dict()
        assert d == {"name": "hc", "plugin": "mod:C", "kwargs": {"k": 0.9}}


class TestMetricSpecFromDict:
    def test_minimal_builtin(self) -> None:
        spec = metric_spec_from_dict({"name": "voltage_deviation"})
        assert spec.plugin is None
        assert spec.kwargs == ()

    def test_with_plugin_and_kwargs(self) -> None:
        spec = metric_spec_from_dict(
            {
                "name": "hc_090",
                "plugin": "mod:C",
                "kwargs": {"voltage_low": 0.90, "confidence": 0.95},
            }
        )
        assert spec.plugin == "mod:C"
        # kwargs canonicalised as sorted tuple-of-tuples
        assert spec.kwargs == (("confidence", 0.95), ("voltage_low", 0.90))

    def test_invalid_kwargs_type_rejected(self) -> None:
        with pytest.raises(ValueError, match="kwargs"):
            metric_spec_from_dict({"name": "m", "kwargs": "oops"})

    def test_missing_name_rejected(self) -> None:
        with pytest.raises(ValueError, match="name"):
            metric_spec_from_dict({})


# ----------------------------------------------------------------- EvaluationPlan


class TestEvaluationPlan:
    def test_basic_construction(self) -> None:
        plan = EvaluationPlan(
            evaluation_id="e1",
            results=(Path("/tmp/exp1.json"), Path("/tmp/exp2.json")),
            metrics=(MetricSpec(name="voltage_deviation"),),
        )
        assert plan.evaluation_id == "e1"
        assert len(plan.results) == 2
        assert len(plan.metrics) == 1

    def test_empty_metrics_rejected(self) -> None:
        with pytest.raises(ValueError, match="metrics"):
            EvaluationPlan(evaluation_id="e1", results=(), metrics=())

    def test_duplicate_metric_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            EvaluationPlan(
                evaluation_id="e1",
                results=(Path("/tmp/x"),),
                metrics=(
                    MetricSpec(name="hc"),
                    MetricSpec(name="hc", plugin="mod:C"),
                ),
            )

    def test_plan_hash_stable(self) -> None:
        p1 = EvaluationPlan(
            evaluation_id="e1",
            results=(Path("/tmp/x"),),
            metrics=(MetricSpec(name="voltage_deviation"),),
        )
        p2 = EvaluationPlan(
            evaluation_id="e1",
            results=(Path("/tmp/x"),),
            metrics=(MetricSpec(name="voltage_deviation"),),
        )
        assert p1.plan_hash() == p2.plan_hash()

    def test_plan_hash_changes_with_kwargs(self) -> None:
        p1 = EvaluationPlan(
            evaluation_id="e1",
            results=(Path("/tmp/x"),),
            metrics=(MetricSpec(name="hc", plugin="mod:C", kwargs=(("k", 0.90),)),),
        )
        p2 = EvaluationPlan(
            evaluation_id="e1",
            results=(Path("/tmp/x"),),
            metrics=(MetricSpec(name="hc", plugin="mod:C", kwargs=(("k", 0.95),)),),
        )
        assert p1.plan_hash() != p2.plan_hash()


# ----------------------------------------------------------------- EvaluationResult


class TestEvaluationResult:
    """EvaluationResult.per_experiment_metrics is column-oriented
    (same shape as SweepResult.per_experiment_metrics)."""

    def test_metric_vector_length_must_match_experiments(self) -> None:
        with pytest.raises(ValueError, match=r"has 1 values but experiment_ids has 2"):
            EvaluationResult(
                evaluation_id="e1",
                plan_hash="h",
                experiment_ids=("e1", "e2"),
                per_experiment_metrics=(("m", (1.0,)),),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                elapsed_s=0.0,
            )

    def test_to_dict_shape(self) -> None:
        r = EvaluationResult(
            evaluation_id="e1",
            plan_hash="h",
            experiment_ids=("x1",),
            per_experiment_metrics=(("m", (0.5,)),),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            elapsed_s=1.0,
        )
        d = r.to_dict()
        assert d["evaluation_id"] == "e1"
        assert d["experiment_ids"] == ["x1"]
        # Column-oriented JSON: ``{metric_name: [v0, ...]}``.
        assert d["per_experiment_metrics"] == {"m": [0.5]}

    def test_metric_names_must_be_sorted_and_unique(self) -> None:
        with pytest.raises(ValueError, match="must be sorted"):
            EvaluationResult(
                evaluation_id="e1",
                plan_hash="h",
                experiment_ids=("x1",),
                per_experiment_metrics=(("z", (1.0,)), ("a", (2.0,))),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                elapsed_s=0.0,
            )
        with pytest.raises(ValueError, match="duplicate"):
            EvaluationResult(
                evaluation_id="e1",
                plan_hash="h",
                experiment_ids=("x1",),
                per_experiment_metrics=(("a", (1.0,)), ("a", (2.0,))),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                elapsed_s=0.0,
            )


# ----------------------------------------------------------------- Evaluator


class TestEvaluator:
    def test_builtin_metric_flow(self) -> None:
        # Two experiments, voltage_deviation = RMSE from 1.0 pu.
        r1 = _make_experiment_result("exp-1", (1.00, 0.95, 1.05))
        r2 = _make_experiment_result("exp-2", (1.00, 0.90, 1.10))
        loader = _InMemoryLoader({Path("/a/exp-1.json"): r1, Path("/a/exp-2.json"): r2})
        plan = EvaluationPlan(
            evaluation_id="eval-1",
            results=(Path("/a/exp-1.json"), Path("/a/exp-2.json")),
            metrics=(MetricSpec(name="voltage_deviation"),),
        )
        result = Evaluator(result_loader=loader).run(plan)
        assert result.experiment_ids == ("exp-1", "exp-2")
        # Column-oriented: one metric column with 2 per-experiment values.
        column_dict = dict(result.per_experiment_metrics)
        assert "voltage_deviation" in column_dict
        assert len(column_dict["voltage_deviation"]) == 2

    def test_same_plugin_two_kwargs_coexist(self) -> None:
        """The flagship §5.1.1 use case: one plugin, two kwargs, three
        output columns under caller-chosen names."""
        r1 = _make_experiment_result("exp-1", (0.94, 0.96, 0.98))
        loader = _InMemoryLoader({Path("/a/exp-1.json"): r1})
        plugin_spec = f"{_ThresholdedFraction.__module__}:_ThresholdedFraction"
        plan = EvaluationPlan(
            evaluation_id="eval-2",
            results=(Path("/a/exp-1.json"),),
            metrics=(
                MetricSpec(
                    name="frac_below_090",
                    plugin=plugin_spec,
                    kwargs=(("voltage_low", 0.90),),
                ),
                MetricSpec(
                    name="frac_below_095",
                    plugin=plugin_spec,
                    kwargs=(("voltage_low", 0.95),),
                ),
                MetricSpec(
                    name="frac_below_097",
                    plugin=plugin_spec,
                    kwargs=(("voltage_low", 0.97),),
                ),
            ),
        )
        result = Evaluator(result_loader=loader).run(plan)
        assert len(result.experiment_ids) == 1
        # Column-oriented: three metric columns, each with 1 per-experiment value.
        column_dict = dict(result.per_experiment_metrics)
        # voltages = (0.94, 0.96, 0.98):
        # < 0.90 → 0/3; < 0.95 → 1/3; < 0.97 → 2/3
        assert column_dict["frac_below_090"][0] == pytest.approx(0.0)
        assert column_dict["frac_below_095"][0] == pytest.approx(1 / 3)
        assert column_dict["frac_below_097"][0] == pytest.approx(2 / 3)

    def test_plan_hash_recorded(self) -> None:
        r1 = _make_experiment_result("exp-1", (1.0,))
        loader = _InMemoryLoader({Path("/a/exp-1.json"): r1})
        plan = EvaluationPlan(
            evaluation_id="eval-3",
            results=(Path("/a/exp-1.json"),),
            metrics=(MetricSpec(name="voltage_deviation"),),
        )
        result = Evaluator(result_loader=loader).run(plan)
        assert result.plan_hash == plan.plan_hash()
