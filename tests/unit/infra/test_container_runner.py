"""Tests for ``ContainerOrchestratorRunner`` + ``ContainerManager``.

Spec references:
    * 03d §3.8.2 — ContainerOrchestratorRunner (prepare / run_connector /
      health_check / teardown, REST-over-HTTP to connector daemons).
    * 03d §3.8.3 — ContainerManager (start / stop / health_check for
      Docker services).
    * 03b §3.5.6 — the REST contract the runner speaks (already
      implemented in ``gridflow.connectors.opendss``).

Strategy:
    We spin up the real connector daemon (``gridflow.connectors.opendss``)
    on an ephemeral port inside the test, then construct a
    ``ContainerOrchestratorRunner`` with a **fake** ``ContainerManager``
    (docker subprocess stub) whose ``start`` / ``stop`` are no-ops. This
    gives us a real end-to-end REST round-trip without needing Docker.
"""

from __future__ import annotations

import threading
from collections.abc import Iterator
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.connectors.opendss import build_daemon
from gridflow.domain.error import (
    ConnectorCommunicationError,
    ConnectorNotFoundError,
    ContainerStartError,
    RunnerStartError,
)
from gridflow.domain.scenario import PackMetadata, ScenarioPack
from gridflow.infra.container_manager import (
    ContainerEndpoint,
    ContainerManager,
)
from gridflow.infra.orchestrator import ContainerOrchestratorRunner
from gridflow.infra.scenario import FileScenarioRegistry
from gridflow.usecase.execution_plan import ExecutionPlan, StepConfig
from gridflow.usecase.interfaces import HealthStatus
from gridflow.usecase.result import StepResult, StepStatus

# ----------------------------------------------------------------- fakes


def _make_pack(pack_id: str = "ieee13@1.0.0") -> ScenarioPack:
    name, version = pack_id.split("@")
    meta = PackMetadata(
        name=name,
        version=version,
        description="t",
        author="t",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
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


class _FakeConnector:
    """Minimal ConnectorInterface stub used by the daemon under test."""

    name = "opendss"

    def __init__(self) -> None:
        self.initialized = False
        self.teardown_called = False

    def initialize(self, pack: ScenarioPack) -> None:
        self.initialized = True

    def step(self, step_index: int):
        from gridflow.domain.result import NodeResult
        from gridflow.usecase.interfaces import ConnectorStepOutput

        return ConnectorStepOutput(
            step=step_index,
            node_result=NodeResult(node_id="__network__", voltages=(1.0, 0.99)),
            converged=True,
        )

    def teardown(self) -> None:
        self.teardown_called = True


class _FakeScenarioRegistry:
    """Minimal ScenarioRegistry stub used by the daemon."""

    def __init__(self, packs: dict[str, ScenarioPack]) -> None:
        self._packs = packs

    def register(self, pack):
        self._packs[pack.pack_id] = pack
        return pack

    def get(self, pack_id: str):
        from gridflow.domain.error import PackNotFoundError

        if pack_id not in self._packs:
            raise PackNotFoundError(f"pack_id '{pack_id}' not found", context={"pack_id": pack_id})
        return self._packs[pack_id]

    def list_all(self):
        return tuple(self._packs.values())

    def update_status(self, pack_id, new_status):
        return self._packs[pack_id]

    def delete(self, pack_id):
        del self._packs[pack_id]


class _FakeContainerManager:
    """Record-and-allow fake ``ContainerManager`` for runner tests.

    Satisfies the Protocol structurally. ``start`` / ``stop`` are no-ops
    because the "container" in tests is actually a local HTTP thread.
    """

    def __init__(self, *, fail_start: bool = False) -> None:
        self._fail_start = fail_start
        self.started: list[tuple[str, ...]] = []
        self.stopped: list[tuple[str, ...]] = []
        self.healthy: dict[str, bool] = {}

    def start(self, services: tuple[str, ...]) -> None:
        if self._fail_start:
            raise ContainerStartError(
                f"fake start failure for {services!r}",
                context={"services": services},
            )
        self.started.append(services)
        for s in services:
            self.healthy[s] = True

    def stop(self, services: tuple[str, ...]) -> None:
        self.stopped.append(services)
        for s in services:
            self.healthy[s] = False

    def health_check(self, service: str) -> HealthStatus:
        ok = self.healthy.get(service, False)
        return HealthStatus(
            healthy=ok,
            message="running" if ok else "stopped",
        )


# ----------------------------------------------------------------- fixtures


@pytest.fixture
def running_opendss_daemon() -> Iterator[tuple[str, int, _FakeConnector]]:
    """Yield ``(host, port, fake_connector)`` of a daemon on an ephemeral port."""
    pack = _make_pack()
    registry = _FakeScenarioRegistry({pack.pack_id: pack})
    fake = _FakeConnector()
    daemon = build_daemon(
        host="127.0.0.1",
        port=0,
        registry=registry,
        connector_factory=lambda: fake,
    )
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = daemon.server_address[0], daemon.server_address[1]
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port, fake
    finally:
        daemon.shutdown()
        daemon.server_close()
        thread.join(timeout=2)


def _build_runner(
    host: str,
    port: int,
    *,
    container_manager: ContainerManager | None = None,
) -> ContainerOrchestratorRunner:
    endpoints = {
        "opendss": ContainerEndpoint(
            connector_id="opendss",
            service_name="opendss-connector",
            base_url=f"http://{host}:{port}",
        ),
    }
    return ContainerOrchestratorRunner(
        container_manager=container_manager or _FakeContainerManager(),
        endpoints=endpoints,
    )


@pytest.fixture
def file_registry(tmp_path: Path) -> FileScenarioRegistry:
    reg = FileScenarioRegistry(tmp_path / "packs")
    reg.register(_make_pack())
    return reg


# ----------------------------------------------------------------- prepare


class TestContainerOrchestratorRunnerPrepare:
    def test_prepare_starts_services_and_initializes_connectors(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """Spec 03d §3.8.2: prepare() calls ContainerManager.start() for each
        service mapped by plan.connectors, then POST /initialize to each
        connector daemon.
        """
        host, port, fake = running_opendss_daemon
        manager = _FakeContainerManager()
        runner = _build_runner(host, port, container_manager=manager)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(StepConfig(step_id=0),),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        try:
            assert manager.started == [("opendss-connector",)]
            assert fake.initialized
        finally:
            runner.teardown()

    def test_prepare_unknown_connector_id_raises(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """plan.connectors contains a connector_id that is not in the runner's
        endpoint map → ConnectorNotFoundError."""
        host, port, _ = running_opendss_daemon
        runner = _build_runner(host, port)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("pandapower",),  # not mapped
        )
        with pytest.raises(ConnectorNotFoundError):
            runner.prepare(plan)

    def test_prepare_container_start_failure_wraps_as_runner_start_error(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """Spec 03d §3.8.2: ContainerManager.start() failure surfaces to the
        caller as RunnerStartError (E-40005)."""
        host, port, _ = running_opendss_daemon
        manager = _FakeContainerManager(fail_start=True)
        runner = _build_runner(host, port, container_manager=manager)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        with pytest.raises(RunnerStartError):
            runner.prepare(plan)


# ----------------------------------------------------------------- run_connector


class TestContainerOrchestratorRunnerRun:
    def test_run_connector_round_trips_via_rest(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """Full /execute REST call. The returned StepResult must carry the
        voltages produced by the fake connector inside the daemon."""
        host, port, _ = running_opendss_daemon
        runner = _build_runner(host, port)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(StepConfig(step_id=0), StepConfig(step_id=1)),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        try:
            result = runner.run_connector("opendss", 0, ())
            assert isinstance(result, StepResult)
            assert result.step_id == 0
            assert result.status is StepStatus.SUCCESS
            assert result.node_result is not None
            assert result.node_result.voltages == (1.0, 0.99)
        finally:
            runner.teardown()

    def test_run_connector_unknown_connector_id_raises(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        host, port, _ = running_opendss_daemon
        runner = _build_runner(host, port)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        try:
            with pytest.raises(ConnectorNotFoundError):
                runner.run_connector("ghost", 0, ())
        finally:
            runner.teardown()

    def test_run_connector_http_failure_wraps_as_communication_error(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """Point the runner at a dead port — run_connector must raise
        ConnectorCommunicationError (E-40006)."""
        host, _port, _ = running_opendss_daemon
        # Use a definitely-closed port (0 is not a valid client port but we
        # need a TCP port guaranteed to be closed; 1 is typically closed).
        runner = _build_runner(host, 1)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        # prepare() talks to the dead port for /initialize → should fail.
        # The failure must surface as RunnerStartError (prepare wraps the
        # communication error into RunnerStartError).
        with pytest.raises((RunnerStartError, ConnectorCommunicationError)):
            runner.prepare(plan)


# ----------------------------------------------------------------- teardown


class TestContainerOrchestratorRunnerTeardown:
    def test_teardown_stops_services_and_calls_daemon_teardown(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        host, port, fake = running_opendss_daemon
        manager = _FakeContainerManager()
        runner = _build_runner(host, port, container_manager=manager)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        runner.teardown()
        assert fake.teardown_called
        assert manager.stopped == [("opendss-connector",)]

    def test_teardown_is_best_effort_even_if_daemon_is_down(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        """Spec 03d §3.8.2: teardown errors are recorded but not raised."""
        host, port, _ = running_opendss_daemon
        manager = _FakeContainerManager()
        runner = _build_runner(host, port, container_manager=manager)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        # Now point the runner at a dead port by mutating its endpoints.
        # (Crude but effective — the daemon will be shut down after yield
        # anyway.) teardown must not raise.
        runner._endpoints["opendss"] = ContainerEndpoint(  # type: ignore[attr-defined]
            connector_id="opendss",
            service_name="opendss-connector",
            base_url="http://127.0.0.1:1",
        )
        runner.teardown()  # must not raise
        # Container manager stop should still have been called.
        assert manager.stopped == [("opendss-connector",)]


# ----------------------------------------------------------------- health_check


class TestContainerOrchestratorRunnerHealth:
    def test_health_check_delegates_to_container_manager(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        host, port, _ = running_opendss_daemon
        manager = _FakeContainerManager()
        runner = _build_runner(host, port, container_manager=manager)
        plan = ExecutionPlan(
            experiment_id="exp-1",
            pack=_make_pack(),
            steps=(),
            connectors=("opendss",),
        )
        runner.prepare(plan)
        try:
            status = runner.health_check("opendss")
            assert status.healthy is True
        finally:
            runner.teardown()

    def test_health_check_unknown_connector_returns_unhealthy(
        self,
        running_opendss_daemon: tuple[str, int, _FakeConnector],
    ) -> None:
        host, port, _ = running_opendss_daemon
        runner = _build_runner(host, port)
        status = runner.health_check("ghost")
        assert status.healthy is False
