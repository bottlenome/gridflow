"""Shared connector REST daemon base.

Spec: ``docs/detailed_design/03b_usecase_classes.md`` §3.5.6 (REST API
contract). The session model, state machine, request validation, error
mapping, and JSON schema are identical for every connector
(``opendss``, ``pandapower``, future ``pandapower-dss``, etc.). This
module provides the implementation once so each
``gridflow.connectors.<name>`` shim only needs to declare:

    1. ``DEFAULT_PORT``                — its container port
    2. its health message string       — for ``GET /health``
    3. its default ``connector_factory`` (which builds an instance of
       the corresponding ``ConnectorInterface`` adapter)
    4. its default :class:`ScenarioRegistry` (typically the same
       file-based registry shared with the rest of gridflow)

Everything else — the lock, the state machine, the request parsing, the
error JSON, the path/verb dispatch — comes from this base.

Why a class hierarchy and not e.g. functional middleware? The Python
stdlib ``BaseHTTPRequestHandler`` API is already class-based, so we go
along with it. The base ``_ConnectorHandler`` carries all the logic;
the per-connector shim only customises the *constructor inputs* of
:class:`DaemonState` (factory + registry) and the health message.
"""

from __future__ import annotations

import contextlib
import json
import threading
from collections.abc import Callable, Mapping
from datetime import UTC, datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any, ClassVar, cast

from gridflow.domain.error import (
    ConnectorError,
    ConnectorRequestError,
    ConnectorStateError,
    GridflowError,
    OpenDSSError,
    PackNotFoundError,
)
from gridflow.domain.scenario import ScenarioPack
from gridflow.domain.scenario.registry import ScenarioRegistry
from gridflow.domain.util.params import as_params
from gridflow.infra.logging import get_logger
from gridflow.usecase.interfaces import ConnectorInterface, ConnectorStepOutput
from gridflow.usecase.result import StepResult, StepStatus

# 0.0.0.0 is required inside the container so the Docker Compose internal
# network can reach the daemon. 127.0.0.1 would only be reachable from
# inside the container itself.
DEFAULT_HOST = "0.0.0.0"

_OK_BODY = json.dumps({"status": "ok"}, separators=(",", ":")).encode("utf-8")


# ----------------------------------------------------------------- daemon state


class DaemonState:
    """Server-side session state for a connector daemon.

    Implements the UNINITIALIZED ↔ READY state machine from 03b §3.5.6.
    A single :class:`ConnectorInterface` instance is held while in READY
    state; a :class:`threading.Lock` serialises state transitions so
    concurrent ``ThreadingHTTPServer`` requests cannot race (e.g. two
    simultaneous ``/initialize`` calls).
    """

    def __init__(
        self,
        registry: ScenarioRegistry,
        connector_factory: Callable[[], ConnectorInterface],
        health_body: bytes,
    ) -> None:
        self._registry = registry
        self._factory = connector_factory
        self._health_body = health_body
        self._lock = threading.Lock()
        self._connector: ConnectorInterface | None = None

    @property
    def lock(self) -> threading.Lock:
        return self._lock

    @property
    def health_body(self) -> bytes:
        return self._health_body

    def is_ready(self) -> bool:
        return self._connector is not None

    def resolve_pack(self, pack_id: str) -> ScenarioPack:
        """Look up a pack — may raise ``PackNotFoundError``."""
        return self._registry.get(pack_id)

    def initialize(self, pack: ScenarioPack) -> None:
        """Transition UNINITIALIZED → READY.

        Caller must hold :attr:`lock` and have already checked that
        ``is_ready()`` is ``False``. Raises ``ConnectorError`` (or
        subclasses) on solver failure; in that case the state stays
        UNINITIALIZED so retries remain possible.
        """
        connector = self._factory()
        try:
            connector.initialize(pack)
        except Exception:
            with contextlib.suppress(Exception):
                connector.teardown()
            raise
        self._connector = connector

    def step(self, step_index: int) -> ConnectorStepOutput:
        """Drive one solver step — requires READY state.

        Caller must hold :attr:`lock`. On failure the session
        auto-resets to UNINITIALIZED (best-effort teardown) per
        03b §3.5.6 state diagram, so a crashed solver does not leave
        the daemon stuck.
        """
        assert self._connector is not None
        try:
            return self._connector.step(step_index)
        except Exception:
            failed = self._connector
            self._connector = None
            with contextlib.suppress(Exception):
                failed.teardown()
            raise

    def teardown(self) -> None:
        """Transition READY → UNINITIALIZED (best-effort).

        Caller must hold :attr:`lock` and have already checked that
        ``is_ready()`` is ``True``. Connector errors during teardown
        are swallowed so the server always ends up in UNINITIALIZED.
        """
        assert self._connector is not None
        connector = self._connector
        self._connector = None
        with contextlib.suppress(Exception):
            connector.teardown()


# ----------------------------------------------------------------- server


class DaemonServer(ThreadingHTTPServer):
    """HTTP server that carries the daemon session state for the handler."""

    allow_reuse_address = True

    def __init__(
        self,
        server_address: tuple[str, int],
        handler_class: type[BaseHTTPRequestHandler],
        state: DaemonState,
    ) -> None:
        super().__init__(server_address, handler_class)
        self.state = state


# ----------------------------------------------------------------- handler


class ConnectorHandler(BaseHTTPRequestHandler):
    """Handler covering the REST contract from 03b §3.5.6.

    Path / verb dispatch is centralised so:
        * Unknown paths uniformly return ``404 Not Found``.
        * Known paths with the wrong verb uniformly return
          ``405 Method Not Allowed`` with an ``Allow`` header.
    """

    _ROUTES: ClassVar[dict[str, tuple[str, str]]] = {
        "/health": ("GET", "_handle_health"),
        "/initialize": ("POST", "_handle_initialize"),
        "/execute": ("POST", "_handle_execute"),
        "/teardown": ("POST", "_handle_teardown"),
    }

    # --- HTTP verb dispatch --------------------------------------------

    def do_GET(self) -> None:  # BaseHTTPRequestHandler API name
        self._dispatch("GET")

    def do_POST(self) -> None:  # BaseHTTPRequestHandler API name
        self._dispatch("POST")

    def _dispatch(self, verb: str) -> None:
        route = self._ROUTES.get(self.path)
        if route is None:
            self._write_empty(404)
            return
        allowed_verb, handler_name = route
        if verb != allowed_verb:
            self._write_method_not_allowed(allowed_verb)
            return
        handler = getattr(self, handler_name)
        handler()

    def _write_method_not_allowed(self, allowed_verb: str) -> None:
        self.send_response(405)
        self.send_header("Allow", allowed_verb)
        self.send_header("Content-Length", "0")
        self.end_headers()

    # --- /health -------------------------------------------------------

    def _handle_health(self) -> None:
        body = self._state().health_body
        self._write_json(200, body)

    # --- /initialize ---------------------------------------------------

    def _handle_initialize(self) -> None:
        try:
            body = self._read_json_body()
        except ConnectorRequestError as exc:
            self._write_error(400, exc)
            return

        pack_id = body.get("pack_id") if isinstance(body, Mapping) else None
        if not isinstance(pack_id, str) or not pack_id:
            self._write_error(
                400,
                ConnectorRequestError(
                    "missing required field 'pack_id'",
                    context={
                        "received_fields": tuple(sorted(body.keys())) if isinstance(body, Mapping) else (),
                    },
                ),
            )
            return

        state = self._state()
        with state.lock:
            if state.is_ready():
                self._write_error(
                    409,
                    ConnectorStateError(
                        "session already active; call /teardown first",
                        context={"current_state": "READY"},
                    ),
                )
                return

            try:
                pack = state.resolve_pack(pack_id)
            except PackNotFoundError as exc:
                self._write_error(422, exc)
                return

            try:
                state.initialize(pack)
            except OpenDSSError as exc:
                self._write_error(500, exc)
                return
            except ConnectorError as exc:
                self._write_error(500, exc)
                return

        self._write_json(200, _OK_BODY)

    # --- /execute ------------------------------------------------------

    def _handle_execute(self) -> None:
        try:
            body = self._read_json_body()
        except ConnectorRequestError as exc:
            self._write_error(400, exc)
            return

        step_raw = body.get("step") if isinstance(body, Mapping) else None
        if not isinstance(step_raw, int) or isinstance(step_raw, bool):
            self._write_error(
                400,
                ConnectorRequestError(
                    "'step' must be an integer",
                    context={"received_type": type(step_raw).__name__},
                ),
            )
            return

        context_raw = body.get("context", [])
        if not isinstance(context_raw, list):
            self._write_error(
                400,
                ConnectorRequestError(
                    "'context' must be a JSON array of [key, value] pairs",
                    context={"received_type": type(context_raw).__name__},
                ),
            )
            return
        try:
            context_pairs = tuple((str(pair[0]), pair[1]) for pair in context_raw if self._is_pair(pair))
            if len(context_pairs) != len(context_raw):
                raise ValueError("each context entry must be a 2-element array")
            _ = as_params(context_pairs)  # validate; pass-through for now
        except (TypeError, ValueError) as exc:
            self._write_error(
                400,
                ConnectorRequestError(
                    f"invalid 'context' shape: {exc}",
                    cause=exc,
                ),
            )
            return

        state = self._state()
        started = datetime.now(tz=UTC)
        with state.lock:
            if not state.is_ready():
                self._write_error(
                    409,
                    ConnectorStateError(
                        "no active session; call /initialize first",
                        context={"current_state": "UNINITIALIZED"},
                    ),
                )
                return

            try:
                output = state.step(step_raw)
            except OpenDSSError as exc:
                self._write_error(500, exc)
                return
            except ConnectorError as exc:
                self._write_error(500, exc)
                return

        result = _output_to_step_result(output, started)
        body_bytes = json.dumps(result.to_dict(), separators=(",", ":")).encode("utf-8")
        self._write_json(200, body_bytes)

    @staticmethod
    def _is_pair(value: object) -> bool:
        return isinstance(value, list) and len(value) == 2 and isinstance(value[0], str)

    # --- /teardown -----------------------------------------------------

    def _handle_teardown(self) -> None:
        state = self._state()
        with state.lock:
            if not state.is_ready():
                self._write_error(
                    409,
                    ConnectorStateError(
                        "no active session to teardown",
                        context={"current_state": "UNINITIALIZED"},
                    ),
                )
                return
            state.teardown()
        self._write_json(200, _OK_BODY)

    # --- helpers -------------------------------------------------------

    def _state(self) -> DaemonState:
        return cast(DaemonServer, self.server).state

    def _read_json_body(self) -> dict[str, Any]:
        length_header = self.headers.get("Content-Length")
        if length_header is None:
            return {}
        try:
            length = int(length_header)
        except ValueError as exc:
            raise ConnectorRequestError(
                f"invalid Content-Length: {length_header!r}",
                cause=exc,
            ) from exc
        if length <= 0:
            return {}
        raw = self.rfile.read(length)
        try:
            parsed = json.loads(raw.decode("utf-8"))
        except json.JSONDecodeError as exc:
            raise ConnectorRequestError(
                f"request body is not valid JSON: {exc.msg}",
                context={"pos": exc.pos},
                cause=exc,
            ) from exc
        if not isinstance(parsed, dict):
            raise ConnectorRequestError(
                f"request body must be a JSON object, got {type(parsed).__name__}",
            )
        return parsed

    def _write_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def _write_error(self, status: int, err: GridflowError) -> None:
        payload = json.dumps(err.to_dict(), separators=(",", ":")).encode("utf-8")
        self._write_json(status, payload)

    def log_message(self, format: str, *args: Any) -> None:
        # Silence default BaseHTTPServer stderr logging.
        del format, args


# ----------------------------------------------------------------- helpers


def _output_to_step_result(output: ConnectorStepOutput, started: datetime) -> StepResult:
    """Convert a ``ConnectorStepOutput`` to a wire-format ``StepResult``."""
    status = StepStatus.SUCCESS if output.converged else StepStatus.ERROR
    elapsed_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000.0
    return StepResult(
        step_id=output.step,
        timestamp=datetime.now(tz=UTC),
        status=status,
        elapsed_ms=elapsed_ms,
        node_result=output.node_result,
        error=None if output.converged else "solver did not converge",
    )


def _default_file_registry() -> ScenarioRegistry:
    """Build the default ``$GRIDFLOW_HOME/packs`` file-based registry."""
    import os
    from pathlib import Path

    from gridflow.infra.scenario import FileScenarioRegistry

    root = Path(os.environ.get("GRIDFLOW_HOME", str(Path.home() / ".gridflow")))
    return FileScenarioRegistry(root / "packs")


# ----------------------------------------------------------------- public factory


def build_daemon_base(
    host: str,
    port: int,
    *,
    health_message: str,
    connector_factory: Callable[[], ConnectorInterface],
    registry: ScenarioRegistry | None = None,
) -> ThreadingHTTPServer:
    """Build (but do not start) a connector REST daemon.

    Each ``gridflow.connectors.<name>`` shim calls this with its own
    health message and default connector factory.

    Args:
        host: Bind address. ``0.0.0.0`` inside Docker, ``127.0.0.1`` in tests.
        port: Bind port. Pass ``0`` in tests to pick an ephemeral port.
        health_message: String returned in the ``GET /health`` JSON body.
        connector_factory: Callable producing a fresh
            :class:`ConnectorInterface` per session.
        registry: Scenario registry. Defaults to
            :class:`FileScenarioRegistry` rooted at ``$GRIDFLOW_HOME/packs``.
    """
    health_body = json.dumps(
        {"healthy": True, "message": health_message},
        separators=(",", ":"),
    ).encode("utf-8")
    state = DaemonState(
        registry=registry if registry is not None else _default_file_registry(),
        connector_factory=connector_factory,
        health_body=health_body,
    )
    return DaemonServer((host, port), ConnectorHandler, state)


def run_daemon_loop(
    daemon: ThreadingHTTPServer,
    *,
    log_name: str,
    host: str,
    port: int,
) -> None:
    """Block on the daemon's serve_forever loop with structlog notifications."""
    log = get_logger(log_name)
    log.info(f"{log_name}_started", host=host, port=port)
    try:
        daemon.serve_forever()
    except KeyboardInterrupt:
        log.info(f"{log_name}_interrupted")
    finally:
        daemon.server_close()
        log.info(f"{log_name}_stopped")
