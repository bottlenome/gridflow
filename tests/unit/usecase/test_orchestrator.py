"""Tests for the UseCase ``Orchestrator`` against the spec-compliant Protocol.

Spec references:
    * 03b §3.3.2 — ``Orchestrator.run(pack, options)`` high-level loop.
    * 03b §3.3.3 — ``OrchestratorRunner`` Protocol (prepare / run_connector /
      health_check / teardown).
    * 03b §3.3.4 — ``ExecutionPlan`` shape.
    * 03d §3.8.2 — Infra runner error contract.

Unit 3b scope: drive the post-refactor Orchestrator/InProcess code paths
via the NEW Protocol. The old tests that called
``run_connector(connector, pack, total_steps)`` are obsoleted by this
file — they were testing the pre-refactor signature.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.error import (
    ConnectorNotFoundError,
    PackNotFoundError,
    SimulationError,
)
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack
from gridflow.infra.orchestrator import InProcessOrchestratorRunner
from gridflow.infra.scenario import FileScenarioRegistry
from gridflow.usecase.execution_plan import ExecutionPlan, StepConfig
from gridflow.usecase.interfaces import ConnectorStepOutput, HealthStatus
from gridflow.usecase.orchestrator import Orchestrator, RunRequest
from gridflow.usecase.result import StepStatus


class FakeConnector:
    """In-memory ConnectorInterface for Orchestrator/InProcess tests."""

    name = "fake"

    def __init__(self, *, fail_on_step: int | None = None) -> None:
        self._fail_on_step = fail_on_step
        self.initialized = False
        self.teardown_called = False
        self.steps_called: list[int] = []

    def initialize(self, pack: ScenarioPack) -> None:
        self.initialized = True

    def step(self, step_index: int) -> ConnectorStepOutput:
        if self._fail_on_step is not None and step_index == self._fail_on_step:
            raise RuntimeError("boom")
        self.steps_called.append(step_index)
        voltages = (1.0 + 0.01 * step_index, 0.99 - 0.01 * step_index)
        return ConnectorStepOutput(
            step=step_index,
            node_result=NodeResult(node_id="__network__", voltages=voltages),
            converged=True,
        )

    def teardown(self) -> None:
        self.teardown_called = True


def _make_pack() -> ScenarioPack:
    meta = PackMetadata(
        name="t",
        version="1.0.0",
        description="d",
        author="a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="fake",
    )
    return ScenarioPack(
        pack_id="t@1",
        name="t",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/n"),
        timeseries_dir=Path("/ts"),
        config_dir=Path("/c"),
    )


# ---------------------------------------------------------------------- runner


class TestInProcessRunnerSpec:
    """Spec 03b §3.3.3 / 03d §3.8.2: the Protocol has
    ``prepare(plan)``, ``run_connector(connector_id, step, context)``,
    ``health_check(connector_id)``, and ``teardown()``.
    """

    def test_prepare_initialises_each_connector_via_factory(self) -> None:
        fake = FakeConnector()
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(StepConfig(step_id=0),),
            connectors=("fake",),
        )
        runner.prepare(plan)
        try:
            assert fake.initialized
        finally:
            runner.teardown()

    def test_prepare_unknown_connector_raises_connector_not_found(self) -> None:
        runner = InProcessOrchestratorRunner(connector_factories={})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("ghost",),
        )
        with pytest.raises(ConnectorNotFoundError):
            runner.prepare(plan)

    def test_run_connector_returns_step_result(self) -> None:
        fake = FakeConnector()
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(StepConfig(step_id=0),),
            connectors=("fake",),
        )
        runner.prepare(plan)
        try:
            result = runner.run_connector("fake", 0, ())
            assert result.step_id == 0
            assert result.status is StepStatus.SUCCESS
            assert result.node_result is not None
            assert result.node_result.voltages == (1.0, 0.99)
        finally:
            runner.teardown()

    def test_run_connector_unknown_id_raises(self) -> None:
        runner = InProcessOrchestratorRunner(connector_factories={"fake": FakeConnector})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("fake",),
        )
        runner.prepare(plan)
        try:
            with pytest.raises(ConnectorNotFoundError):
                runner.run_connector("ghost", 0, ())
        finally:
            runner.teardown()

    def test_run_connector_wraps_solver_failure_as_simulation_error(self) -> None:
        fake = FakeConnector(fail_on_step=1)
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("fake",),
        )
        runner.prepare(plan)
        try:
            runner.run_connector("fake", 0, ())  # ok
            with pytest.raises(SimulationError):
                runner.run_connector("fake", 1, ())
        finally:
            runner.teardown()

    def test_health_check_returns_status(self) -> None:
        fake = FakeConnector()
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("fake",),
        )
        runner.prepare(plan)
        try:
            status = runner.health_check("fake")
            assert isinstance(status, HealthStatus)
            assert status.healthy is True
        finally:
            runner.teardown()

    def test_health_check_unknown_connector_returns_unhealthy(self) -> None:
        runner = InProcessOrchestratorRunner(connector_factories={})
        status = runner.health_check("ghost")
        assert isinstance(status, HealthStatus)
        assert status.healthy is False

    def test_teardown_calls_each_connector_and_clears_registry(self) -> None:
        fake = FakeConnector()
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("fake",),
        )
        runner.prepare(plan)
        runner.teardown()
        assert fake.teardown_called
        # After teardown, /run_connector must fail with ConnectorNotFoundError
        with pytest.raises(ConnectorNotFoundError):
            runner.run_connector("fake", 0, ())

    def test_teardown_is_best_effort(self) -> None:
        class _Exploding(FakeConnector):
            def teardown(self) -> None:
                super().teardown()
                raise RuntimeError("can't stop, won't stop")

        fake = _Exploding()
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("fake",),
        )
        runner.prepare(plan)
        # Must not raise even though the underlying connector does
        runner.teardown()
        assert fake.teardown_called


# ---------------------------------------------------------------------- Orchestrator


@dataclass
class _OrchestratorFixture:
    registry: FileScenarioRegistry
    fake: FakeConnector
    orchestrator: Orchestrator


def _build_orchestrator(tmp_path: Path) -> _OrchestratorFixture:
    reg = FileScenarioRegistry(tmp_path / "packs")
    reg.register(_make_pack())
    fake = FakeConnector()
    runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
    return _OrchestratorFixture(
        registry=reg,
        fake=fake,
        orchestrator=Orchestrator(registry=reg, runner=runner),
    )


class TestOrchestrator:
    """Spec 03b §3.3.2: Orchestrator orchestrates via the new Protocol."""

    def test_full_run_updates_pack_status(self, tmp_path: Path) -> None:
        fixture = _build_orchestrator(tmp_path)
        result = fixture.orchestrator.run(RunRequest(pack_id="t@1", connector_id="fake", total_steps=2))
        assert len(result.steps) == 2
        assert all(s.status == StepStatus.SUCCESS for s in result.steps)
        assert result.metadata.connector == "fake"
        assert fixture.registry.get("t@1").status == PackStatus.COMPLETED
        assert fixture.fake.steps_called == [0, 1]

    def test_missing_pack_raises(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        runner = InProcessOrchestratorRunner(connector_factories={"fake": FakeConnector})
        orchestrator = Orchestrator(registry=reg, runner=runner)
        with pytest.raises(PackNotFoundError):
            orchestrator.run(RunRequest(pack_id="missing", connector_id="fake"))

    def test_zero_steps_rejected(self, tmp_path: Path) -> None:
        fixture = _build_orchestrator(tmp_path)
        with pytest.raises(Exception, match="total_steps"):
            fixture.orchestrator.run(RunRequest(pack_id="t@1", connector_id="fake", total_steps=0))

    def test_seed_propagated(self, tmp_path: Path) -> None:
        fixture = _build_orchestrator(tmp_path)
        result = fixture.orchestrator.run(RunRequest(pack_id="t@1", connector_id="fake", total_steps=1, seed=7))
        assert result.metadata.seed == 7

    def test_teardown_always_called_even_on_failure(self, tmp_path: Path) -> None:
        """When run_connector raises, teardown must still reset the runner."""
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_make_pack())
        fake = FakeConnector(fail_on_step=0)
        runner = InProcessOrchestratorRunner(connector_factories={"fake": lambda: fake})
        orchestrator = Orchestrator(registry=reg, runner=runner)
        with pytest.raises(SimulationError):
            orchestrator.run(RunRequest(pack_id="t@1", connector_id="fake", total_steps=1))
        assert fake.teardown_called
