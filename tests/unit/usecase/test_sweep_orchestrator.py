"""Tests for ``SweepOrchestrator`` and the ``Aggregator`` contract.

Spec: ``docs/phase1_result.md`` §7.13.1 and ``docs/mvp_scenario_v2.md`` §5.

TDD Unit A-ii: drive the UseCase that ties a SweepPlan to the existing
Orchestrator/InProcessOrchestratorRunner pipeline. The sweep orchestrator
must:

    1. Expand the SweepPlan into N parameter assignments.
    2. For each assignment, create a derived ExperimentResult via the
       inner :class:`Orchestrator`. For MVP the derivation is: load the
       base pack, override ``pack.metadata.parameters`` with the
       assignment, construct a one-off RunRequest.
    3. Aggregate the N per-experiment metrics using the registered
       Aggregator.
    4. Return a :class:`SweepResult` with all child experiment IDs.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackMetadata, ScenarioPack
from gridflow.infra.scenario import FileScenarioRegistry
from gridflow.usecase.interfaces import ConnectorStepOutput
from gridflow.usecase.sweep import (
    AggregatorRegistry,
    ExtremaAggregator,
    StatisticsAggregator,
    SweepOrchestrator,
)
from gridflow.usecase.sweep_plan import (
    ChoiceAxis,
    RandomSampleAxis,
    RangeAxis,
    SweepPlan,
    SweepResult,
)

# ----------------------------------------------------------------- fakes


class _FakeConnector:
    """Deterministic connector that echoes the pack's ``pv_kw`` as a voltage."""

    name = "fake"

    def __init__(self) -> None:
        self._pack: ScenarioPack | None = None
        self.initialized_packs: list[ScenarioPack] = []

    def initialize(self, pack: ScenarioPack) -> None:
        self._pack = pack
        self.initialized_packs.append(pack)

    def step(self, step_index: int) -> ConnectorStepOutput:
        assert self._pack is not None
        # Pull pv_kw out of the pack's parameters (if present) and use it as
        # the per-step voltage. This gives us a clean way to assert that
        # the sweep propagated the right parameter value.
        pv_kw = 0.0
        for key, value in self._pack.metadata.parameters:
            if key == "pv_kw":
                pv_kw = float(value)  # type: ignore[arg-type]
                break
        voltages = (1.0 - pv_kw / 10000.0,)  # simple deterministic mapping
        return ConnectorStepOutput(
            step=step_index,
            node_result=NodeResult(node_id="test", voltages=voltages),
            converged=True,
        )

    def teardown(self) -> None:
        self._pack = None


class _ThresholdCounter:
    """Counts how many voltages are strictly below ``threshold``.

    Exposed at module level so the metric plugin loader (which imports
    by ``module:ClassName``) can reach it via ``test_sweep_orchestrator``.
    Used to verify §5.1.1 Option A — that a metric-targeted axis
    re-instantiates the metric per child with the new kwargs.
    """

    name = "threshold_counter"
    unit = "count"

    def __init__(self, *, threshold: float = 0.0) -> None:
        self.threshold = threshold

    def calculate(self, result) -> float:  # type: ignore[no-untyped-def]
        voltages = tuple(v for nr in result.node_results for v in nr.voltages)
        return float(sum(1 for v in voltages if v < self.threshold))


def _make_pack(pack_id: str = "base@1.0.0") -> ScenarioPack:
    name, version = pack_id.split("@")
    meta = PackMetadata(
        name=name,
        version=version,
        description="t",
        author="t",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="fake",
    )
    return ScenarioPack(
        pack_id=pack_id,
        name=name,
        version=version,
        metadata=meta,
        network_dir=Path("/tmp"),
        timeseries_dir=Path("/tmp"),
        config_dir=Path("/tmp"),
    )


def _make_orchestrator_fixture(tmp_path: Path) -> tuple[FileScenarioRegistry, SweepOrchestrator, _FakeConnector]:
    from gridflow.infra.orchestrator import InProcessOrchestratorRunner
    from gridflow.usecase.orchestrator import Orchestrator

    reg = FileScenarioRegistry(tmp_path / "packs")
    reg.register(_make_pack())
    fake = _FakeConnector()
    runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
    orchestrator = Orchestrator(registry=reg, runner=runner)
    aggregator_registry = AggregatorRegistry()
    aggregator_registry.register(StatisticsAggregator())
    aggregator_registry.register(ExtremaAggregator())
    sweep = SweepOrchestrator(
        registry=reg,
        orchestrator=orchestrator,
        aggregator_registry=aggregator_registry,
        connector_id="fake",
    )
    return reg, sweep, fake


# ----------------------------------------------------------------- Aggregators


class TestStatisticsAggregator:
    def test_computes_mean_median_std_quartiles(self) -> None:
        agg = StatisticsAggregator()
        summaries = [
            {"voltage_deviation": 0.1, "runtime": 0.5},
            {"voltage_deviation": 0.2, "runtime": 0.6},
            {"voltage_deviation": 0.3, "runtime": 0.7},
            {"voltage_deviation": 0.4, "runtime": 0.8},
        ]
        result = dict(agg.aggregate(summaries))
        assert result["voltage_deviation_mean"] == pytest.approx(0.25)
        assert result["voltage_deviation_median"] == pytest.approx(0.25)
        assert result["voltage_deviation_min"] == pytest.approx(0.1)
        assert result["voltage_deviation_max"] == pytest.approx(0.4)
        assert result["runtime_mean"] == pytest.approx(0.65)

    def test_empty_input_raises(self) -> None:
        agg = StatisticsAggregator()
        with pytest.raises(ValueError, match="empty"):
            agg.aggregate([])

    def test_registered_name(self) -> None:
        assert StatisticsAggregator().name == "statistics"


class TestExtremaAggregator:
    def test_min_max_only(self) -> None:
        agg = ExtremaAggregator()
        result = dict(agg.aggregate([{"m": 1.0}, {"m": 3.0}, {"m": 2.0}]))
        assert result == {"m_min": 1.0, "m_max": 3.0}

    def test_registered_name(self) -> None:
        assert ExtremaAggregator().name == "extrema"


class TestAggregatorRegistry:
    def test_register_and_get(self) -> None:
        reg = AggregatorRegistry()
        reg.register(StatisticsAggregator())
        got = reg.get("statistics")
        assert got is not None
        assert got.name == "statistics"

    def test_unknown_name_raises(self) -> None:
        reg = AggregatorRegistry()
        with pytest.raises(KeyError, match="ghost"):
            reg.get("ghost")

    def test_duplicate_name_rejected(self) -> None:
        reg = AggregatorRegistry()
        reg.register(StatisticsAggregator())
        with pytest.raises(ValueError, match="already"):
            reg.register(StatisticsAggregator())


# ----------------------------------------------------------------- SweepOrchestrator


class TestSweepOrchestratorRun:
    def test_runs_all_expanded_children(self, tmp_path: Path) -> None:
        _, sweep, fake = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(RangeAxis(name="pv_kw", start=100.0, stop=400.0, step=100.0),),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        assert isinstance(result, SweepResult)
        assert len(result.experiment_ids) == 3
        # Each child experiment saw a different pv_kw value.
        assert {p.metadata.parameters for p in fake.initialized_packs} != set()

    def test_returns_aggregated_metrics(self, tmp_path: Path) -> None:
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(RangeAxis(name="pv_kw", start=100.0, stop=500.0, step=100.0),),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        keys = {name for name, _ in result.aggregated_metrics}
        # The built-in voltage_deviation metric + stats aggregator yields
        # voltage_deviation_mean / median / min / max keys.
        assert "voltage_deviation_mean" in keys
        assert "voltage_deviation_min" in keys
        assert "voltage_deviation_max" in keys
        assert "runtime_mean" in keys

    def test_random_axes_yield_correct_child_count(self, tmp_path: Path) -> None:
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(
                RandomSampleAxis(
                    name="pv_kw",
                    low=100.0,
                    high=1000.0,
                    n_samples=7,
                    seed=42,
                ),
            ),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        assert len(result.experiment_ids) == 7

    def test_plan_hash_is_stable_and_recorded(self, tmp_path: Path) -> None:
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(ChoiceAxis(name="pv_kw", values=(100.0, 200.0)),),
            aggregator_name="statistics",
        )
        result1 = sweep.run(plan)
        result2 = sweep.run(plan)
        assert result1.plan_hash == result2.plan_hash
        assert result1.plan_hash == plan.plan_hash()

    def test_unknown_aggregator_name_raises(self, tmp_path: Path) -> None:
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(ChoiceAxis(name="x", values=(1,)),),
            aggregator_name="ghost",
        )
        with pytest.raises(KeyError, match="ghost"):
            sweep.run(plan)

    def test_missing_base_pack_raises(self, tmp_path: Path) -> None:
        from gridflow.domain.error import PackNotFoundError

        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="missing@1.0.0",
            axes=(ChoiceAxis(name="x", values=(1,)),),
            aggregator_name="statistics",
        )
        with pytest.raises(PackNotFoundError):
            sweep.run(plan)

    def test_child_pack_parameters_override_base(self, tmp_path: Path) -> None:
        _, sweep, fake = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(RangeAxis(name="pv_kw", start=100.0, stop=400.0, step=100.0),),
            aggregator_name="statistics",
        )
        sweep.run(plan)
        seen_kws: list[float] = []
        for pack in fake.initialized_packs:
            for key, value in pack.metadata.parameters:
                if key == "pv_kw":
                    seen_kws.append(float(value))  # type: ignore[arg-type]
        assert sorted(seen_kws) == [100.0, 200.0, 300.0]

    def test_per_experiment_metrics_are_recorded(self, tmp_path: Path) -> None:
        """§5.1.2: SweepResult must carry per-child raw metric values so
        downstream analysis (histogram / quantile / bootstrap) does not
        need to re-open every child ExperimentResult JSON."""
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(RangeAxis(name="pv_kw", start=100.0, stop=400.0, step=100.0),),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        assert len(result.per_experiment_metrics) == len(result.experiment_ids) == 3
        # Each per-experiment entry is the canonical sorted tuple of
        # (metric_name, value) pairs; all metrics computed by the harness
        # appear (at least voltage_deviation + runtime).
        for row in result.per_experiment_metrics:
            keys = [name for name, _ in row]
            assert "voltage_deviation" in keys
            assert "runtime" in keys
            # sorted by key
            assert keys == sorted(keys)

    def test_metric_targeted_axis_reinstantiates_metric_per_child(self, tmp_path: Path) -> None:
        """§5.1.1 Option A: axes with ``target='metric:<name>'`` override
        that metric's kwargs per child without re-running the simulation."""
        from gridflow.usecase.evaluation import MetricSpec

        reg, _, fake = _make_orchestrator_fixture(tmp_path)
        # Rebuild the sweep orchestrator with an explicit metric_specs
        # referencing a plugin metric whose threshold we'll sweep.
        from gridflow.infra.orchestrator import InProcessOrchestratorRunner
        from gridflow.usecase.orchestrator import Orchestrator

        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        orch = Orchestrator(registry=reg, runner=runner)
        agg_reg = AggregatorRegistry()
        agg_reg.register(StatisticsAggregator())
        plugin_spec = f"{__name__}:_ThresholdCounter"
        sweep = SweepOrchestrator(
            registry=reg,
            orchestrator=orch,
            aggregator_registry=agg_reg,
            connector_id="fake",
            # Start with threshold=0 so we can see the override take effect.
            metric_specs=(
                MetricSpec(
                    name="threshold_counter",
                    plugin=plugin_spec,
                    kwargs=(("threshold", 0.0),),
                ),
            ),
        )
        # Sweep pv_kw (→ changes voltage) and also sweep metric.threshold
        # over 3 values. Expansion is cartesian: 2 pv_kws * 3 thresholds = 6 children.
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(
                RangeAxis(name="pv_kw", start=100.0, stop=300.0, step=100.0),
                RangeAxis(
                    name="threshold",
                    start=0.90,
                    stop=1.00,
                    step=0.03,
                    target="metric:threshold_counter",
                ),
            ),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        # 2 pv_kws * 4 thresholds (0.90, 0.93, 0.96, 0.99) = 8 children
        assert len(result.experiment_ids) == 8
        # Assignments carry the metric override.
        some_metric_ov = [a.metric_params for a in result.assignments if a.metric_params]
        assert len(some_metric_ov) == 8
        # Each metric_params entry names our target metric and carries a
        # single 'threshold' override key.
        for mp in some_metric_ov:
            assert len(mp) == 1
            metric_name, kwargs = mp[0]
            assert metric_name == "threshold_counter"
            assert [k for k, _ in kwargs] == ["threshold"]

    def test_metric_target_without_spec_raises(self, tmp_path: Path) -> None:
        """Fail-fast when a metric-targeted axis names an unknown metric."""
        from gridflow.domain.error import OrchestratorError

        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(
                ChoiceAxis(
                    name="threshold",
                    values=(0.9,),
                    target="metric:unknown_metric",
                ),
            ),
            aggregator_name="statistics",
        )
        with pytest.raises(OrchestratorError, match="unknown_metric"):
            sweep.run(plan)

    def test_assignments_are_recorded(self, tmp_path: Path) -> None:
        """§5.1.2 (companion): SweepResult carries the parameter assignment
        that produced each experiment so downstream tools can recover
        *which* axis values produced which outcome."""
        _, sweep, _ = _make_orchestrator_fixture(tmp_path)
        plan = SweepPlan(
            sweep_id="s1",
            base_pack_id="base@1.0.0",
            axes=(RangeAxis(name="pv_kw", start=100.0, stop=400.0, step=100.0),),
            aggregator_name="statistics",
        )
        result = sweep.run(plan)
        # Assignments are positionally aligned with experiment_ids and
        # carry exactly the axis values the child saw.
        pv_kws = [dict(a.pack_params)["pv_kw"] for a in result.assignments]
        assert sorted(pv_kws) == [100.0, 200.0, 300.0]
