"""Tests for per-bus voltage exposure through the result chain (issue #30)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import NodeResult
from gridflow.usecase.result import ExperimentResult, StepResult, StepStatus


def _step(bus_voltages: tuple[tuple[str, float], ...], step_id: int = 0) -> StepResult:
    return StepResult(
        step_id=step_id,
        timestamp=datetime(2026, 1, 1, tzinfo=UTC),
        status=StepStatus.SUCCESS,
        elapsed_ms=1.0,
        node_result=NodeResult(node_id="__network__", voltages=tuple(v for _, v in bus_voltages)),
        bus_voltages=bus_voltages,
    )


def _experiment(steps: tuple[StepResult, ...]) -> ExperimentResult:
    meta = ExperimentMetadata(
        experiment_id="e",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="p",
        connector="opendss",
    )
    return ExperimentResult(experiment_id="e", metadata=meta, steps=steps)


class TestExperimentResultBusVoltages:
    def test_final_bus_voltages_from_last_carrying_step(self) -> None:
        exp = _experiment(
            (
                _step((("a", 1.00), ("b", 0.98)), step_id=0),
                _step((("a", 1.02), ("b", 0.97)), step_id=1),
            )
        )
        assert exp.final_bus_voltages() == (("a", 1.02), ("b", 0.97))

    def test_voltage_at_resolves(self) -> None:
        exp = _experiment((_step((("675.1.2.3", 1.03), ("632.1.2.3", 1.00))),))
        assert exp.voltage_at("675.1.2.3") == pytest.approx(1.03)

    def test_voltage_at_missing_bus_raises(self) -> None:
        exp = _experiment((_step((("a", 1.0),)),))
        with pytest.raises(KeyError):
            exp.voltage_at("nope")

    def test_no_bus_voltages_is_empty(self) -> None:
        # A step with no per-bus data (e.g. a connector that only emits the
        # flat vector) yields an empty mapping, not an error.
        meta = ExperimentMetadata(
            experiment_id="e",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            scenario_pack_id="p",
            connector="fake",
        )
        exp = ExperimentResult(
            experiment_id="e",
            metadata=meta,
            steps=(
                StepResult(
                    step_id=0,
                    timestamp=datetime(2026, 1, 1, tzinfo=UTC),
                    status=StepStatus.SUCCESS,
                    elapsed_ms=1.0,
                ),
            ),
        )
        assert exp.final_bus_voltages() == ()
        with pytest.raises(KeyError):
            exp.voltage_at("a")

    def test_skips_trailing_step_without_bus_voltages(self) -> None:
        # Last step has no per-bus data; fall back to the prior step that does.
        exp = _experiment((_step((("a", 1.0),), step_id=0),))
        empty_last = StepResult(
            step_id=1,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            status=StepStatus.SUCCESS,
            elapsed_ms=1.0,
        )
        exp = _experiment((exp.steps[0], empty_last))
        assert exp.final_bus_voltages() == (("a", 1.0),)


class TestStepResultRoundTrip:
    def test_to_dict_includes_bus_voltages(self) -> None:
        d = _step((("a", 1.0), ("b", 0.99))).to_dict()
        assert d["bus_voltages"] == [["a", 1.0], ["b", 0.99]]

    def test_rehydrate_preserves_bus_voltages(self) -> None:
        from gridflow.adapter.cli.app import _rehydrate_experiment_result

        exp = _experiment((_step((("675.1.2.3", 1.03), ("632.1.2.3", 1.00))),))
        data = exp.to_dict()
        restored = _rehydrate_experiment_result(data)
        assert restored.voltage_at("675.1.2.3") == pytest.approx(1.03)
        assert restored.final_bus_voltages() == (("675.1.2.3", 1.03), ("632.1.2.3", 1.00))


class TestRunnerThreadsBusVoltages:
    def test_in_process_runner_carries_bus_voltages(self) -> None:
        from gridflow.infra.orchestrator import InProcessOrchestratorRunner
        from gridflow.usecase.interfaces import ConnectorStepOutput

        class _Fake:
            name = "fake"

            def initialize(self, pack) -> None:  # type: ignore[no-untyped-def]
                pass

            def step(self, step_index: int) -> ConnectorStepOutput:
                return ConnectorStepOutput(
                    step=step_index,
                    node_result=NodeResult(node_id="__network__", voltages=(1.0, 0.98)),
                    converged=True,
                    bus_voltages=(("busA", 1.0), ("busB", 0.98)),
                )

            def teardown(self) -> None:
                pass

        runner = InProcessOrchestratorRunner(connector_factories={"fake": _Fake})
        # prepare wires the connector; ExecutionPlan not needed for run_connector
        # once the connector is registered — build it directly.
        runner._connectors["fake"] = _Fake()  # type: ignore[attr-defined]
        result = runner.run_connector("fake", 0, ())
        assert result.bus_voltages == (("busA", 1.0), ("busB", 0.98))
