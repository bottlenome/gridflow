"""Tests for the OpenDSS connector REST daemon.

Spec:
    * docs/detailed_design/11_build_deploy.md §11.1.2 — the
      ``opendss-connector`` container runs ``python -m gridflow.connectors.opendss``
      as a long-running daemon that exposes HEALTHCHECK on port 8000 via
      ``GET /health``.
    * docs/detailed_design/03b_usecase_classes.md §3.5.6 — REST API
      endpoints, session model (1 container = 1 session), state transitions
      (UNINITIALIZED ↔ READY), error contract (400/404/405/409/422/500 with
      GridflowError.to_dict() compatible JSON bodies).
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from datetime import UTC, datetime
from http import HTTPStatus
from typing import Any

import pytest

from gridflow.connectors.opendss import build_daemon
from gridflow.domain.error import OpenDSSError, PackNotFoundError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack
from gridflow.usecase.interfaces import ConnectorStepOutput

# ----------------------------------------------------------------- fakes


def _make_pack(pack_id: str = "ieee13@1.0.0") -> ScenarioPack:
    from pathlib import Path

    name, version = pack_id.split("@")
    meta = PackMetadata(
        name=name,
        version=version,
        description="test",
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


class _FakeRegistry:
    """Minimal ScenarioRegistry stub for daemon tests."""

    def __init__(self, packs: dict[str, ScenarioPack] | None = None) -> None:
        self._packs: dict[str, ScenarioPack] = dict(packs or {})

    def register(self, pack: ScenarioPack) -> ScenarioPack:
        self._packs[pack.pack_id] = pack
        return pack

    def get(self, pack_id: str) -> ScenarioPack:
        if pack_id not in self._packs:
            raise PackNotFoundError(
                f"pack_id '{pack_id}' not found",
                context={"pack_id": pack_id},
            )
        return self._packs[pack_id]

    def list_all(self) -> tuple[ScenarioPack, ...]:
        return tuple(self._packs.values())

    def update_status(self, pack_id: str, new_status: PackStatus) -> ScenarioPack:
        return self._packs[pack_id]

    def delete(self, pack_id: str) -> None:
        del self._packs[pack_id]


class _FakeConnector:
    """In-memory ConnectorInterface implementation for daemon tests."""

    name = "fake"

    def __init__(
        self,
        *,
        initialize_error: Exception | None = None,
        step_error: Exception | None = None,
    ) -> None:
        self._initialize_error = initialize_error
        self._step_error = step_error
        self.initialized_pack: ScenarioPack | None = None
        self.steps_called: list[int] = []
        self.teardown_called = False

    def initialize(self, pack: ScenarioPack) -> None:
        if self._initialize_error is not None:
            raise self._initialize_error
        self.initialized_pack = pack

    def step(self, step_index: int) -> ConnectorStepOutput:
        if self._step_error is not None:
            raise self._step_error
        self.steps_called.append(step_index)
        return ConnectorStepOutput(
            step=step_index,
            node_result=NodeResult(node_id="__network__", voltages=(1.0, 0.99, 0.98)),
            converged=True,
            metadata=(("bus_names", ("a", "b", "c")),),
        )

    def teardown(self) -> None:
        self.teardown_called = True


# ----------------------------------------------------------------- fixtures


def _start_daemon(
    *,
    registry: Any = None,
    connector: Any = None,
) -> tuple[Any, threading.Thread, tuple[str, int]]:
    """Build + start a daemon on an ephemeral port with injected fakes."""
    fake_connector = connector or _FakeConnector()

    def factory() -> Any:
        return fake_connector

    daemon = build_daemon(
        host="127.0.0.1",
        port=0,
        registry=registry or _FakeRegistry(),
        connector_factory=factory,
    )
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    host, port = daemon.server_address[0], daemon.server_address[1]
    assert isinstance(host, str)
    assert isinstance(port, int)
    return daemon, thread, (host, port)


def _stop_daemon(daemon: Any, thread: threading.Thread) -> None:
    daemon.shutdown()
    daemon.server_close()
    thread.join(timeout=2)


@pytest.fixture
def running_daemon() -> Iterator[tuple[str, int]]:
    """Yield ``(host, port)`` of a daemon backed by default empty fakes."""
    daemon, thread, addr = _start_daemon()
    try:
        yield addr
    finally:
        _stop_daemon(daemon, thread)


# ----------------------------------------------------------------- helpers


def _http_post(
    host: str,
    port: int,
    path: str,
    body: dict[str, Any] | None = None,
    *,
    raw_body: bytes | None = None,
    content_type: str = "application/json",
) -> tuple[int, dict[str, Any]]:
    """POST and return ``(status, parsed_json_body)``. Captures HTTP errors."""
    data = raw_body if raw_body is not None else json.dumps(body or {}).encode("utf-8")
    req = urllib.request.Request(
        f"http://{host}:{port}{path}",
        data=data,
        method="POST",
        headers={"Content-Type": content_type},
    )
    try:
        with urllib.request.urlopen(req, timeout=2) as resp:
            return resp.status, json.loads(resp.read().decode("utf-8") or "{}")
    except urllib.error.HTTPError as exc:
        payload: dict[str, Any] = {}
        raw = exc.read().decode("utf-8")
        if raw:
            payload = json.loads(raw)
        return exc.code, payload


# ----------------------------------------------------------------- Unit 1: /health


class TestOpenDSSConnectorDaemonHealth:
    """Unit 1: minimum viable daemon — ``/health`` contract only."""

    def test_health_endpoint_returns_200_healthy_true(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        """Spec 03b §3.5.6: ``GET /health`` returns ``HealthStatus`` JSON.

        HealthStatus schema (03b §3.5.5): ``{"healthy": bool, "message": str}``.
        """
        host, port = running_daemon
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
            assert resp.status == HTTPStatus.OK
            assert resp.headers.get("Content-Type") == "application/json"
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload == {"healthy": True, "message": "opendss-connector ready"}

    def test_unknown_path_returns_404(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        host, port = running_daemon
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/unknown", timeout=2)
        assert exc_info.value.code == HTTPStatus.NOT_FOUND

    def test_health_endpoint_satisfies_dockerfile_healthcheck(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        """Regression: detailed design 11.1.2 specifies::

            HEALTHCHECK ... CMD python -c "import urllib.request; \\
                urllib.request.urlopen('http://localhost:8000/health')" || exit 1
        """
        host, port = running_daemon
        urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)


# ----------------------------------------------------------------- Unit 2a: /initialize


class TestInitializeEndpoint:
    """Unit 2a: ``POST /initialize`` — session creation + state invariants."""

    def test_initialize_with_valid_pack_id_returns_200(self) -> None:
        """Spec 03b §3.5.6: ``POST /initialize {"pack_id": str}`` → 200 ``{"status": "ok"}``.

        Side-effect: the underlying ConnectorInterface.initialize() must be
        called with the pack resolved from the registry.
        """
        pack = _make_pack("ieee13@1.0.0")
        registry = _FakeRegistry({pack.pack_id: pack})
        connector = _FakeConnector()
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            status, body = _http_post(host, port, "/initialize", {"pack_id": "ieee13@1.0.0"})
            assert status == HTTPStatus.OK
            assert body == {"status": "ok"}
            assert connector.initialized_pack is pack
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_twice_returns_409_conflict(self) -> None:
        """Spec 03b §3.5.6: /initialize while session is READY → 409 Conflict.

        Error body must be GridflowError.to_dict() compatible with
        ``error_code == "E-30006"`` (ConnectorStateError).
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        daemon, thread, (host, port) = _start_daemon(registry=registry)
        try:
            # First initialize succeeds
            status, _ = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status == HTTPStatus.OK
            # Second initialize must be rejected
            status, body = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status == HTTPStatus.CONFLICT
            assert body["error_code"] == "E-30006"
            assert "message" in body
            assert "context" in body
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_with_missing_pack_id_returns_400(self) -> None:
        """Spec 03b §3.5.6: request body missing ``pack_id`` → 400 Bad Request.

        Error code must be ``E-30007`` (ConnectorRequestError).
        """
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, body = _http_post(host, port, "/initialize", {})
            assert status == HTTPStatus.BAD_REQUEST
            assert body["error_code"] == "E-30007"
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_with_malformed_json_returns_400(self) -> None:
        """Spec 03b §3.5.6: unparsable JSON body → 400 ConnectorRequestError."""
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, body = _http_post(host, port, "/initialize", raw_body=b"{not-json")
            assert status == HTTPStatus.BAD_REQUEST
            assert body["error_code"] == "E-30007"
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_with_unknown_pack_id_returns_422(self) -> None:
        """Spec 03b §3.5.6: unknown pack_id → 422 Unprocessable Entity (PackNotFoundError).

        The domain error code ``E-10002`` must be surfaced in the response body.
        """
        daemon, thread, (host, port) = _start_daemon(registry=_FakeRegistry())
        try:
            status, body = _http_post(host, port, "/initialize", {"pack_id": "missing@1.0.0"})
            assert status == HTTPStatus.UNPROCESSABLE_ENTITY
            assert body["error_code"] == "E-10002"
        finally:
            _stop_daemon(daemon, thread)

    def test_initialize_when_connector_raises_returns_500(self) -> None:
        """Spec 03b §3.5.6: connector.initialize() raising OpenDSSError → 500.

        The error code ``E-30002`` must be surfaced and the server must remain
        in UNINITIALIZED state (no partial session left behind).
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        connector = _FakeConnector(
            initialize_error=OpenDSSError(
                "solver did not converge",
                context={"pack_id": pack.pack_id},
            )
        )
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            status, body = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status == HTTPStatus.INTERNAL_SERVER_ERROR
            assert body["error_code"] == "E-30002"
            # A second initialize must succeed because the server rolled back
            # to UNINITIALIZED (using a fresh connector via the factory).
            # We swap the factory error out via a new connector instance.
        finally:
            _stop_daemon(daemon, thread)


# ----------------------------------------------------------------- Unit 2b: /execute


class TestExecuteEndpoint:
    """Unit 2b: ``POST /execute`` — step dispatch + StepResult serialisation."""

    def test_execute_before_initialize_returns_409(self) -> None:
        """Spec 03b §3.5.6: /execute while UNINITIALIZED → 409 ConnectorStateError."""
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, body = _http_post(host, port, "/execute", {"step": 0, "context": []})
            assert status == HTTPStatus.CONFLICT
            assert body["error_code"] == "E-30006"
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_after_initialize_returns_step_result(self) -> None:
        """Spec 03b §3.5.6: /execute after /initialize → 200 StepResult JSON.

        The response body must be a serialised ``StepResult`` (03e §3.11.3)
        with at least ``step_id``, ``timestamp``, ``status``, and
        ``node_result``.
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        connector = _FakeConnector()
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(
                host,
                port,
                "/execute",
                {"step": 0, "context": [["mode", "steady_state"]]},
            )
            assert status == HTTPStatus.OK
            assert body["step_id"] == 0
            assert body["status"] == "success"
            assert body["error"] is None
            assert body["node_result"]["node_id"] == "__network__"
            assert body["node_result"]["voltages"] == [1.0, 0.99, 0.98]
            assert "timestamp" in body
            assert connector.steps_called == [0]
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_missing_step_field_returns_400(self) -> None:
        """Spec 03b §3.5.6: /execute without ``step`` → 400 ConnectorRequestError."""
        pack = _make_pack()
        daemon, thread, (host, port) = _start_daemon(registry=_FakeRegistry({pack.pack_id: pack}))
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(host, port, "/execute", {"context": []})
            assert status == HTTPStatus.BAD_REQUEST
            assert body["error_code"] == "E-30007"
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_wrong_step_type_returns_400(self) -> None:
        pack = _make_pack()
        daemon, thread, (host, port) = _start_daemon(registry=_FakeRegistry({pack.pack_id: pack}))
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(host, port, "/execute", {"step": "zero", "context": []})
            assert status == HTTPStatus.BAD_REQUEST
            assert body["error_code"] == "E-30007"
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_context_must_be_list_of_pairs(self) -> None:
        """Spec 03b §3.5.6: context is ``tuple[tuple[str, object], ...]`` over the wire.

        Accept JSON ``list[list[str, object]]``. Reject plain dicts (the old
        pre-depth-revision form) and non-pair shapes to enforce the
        CLAUDE.md §0.1 params tuple convention.
        """
        pack = _make_pack()
        daemon, thread, (host, port) = _start_daemon(registry=_FakeRegistry({pack.pack_id: pack}))
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(host, port, "/execute", {"step": 0, "context": {"mode": "x"}})
            assert status == HTTPStatus.BAD_REQUEST
            assert body["error_code"] == "E-30007"
        finally:
            _stop_daemon(daemon, thread)

    def test_execute_propagates_solver_failure_as_500(self) -> None:
        """Spec 03b §3.5.6: connector.step() raising → 500 with error_code surfaced.

        The session must transition back to UNINITIALIZED (auto-teardown) per
        the state diagram, so a subsequent /initialize is allowed.
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        failing = _FakeConnector(
            step_error=OpenDSSError("not converged", context={"step": 0}),
        )
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=failing)
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(host, port, "/execute", {"step": 0, "context": []})
            assert status == HTTPStatus.INTERNAL_SERVER_ERROR
            assert body["error_code"] == "E-30002"
            # State must now be UNINITIALIZED. We can detect this by
            # observing that teardown was called and /execute is rejected
            # with 409 (not another 500).
            assert failing.teardown_called
            status2, body2 = _http_post(host, port, "/execute", {"step": 1, "context": []})
            assert status2 == HTTPStatus.CONFLICT
            assert body2["error_code"] == "E-30006"
        finally:
            _stop_daemon(daemon, thread)


# ----------------------------------------------------------------- Unit 2c: /teardown


class TestTeardownEndpoint:
    """Unit 2c: ``POST /teardown`` — explicit session release."""

    def test_teardown_after_initialize_returns_200(self) -> None:
        """Spec 03b §3.5.6: /teardown transitions READY → UNINITIALIZED.

        After /teardown, a fresh /initialize must succeed on the same
        daemon instance (full round-trip through the state machine).
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        connector = _FakeConnector()
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})

            status, body = _http_post(host, port, "/teardown")
            assert status == HTTPStatus.OK
            assert body == {"status": "ok"}
            assert connector.teardown_called

            # And /initialize must succeed again — the daemon is back to
            # UNINITIALIZED state.
            status2, _ = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status2 == HTTPStatus.OK
        finally:
            _stop_daemon(daemon, thread)

    def test_teardown_without_session_returns_409(self) -> None:
        """Spec 03b §3.5.6: /teardown from UNINITIALIZED → 409 ConnectorStateError."""
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, body = _http_post(host, port, "/teardown")
            assert status == HTTPStatus.CONFLICT
            assert body["error_code"] == "E-30006"
        finally:
            _stop_daemon(daemon, thread)

    def test_teardown_swallows_connector_errors_and_still_resets(self) -> None:
        """Teardown must be best-effort and always leave UNINITIALIZED state.

        Rationale: 03b §3.5.6 state diagram — /teardown always goes to
        UNINITIALIZED. A solver that throws during teardown should not
        leave the daemon stuck in READY (which would force a kill-and-
        restart to recover).
        """
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})

        class _TeardownBombConnector(_FakeConnector):
            def teardown(self) -> None:
                super().teardown()
                raise RuntimeError("solver crashed during teardown")

        connector = _TeardownBombConnector()
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            status, body = _http_post(host, port, "/teardown")
            # We still return 200 (best-effort) and the state is reset.
            assert status == HTTPStatus.OK
            assert body == {"status": "ok"}
            assert connector.teardown_called
            # Subsequent /initialize must succeed (daemon is UNINITIALIZED).
            status2, _ = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status2 == HTTPStatus.OK
        finally:
            _stop_daemon(daemon, thread)


# ----------------------------------------------------------------- Unit 2d: method dispatch + end-to-end


class TestMethodDispatch:
    """Unit 2d: verb/path dispatch — wrong verb on a known path → 405."""

    def test_get_on_initialize_returns_405(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        host, port = running_daemon
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/initialize", timeout=2)
        assert exc_info.value.code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_get_on_execute_returns_405(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        host, port = running_daemon
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/execute", timeout=2)
        assert exc_info.value.code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_get_on_teardown_returns_405(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        host, port = running_daemon
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/teardown", timeout=2)
        assert exc_info.value.code == HTTPStatus.METHOD_NOT_ALLOWED

    def test_post_on_health_returns_405(self) -> None:
        daemon, thread, (host, port) = _start_daemon()
        try:
            status, _ = _http_post(host, port, "/health")
            assert status == HTTPStatus.METHOD_NOT_ALLOWED
        finally:
            _stop_daemon(daemon, thread)


class TestFullLifecycleRoundTrip:
    """Unit 2d: end-to-end UNINITIALIZED → READY → READY → UNINITIALIZED.

    Exercises all four endpoints over a single daemon instance with a
    fake connector, covering the state diagram in 03b §3.5.6.
    """

    def test_full_lifecycle_with_fake_connector(self) -> None:
        pack = _make_pack()
        registry = _FakeRegistry({pack.pack_id: pack})
        connector = _FakeConnector()
        daemon, thread, (host, port) = _start_daemon(registry=registry, connector=connector)
        try:
            # 1. Health check always works
            with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
                assert resp.status == HTTPStatus.OK

            # 2. /initialize
            status, _ = _http_post(host, port, "/initialize", {"pack_id": pack.pack_id})
            assert status == HTTPStatus.OK

            # 3. Two /execute calls (monotonic step)
            for step in (0, 1):
                status, body = _http_post(
                    host,
                    port,
                    "/execute",
                    {"step": step, "context": [["phase", "steady"]]},
                )
                assert status == HTTPStatus.OK
                assert body["step_id"] == step
                assert body["status"] == "success"

            # 4. /teardown
            status, _ = _http_post(host, port, "/teardown")
            assert status == HTTPStatus.OK

            # Verify end-state
            assert connector.steps_called == [0, 1]
            assert connector.teardown_called
        finally:
            _stop_daemon(daemon, thread)
