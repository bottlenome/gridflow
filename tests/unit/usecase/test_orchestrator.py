"""Tests for the UseCase Orchestrator and InProcessOrchestratorRunner."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.error import PackNotFoundError, SimulationError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack
from gridflow.infra.orchestrator import (
    ContainerOrchestratorRunner,
    InProcessOrchestratorRunner,
)
from gridflow.infra.scenario import FileScenarioRegistry
from gridflow.usecase.interfaces import ConnectorStepOutput
from gridflow.usecase.orchestrator import Orchestrator, RunRequest
from gridflow.usecase.result import StepStatus


class FakeConnector:
    """In-memory connector that emits deterministic bus voltages."""

    name = "fake"

    def __init__(self, *, fail_on_step: int | None = None) -> None:
        self._fail_on_step = fail_on_step
        self.initialized = False
        self.teardown_called = False

    def initialize(self, pack: ScenarioPack) -> None:
        self.initialized = True

    def step(self, step_index: int) -> ConnectorStepOutput:
        if self._fail_on_step is not None and step_index == self._fail_on_step:
            raise RuntimeError("boom")
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


class TestInProcessRunner:
    def test_runs_all_steps(self) -> None:
        runner = InProcessOrchestratorRunner()
        connector = FakeConnector()
        outputs = runner.run_connector(connector, _make_pack(), total_steps=3)
        assert len(outputs) == 3
        assert connector.initialized
        assert connector.teardown_called

    def test_teardown_called_on_failure(self) -> None:
        runner = InProcessOrchestratorRunner()
        connector = FakeConnector(fail_on_step=1)
        with pytest.raises(SimulationError):
            runner.run_connector(connector, _make_pack(), total_steps=3)
        assert connector.teardown_called


class TestOrchestrator:
    def test_full_run_updates_pack_status(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_make_pack())
        orchestrator = Orchestrator(registry=reg, runner=InProcessOrchestratorRunner())
        result = orchestrator.run(RunRequest(pack_id="t@1", connector=FakeConnector(), total_steps=2))
        assert len(result.steps) == 2
        assert all(s.status == StepStatus.SUCCESS for s in result.steps)
        assert result.metadata.connector == "fake"
        assert reg.get("t@1").status == PackStatus.COMPLETED

    def test_missing_pack_raises(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        orchestrator = Orchestrator(registry=reg, runner=InProcessOrchestratorRunner())
        with pytest.raises(PackNotFoundError):
            orchestrator.run(RunRequest(pack_id="missing", connector=FakeConnector()))

    def test_zero_steps_rejected(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_make_pack())
        orchestrator = Orchestrator(registry=reg, runner=InProcessOrchestratorRunner())
        with pytest.raises(Exception, match="total_steps"):
            orchestrator.run(RunRequest(pack_id="t@1", connector=FakeConnector(), total_steps=0))

    def test_seed_propagated(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_make_pack())
        orchestrator = Orchestrator(registry=reg, runner=InProcessOrchestratorRunner())
        result = orchestrator.run(RunRequest(pack_id="t@1", connector=FakeConnector(), total_steps=1, seed=7))
        assert result.metadata.seed == 7


class TestContainerRunnerStub:
    def test_raises_container_error(self) -> None:
        from gridflow.domain.error import ContainerError

        runner = ContainerOrchestratorRunner()
        with pytest.raises(ContainerError):
            runner.run_connector(FakeConnector(), _make_pack(), total_steps=1)
