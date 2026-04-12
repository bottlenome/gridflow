"""Tests for the SweepPlan YAML loader.

Spec: ``docs/mvp_scenario_v2.md`` §5.2 — sweep_plan.yaml schema example.

The loader is intentionally placed in usecase (not adapter) so any
loader of YAML / JSON / dict-like sources can build a SweepPlan via the
same construction path.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gridflow.usecase.sweep_plan import (
    ChoiceAxis,
    RandomSampleAxis,
    RangeAxis,
    SweepPlan,
)
from gridflow.usecase.sweep_yaml_loader import (
    SweepPlanLoadError,
    load_sweep_plan_from_dict,
    load_sweep_plan_from_yaml,
)


class TestLoadFromDict:
    def test_minimal_range_plan(self) -> None:
        plan = load_sweep_plan_from_dict(
            {
                "sweep": {
                    "id": "demo",
                    "base_pack_id": "ieee13@1.0.0",
                    "aggregator": "statistics",
                    "seed": 42,
                },
                "axes": [
                    {"name": "pv_kw", "type": "range", "start": 100, "stop": 500, "step": 100},
                ],
            }
        )
        assert isinstance(plan, SweepPlan)
        assert plan.sweep_id == "demo"
        assert plan.base_pack_id == "ieee13@1.0.0"
        assert plan.seed == 42
        assert len(plan.axes) == 1
        assert isinstance(plan.axes[0], RangeAxis)

    def test_choice_axis(self) -> None:
        plan = load_sweep_plan_from_dict(
            {
                "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                "axes": [{"name": "bus", "type": "choice", "values": ["671", "675"]}],
            }
        )
        axis = plan.axes[0]
        assert isinstance(axis, ChoiceAxis)
        assert axis.values == ("671", "675")

    def test_random_uniform_axis(self) -> None:
        plan = load_sweep_plan_from_dict(
            {
                "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                "axes": [
                    {
                        "name": "pv_kw",
                        "type": "random_uniform",
                        "low": 100,
                        "high": 500,
                        "n_samples": 10,
                        "seed": 1,
                    },
                ],
            }
        )
        axis = plan.axes[0]
        assert isinstance(axis, RandomSampleAxis)
        assert axis.low == 100.0
        assert axis.high == 500.0
        assert axis.n_samples == 10

    def test_random_choice_axis(self) -> None:
        plan = load_sweep_plan_from_dict(
            {
                "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                "axes": [
                    {
                        "name": "bus",
                        "type": "random_choice",
                        "values": ["a", "b", "c"],
                        "n_samples": 5,
                        "seed": 1,
                    },
                ],
            }
        )
        axis = plan.axes[0]
        assert isinstance(axis, RandomSampleAxis)
        assert axis.values == ("a", "b", "c")
        assert axis.n_samples == 5

    def test_multiple_axes(self) -> None:
        plan = load_sweep_plan_from_dict(
            {
                "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                "axes": [
                    {"name": "bus", "type": "choice", "values": ["671", "675"]},
                    {"name": "pv_kw", "type": "range", "start": 100, "stop": 400, "step": 100},
                ],
            }
        )
        assert len(plan.axes) == 2

    def test_missing_sweep_section(self) -> None:
        with pytest.raises(SweepPlanLoadError, match="sweep"):
            load_sweep_plan_from_dict({"axes": []})

    def test_missing_axes_section(self) -> None:
        with pytest.raises(SweepPlanLoadError, match="axes"):
            load_sweep_plan_from_dict({"sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"}})

    def test_unknown_axis_type(self) -> None:
        with pytest.raises(SweepPlanLoadError, match="type"):
            load_sweep_plan_from_dict(
                {
                    "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                    "axes": [{"name": "x", "type": "exponential"}],
                }
            )

    def test_axis_missing_required_field(self) -> None:
        with pytest.raises(SweepPlanLoadError, match="start"):
            load_sweep_plan_from_dict(
                {
                    "sweep": {"id": "s", "base_pack_id": "p@1", "aggregator": "statistics"},
                    "axes": [{"name": "x", "type": "range", "stop": 5, "step": 1}],
                }
            )


class TestLoadFromYAMLFile:
    def test_loads_real_file(self, tmp_path: Path) -> None:
        path = tmp_path / "sweep.yaml"
        path.write_text(
            """
sweep:
  id: demo_yaml
  base_pack_id: ieee13@1.0.0
  aggregator: statistics
  seed: 42
axes:
  - name: pv_kw
    type: range
    start: 100
    stop: 500
    step: 100
""",
            encoding="utf-8",
        )
        plan = load_sweep_plan_from_yaml(path)
        assert plan.sweep_id == "demo_yaml"
        assert isinstance(plan.axes[0], RangeAxis)

    def test_missing_file_raises(self, tmp_path: Path) -> None:
        with pytest.raises(SweepPlanLoadError, match="not found"):
            load_sweep_plan_from_yaml(tmp_path / "nope.yaml")

    def test_malformed_yaml_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "bad.yaml"
        path.write_text("sweep: { id: demo\n", encoding="utf-8")  # unterminated
        with pytest.raises(SweepPlanLoadError):
            load_sweep_plan_from_yaml(path)
