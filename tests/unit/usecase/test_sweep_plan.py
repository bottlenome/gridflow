"""Tests for UseCase-layer sweep domain types.

Spec references:
    * phase1_result.md §7.13.1 — ideal design for ``gridflow sweep``.
    * docs/mvp_scenario_v2.md §5.2 — SweepPlan YAML schema example.
    * CLAUDE.md §0.1 — all domain types must be frozen, hashable, and
      carry params as ``tuple[tuple[str, object], ...]``.

TDD Unit A-i: drive the (yet unimplemented) ``SweepPlan``, ``ParamAxis``
hierarchy, and ``SweepResult`` so we can build the rest of the sweep
use-case on top of solid type foundations.
"""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridflow.usecase.sweep_plan import (
    ChildAssignment,
    ChoiceAxis,
    RandomSampleAxis,
    RangeAxis,
    SweepPlan,
    SweepResult,
)


class TestRangeAxis:
    def test_expands_inclusive_start_exclusive_stop(self) -> None:
        axis = RangeAxis(name="pv_kw", start=100.0, stop=500.0, step=100.0)
        assert axis.sample() == (100.0, 200.0, 300.0, 400.0)

    def test_is_frozen(self) -> None:
        axis = RangeAxis(name="x", start=0.0, stop=3.0, step=1.0)
        with pytest.raises((AttributeError, Exception)):
            axis.name = "y"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        a = RangeAxis(name="x", start=0.0, stop=3.0, step=1.0)
        b = RangeAxis(name="x", start=0.0, stop=3.0, step=1.0)
        assert {a, b} == {a}

    def test_step_must_be_positive(self) -> None:
        with pytest.raises(ValueError, match="step"):
            RangeAxis(name="x", start=0.0, stop=1.0, step=0.0)
        with pytest.raises(ValueError, match="step"):
            RangeAxis(name="x", start=0.0, stop=1.0, step=-1.0)

    def test_start_less_than_stop(self) -> None:
        with pytest.raises(ValueError, match="start"):
            RangeAxis(name="x", start=1.0, stop=1.0, step=0.1)


class TestChoiceAxis:
    def test_returns_values_verbatim(self) -> None:
        axis = ChoiceAxis(name="bus", values=("671", "675", "634"))
        assert axis.sample() == ("671", "675", "634")

    def test_rejects_empty_values(self) -> None:
        with pytest.raises(ValueError, match="values"):
            ChoiceAxis(name="x", values=())

    def test_is_frozen_and_hashable(self) -> None:
        a = ChoiceAxis(name="x", values=("a", "b"))
        b = ChoiceAxis(name="x", values=("a", "b"))
        assert {a, b} == {a}


class TestRandomSampleAxis:
    def test_uniform_sampling_deterministic_by_seed(self) -> None:
        axis = RandomSampleAxis(
            name="pv_kw",
            low=100.0,
            high=500.0,
            n_samples=5,
            seed=42,
        )
        first = axis.sample()
        assert len(first) == 5
        assert all(100.0 <= v < 500.0 for v in first)
        second = axis.sample()
        assert first == second  # deterministic (seed)

    def test_different_seeds_produce_different_samples(self) -> None:
        a = RandomSampleAxis(name="x", low=0.0, high=1.0, n_samples=10, seed=1).sample()
        b = RandomSampleAxis(name="x", low=0.0, high=1.0, n_samples=10, seed=2).sample()
        assert a != b

    def test_rejects_low_geq_high(self) -> None:
        with pytest.raises(ValueError, match="low"):
            RandomSampleAxis(name="x", low=1.0, high=1.0, n_samples=5, seed=0)

    def test_rejects_non_positive_samples(self) -> None:
        with pytest.raises(ValueError, match="n_samples"):
            RandomSampleAxis(name="x", low=0.0, high=1.0, n_samples=0, seed=0)


class TestRandomChoiceAxis:
    """RandomSampleAxis also supports categorical sampling via ``values``."""

    def test_values_only_random_choice(self) -> None:
        """When ``values`` is given instead of (low, high), the axis samples
        uniformly from the discrete set with replacement."""
        axis = RandomSampleAxis(
            name="bus",
            values=("671", "675", "634"),
            n_samples=10,
            seed=42,
        )
        samples = axis.sample()
        assert len(samples) == 10
        assert all(v in {"671", "675", "634"} for v in samples)

    def test_categorical_deterministic_by_seed(self) -> None:
        a = RandomSampleAxis(name="x", values=("a", "b", "c"), n_samples=5, seed=1).sample()
        b = RandomSampleAxis(name="x", values=("a", "b", "c"), n_samples=5, seed=1).sample()
        assert a == b

    def test_cannot_set_both_numeric_and_categorical(self) -> None:
        with pytest.raises(ValueError, match="either"):
            RandomSampleAxis(
                name="x",
                low=0.0,
                high=1.0,
                values=("a",),
                n_samples=1,
                seed=0,
            )


class TestSweepPlan:
    def test_basic_construction(self) -> None:
        plan = SweepPlan(
            sweep_id="my_sweep",
            base_pack_id="ieee13@1.0.0",
            axes=(
                RangeAxis(name="pv_kw", start=100.0, stop=500.0, step=100.0),
                ChoiceAxis(name="pv_bus", values=("671", "675")),
            ),
            aggregator_name="statistics",
            seed=42,
        )
        assert plan.sweep_id == "my_sweep"
        assert len(plan.axes) == 2
        assert plan.aggregator_name == "statistics"

    def test_is_frozen(self) -> None:
        plan = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(RangeAxis(name="x", start=0.0, stop=1.0, step=0.5),),
            aggregator_name="statistics",
        )
        with pytest.raises((AttributeError, Exception)):
            plan.sweep_id = "other"  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        a = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(ChoiceAxis(name="x", values=("a",)),),
            aggregator_name="statistics",
        )
        b = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(ChoiceAxis(name="x", values=("a",)),),
            aggregator_name="statistics",
        )
        assert hash(a) == hash(b)

    def test_empty_axes_rejected(self) -> None:
        with pytest.raises(ValueError, match="axes"):
            SweepPlan(
                sweep_id="s",
                base_pack_id="p@1",
                axes=(),
                aggregator_name="statistics",
            )

    def test_duplicate_axis_names_rejected(self) -> None:
        with pytest.raises(ValueError, match="duplicate"):
            SweepPlan(
                sweep_id="s",
                base_pack_id="p@1",
                axes=(
                    ChoiceAxis(name="x", values=("a",)),
                    ChoiceAxis(name="x", values=("b",)),
                ),
                aggregator_name="statistics",
            )


class TestSweepPlanExpand:
    """``SweepPlan.expand`` enumerates parameter assignments for each child run.

    For non-random axes the expansion is the cartesian product. For random
    axes the expansion is zip-wise (i.e. 500 samples * 500 samples = 500
    assignments, not 500 * 500 = 250k).
    """

    def test_deterministic_cartesian_product(self) -> None:
        plan = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(
                ChoiceAxis(name="bus", values=("671", "675")),
                RangeAxis(name="kw", start=100.0, stop=301.0, step=100.0),
            ),
            aggregator_name="statistics",
        )
        assignments = plan.expand()
        # 2 buses * 3 kw = 6 combinations
        assert len(assignments) == 6
        bus_kw = {(dict(a.pack_params)["bus"], dict(a.pack_params)["kw"]) for a in assignments}
        assert bus_kw == {
            ("671", 100.0),
            ("671", 200.0),
            ("671", 300.0),
            ("675", 100.0),
            ("675", 200.0),
            ("675", 300.0),
        }

    def test_random_axes_zipped(self) -> None:
        plan = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(
                RandomSampleAxis(name="bus", values=("671", "675", "634"), n_samples=10, seed=1),
                RandomSampleAxis(name="kw", low=100.0, high=500.0, n_samples=10, seed=2),
            ),
            aggregator_name="statistics",
        )
        assignments = plan.expand()
        assert len(assignments) == 10  # zipped, not cartesian

    def test_cannot_mix_random_counts(self) -> None:
        with pytest.raises(ValueError, match="n_samples"):
            SweepPlan(
                sweep_id="s",
                base_pack_id="p@1",
                axes=(
                    RandomSampleAxis(name="a", values=("x",), n_samples=5, seed=1),
                    RandomSampleAxis(name="b", low=0.0, high=1.0, n_samples=10, seed=2),
                ),
                aggregator_name="statistics",
            )

    def test_mixed_cartesian_and_random(self) -> None:
        """Random axes zip internally; the result zips further with cartesian
        axes (= cartesian x zipped-random)."""
        plan = SweepPlan(
            sweep_id="s",
            base_pack_id="p@1",
            axes=(
                ChoiceAxis(name="solver", values=("opendss", "pandapower")),
                RandomSampleAxis(name="bus", values=("671", "675"), n_samples=3, seed=1),
                RandomSampleAxis(name="kw", low=100.0, high=500.0, n_samples=3, seed=2),
            ),
            aggregator_name="statistics",
        )
        assignments = plan.expand()
        # 2 solvers * 3 random samples = 6
        assert len(assignments) == 6


class TestSweepResult:
    def test_basic_construction(self) -> None:
        result = SweepResult(
            sweep_id="s",
            base_pack_id="p@1",
            plan_hash="abc123",
            experiment_ids=("exp-1", "exp-2"),
            aggregated_metrics=(("voltage_deviation_mean", 0.05),),
            per_experiment_metrics=(
                (("voltage_deviation", 0.04),),
                (("voltage_deviation", 0.06),),
            ),
            assignments=(
                ChildAssignment(pack_params=(("pv_kw", 100.0),)),
                ChildAssignment(pack_params=(("pv_kw", 200.0),)),
            ),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            elapsed_s=1.23,
        )
        assert result.sweep_id == "s"
        assert result.experiment_ids == ("exp-1", "exp-2")
        assert len(result.per_experiment_metrics) == 2
        assert result.per_experiment_metrics[0] == (("voltage_deviation", 0.04),)
        assert result.assignments[1].pack_params == (("pv_kw", 200.0),)

    def test_is_frozen(self) -> None:
        r = SweepResult(
            sweep_id="s",
            base_pack_id="p@1",
            plan_hash="h",
            experiment_ids=(),
            aggregated_metrics=(),
            per_experiment_metrics=(),
            assignments=(),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            elapsed_s=0.0,
        )
        with pytest.raises((AttributeError, Exception)):
            r.sweep_id = "other"  # type: ignore[misc]

    def test_to_dict_roundtrip_shape(self) -> None:
        r = SweepResult(
            sweep_id="s",
            base_pack_id="p@1",
            plan_hash="h",
            experiment_ids=("e1",),
            aggregated_metrics=(("m1", 1.0),),
            per_experiment_metrics=((("m1", 1.0),),),
            assignments=(ChildAssignment(pack_params=(("pv_kw", 100.0),)),),
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            elapsed_s=1.0,
        )
        d = r.to_dict()
        assert d["sweep_id"] == "s"
        assert d["base_pack_id"] == "p@1"
        assert d["experiment_ids"] == ["e1"]
        assert d["aggregated_metrics"] == {"m1": 1.0}
        assert d["per_experiment_metrics"] == [{"m1": 1.0}]
        assert d["assignments"] == [{"pack_params": {"pv_kw": 100.0}, "metric_params": {}}]
        assert d["elapsed_s"] == 1.0

    def test_length_mismatch_raises(self) -> None:
        with pytest.raises(ValueError, match="per_experiment_metrics length"):
            SweepResult(
                sweep_id="s",
                base_pack_id="p@1",
                plan_hash="h",
                experiment_ids=("e1", "e2"),
                aggregated_metrics=(),
                per_experiment_metrics=((("m", 1.0),),),
                assignments=(
                    ChildAssignment(pack_params=(("pv_kw", 1.0),)),
                    ChildAssignment(pack_params=(("pv_kw", 2.0),)),
                ),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                elapsed_s=0.0,
            )
        with pytest.raises(ValueError, match="assignments length"):
            SweepResult(
                sweep_id="s",
                base_pack_id="p@1",
                plan_hash="h",
                experiment_ids=("e1",),
                aggregated_metrics=(),
                per_experiment_metrics=((("m", 1.0),),),
                assignments=(),
                created_at=datetime(2026, 1, 1, tzinfo=UTC),
                elapsed_s=0.0,
            )
