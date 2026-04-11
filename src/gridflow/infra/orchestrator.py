"""Infrastructure runners implementing :class:`OrchestratorRunner`.

Spec: docs/detailed_design/03b_usecase_classes.md §3.3.3 (UseCase
Protocol) + docs/detailed_design/03d_infra_classes.md §3.8.2 / §3.8.3
(Container implementation).

Two flavours ship with gridflow:

    * :class:`InProcessOrchestratorRunner` — instantiates connectors in
      the current Python process via an injected factory registry. Used
      by local development, unit/E2E tests, and the bare ``gridflow``
      CLI when run outside Docker Compose.
    * :class:`ContainerOrchestratorRunner` — Docker-Compose-backed
      runner that drives connector daemons over REST per
      03b §3.5.6. Implemented in a later unit — this module currently
      ships a stub that satisfies the Protocol so DI wiring compiles.

Both runners speak the same UseCase-level :class:`OrchestratorRunner`
contract so the UseCase ``Orchestrator`` is completely agnostic to the
physical execution backend.
"""

from __future__ import annotations

import contextlib
import json
from collections.abc import Callable
from datetime import UTC, datetime
from typing import Any

import httpx

from gridflow.domain.error import (
    ConnectorCommunicationError,
    ConnectorError,
    ConnectorNotFoundError,
    ContainerStartError,
    OpenDSSError,
    RunnerStartError,
    SimulationError,
)
from gridflow.domain.result import NodeResult
from gridflow.domain.util.params import Params
from gridflow.infra.container_manager import ContainerEndpoint, ContainerManager
from gridflow.infra.logging import get_logger
from gridflow.usecase.execution_plan import ExecutionPlan
from gridflow.usecase.interfaces import (
    ConnectorInterface,
    HealthStatus,
    OrchestratorRunner,
)
from gridflow.usecase.result import StepResult, StepStatus


class InProcessOrchestratorRunner(OrchestratorRunner):
    """Drive connectors in the current Python process.

    The runner owns a registry of factories (``{connector_id: Callable}``)
    and creates a fresh connector per experiment inside :meth:`prepare`.
    This keeps per-experiment state isolated while allowing the same
    ``connector_id`` to be reused across multiple experiments.

    Attributes:
        _factories: Callable per connector ID returning a fresh
            :class:`ConnectorInterface` instance. Injected at construction
            (typically by the CLI / DI wiring).
        _connectors: Currently live ``connector_id → ConnectorInterface``
            map. Populated by :meth:`prepare`, cleared by :meth:`teardown`.
    """

    def __init__(
        self,
        connector_factories: dict[str, Callable[[], ConnectorInterface]] | None = None,
    ) -> None:
        self._factories: dict[str, Callable[[], ConnectorInterface]] = dict(connector_factories or {})
        self._connectors: dict[str, ConnectorInterface] = {}

    # -------------------------------------------------------- lifecycle

    def prepare(self, plan: ExecutionPlan) -> None:
        for connector_id in plan.connectors:
            factory = self._factories.get(connector_id)
            if factory is None:
                raise ConnectorNotFoundError(
                    f"connector '{connector_id}' is not registered with the runner",
                    context={
                        "connector_id": connector_id,
                        "registered": tuple(sorted(self._factories.keys())),
                    },
                )
            connector = factory()
            try:
                connector.initialize(plan.pack)
            except Exception:
                with contextlib.suppress(Exception):
                    connector.teardown()
                raise
            self._connectors[connector_id] = connector

    def run_connector(
        self,
        connector_id: str,
        step: int,
        context: Params,
    ) -> StepResult:
        del context  # informational; in-process runner does not forward it yet
        connector = self._connectors.get(connector_id)
        if connector is None:
            raise ConnectorNotFoundError(
                f"connector '{connector_id}' is not prepared",
                context={
                    "connector_id": connector_id,
                    "prepared": tuple(sorted(self._connectors.keys())),
                },
            )
        started = datetime.now(tz=UTC)
        try:
            output = connector.step(step)
        except OpenDSSError:
            raise
        except ConnectorError:
            raise
        except Exception as exc:
            raise SimulationError(
                f"connector '{connector_id}' step {step} failed",
                context={"connector_id": connector_id, "step": step},
                cause=exc,
            ) from exc
        elapsed_ms = (datetime.now(tz=UTC) - started).total_seconds() * 1000.0
        status = StepStatus.SUCCESS if output.converged else StepStatus.ERROR
        return StepResult(
            step_id=output.step,
            timestamp=datetime.now(tz=UTC),
            status=status,
            elapsed_ms=elapsed_ms,
            node_result=output.node_result,
            error=None if output.converged else "solver did not converge",
        )

    def health_check(self, connector_id: str) -> HealthStatus:
        if connector_id in self._connectors:
            return HealthStatus(healthy=True, message="in-process connector ready")
        return HealthStatus(
            healthy=False,
            message=f"connector '{connector_id}' is not prepared",
        )

    def teardown(self) -> None:
        for connector in self._connectors.values():
            with contextlib.suppress(Exception):
                connector.teardown()
        self._connectors.clear()


class ContainerOrchestratorRunner(OrchestratorRunner):
    """Docker-Compose-backed runner (spec 03d §3.8.2).

    Flow:
        1. ``prepare(plan)`` asks the injected
           :class:`ContainerManager` to ``start`` every Docker service
           referenced by ``plan.connectors`` (resolved via the
           ``endpoints`` map), then POSTs ``/initialize`` to each
           connector daemon so each session transitions
           ``UNINITIALIZED → READY``.
        2. ``run_connector(connector_id, step, context)`` POSTs
           ``/execute`` to the daemon addressed by ``endpoints[connector_id]``
           and returns the deserialised :class:`StepResult`.
        3. ``teardown()`` POSTs ``/teardown`` (best-effort) to every active
           daemon, then asks the :class:`ContainerManager` to ``stop``
           all services. Always runnable, even if the daemons are gone.

    Errors surface as spec-compliant Infra-layer exceptions:
        * :class:`RunnerStartError` (E-40005) on prepare failure.
        * :class:`ConnectorCommunicationError` (E-40006) on transport
          failure (timeout, connection refused, unexpected HTTP status).
        * :class:`ConnectorNotFoundError` (E-40007) when the runner
          receives a ``connector_id`` it has no endpoint for.
    """

    # Timeouts are conservative — the connector daemon answers in
    # milliseconds inside Docker Compose, so anything longer than a
    # second indicates a real problem.
    _DEFAULT_TIMEOUT_S = 5.0

    def __init__(
        self,
        *,
        container_manager: ContainerManager,
        endpoints: dict[str, ContainerEndpoint],
        timeout_s: float = _DEFAULT_TIMEOUT_S,
    ) -> None:
        self._manager = container_manager
        self._endpoints: dict[str, ContainerEndpoint] = dict(endpoints)
        self._timeout_s = timeout_s
        self._active: set[str] = set()
        self._log = get_logger("gridflow.infra.container_runner")

    # -------------------------------------------------------- lifecycle

    def prepare(self, plan: ExecutionPlan) -> None:
        # 1. Validate every connector_id up-front so we fail fast before
        #    touching Docker.
        for connector_id in plan.connectors:
            if connector_id not in self._endpoints:
                raise ConnectorNotFoundError(
                    f"no endpoint registered for connector '{connector_id}'",
                    context={
                        "connector_id": connector_id,
                        "registered": tuple(sorted(self._endpoints.keys())),
                    },
                )

        services = tuple(self._endpoints[cid].service_name for cid in plan.connectors)

        # 2. Start Docker services. Failure → RunnerStartError.
        try:
            self._manager.start(services)
        except ContainerStartError as exc:
            raise RunnerStartError(
                f"failed to start services {services!r}",
                context={"services": services},
                cause=exc,
            ) from exc

        # 3. Initialize each connector via REST. If initialization fails
        #    for any connector, tear the whole thing down and re-raise as
        #    RunnerStartError so the caller sees a single well-typed error.
        try:
            for connector_id in plan.connectors:
                self._post_initialize(connector_id, plan.pack.pack_id)
                self._active.add(connector_id)
        except Exception:
            self._best_effort_teardown(services)
            raise

    def run_connector(
        self,
        connector_id: str,
        step: int,
        context: Params,
    ) -> StepResult:
        endpoint = self._endpoints.get(connector_id)
        if endpoint is None:
            raise ConnectorNotFoundError(
                f"no endpoint registered for connector '{connector_id}'",
                context={"connector_id": connector_id},
            )
        body = {"step": step, "context": [list(pair) for pair in context]}
        payload = self._post(
            endpoint,
            "/execute",
            body,
            connector_id=connector_id,
            error_context={"step": step},
        )
        return _step_result_from_payload(payload)

    def health_check(self, connector_id: str) -> HealthStatus:
        endpoint = self._endpoints.get(connector_id)
        if endpoint is None:
            return HealthStatus(
                healthy=False,
                message=f"no endpoint registered for connector '{connector_id}'",
            )
        try:
            return self._manager.health_check(endpoint.service_name)
        except Exception as exc:  # pragma: no cover - depends on manager impl
            return HealthStatus(
                healthy=False,
                message=f"container manager error: {exc}",
            )

    def teardown(self) -> None:
        # 1. Best-effort POST /teardown to every active daemon so that
        #    the connector releases its solver resources cleanly.
        for connector_id in tuple(self._active):
            endpoint = self._endpoints.get(connector_id)
            if endpoint is None:
                continue
            with contextlib.suppress(Exception):
                self._post(
                    endpoint,
                    "/teardown",
                    {},
                    connector_id=connector_id,
                    error_context={},
                )
        self._active.clear()

        # 2. Stop every docker service we started. Manager errors are
        #    swallowed — teardown must always succeed from the caller's
        #    point of view.
        services = tuple(ep.service_name for ep in self._endpoints.values())
        if services:
            with contextlib.suppress(Exception):
                self._manager.stop(services)

    # --------------------------------------------------------- helpers

    def _post_initialize(self, connector_id: str, pack_id: str) -> None:
        endpoint = self._endpoints[connector_id]
        try:
            self._post(
                endpoint,
                "/initialize",
                {"pack_id": pack_id},
                connector_id=connector_id,
                error_context={"pack_id": pack_id},
            )
        except ConnectorCommunicationError as exc:
            raise RunnerStartError(
                f"failed to initialize connector '{connector_id}' at {endpoint.base_url}",
                context={
                    "connector_id": connector_id,
                    "pack_id": pack_id,
                    "base_url": endpoint.base_url,
                },
                cause=exc,
            ) from exc

    def _post(
        self,
        endpoint: ContainerEndpoint,
        path: str,
        body: dict[str, Any],
        *,
        connector_id: str,
        error_context: dict[str, object],
    ) -> dict[str, Any]:
        """POST JSON to a connector daemon and return the decoded JSON body.

        Wraps all transport-layer failures (timeouts, connection errors,
        unexpected HTTP statuses) as ``ConnectorCommunicationError`` so
        callers never see an httpx exception.
        """
        url = endpoint.base_url.rstrip("/") + path
        try:
            response = httpx.post(
                url,
                json=body,
                timeout=self._timeout_s,
            )
        except httpx.HTTPError as exc:
            raise ConnectorCommunicationError(
                f"HTTP POST {path} to {url} failed: {exc}",
                context={
                    "connector_id": connector_id,
                    "url": url,
                    **error_context,
                },
                cause=exc,
            ) from exc

        if response.status_code >= 400:
            try:
                err_payload = response.json()
            except json.JSONDecodeError:
                err_payload = {"error_code": "E-40006", "message": response.text}
            raise ConnectorCommunicationError(
                f"HTTP POST {path} returned {response.status_code}: {err_payload.get('message', '')}",
                context={
                    "connector_id": connector_id,
                    "url": url,
                    "http_status": response.status_code,
                    "remote_error_code": err_payload.get("error_code"),
                    **error_context,
                },
            )

        try:
            parsed = response.json()
        except json.JSONDecodeError as exc:
            raise ConnectorCommunicationError(
                f"HTTP POST {path} returned invalid JSON",
                context={"connector_id": connector_id, "url": url, **error_context},
                cause=exc,
            ) from exc
        if not isinstance(parsed, dict):
            raise ConnectorCommunicationError(
                f"HTTP POST {path} returned non-object JSON",
                context={"connector_id": connector_id, "url": url, **error_context},
            )
        return parsed

    def _best_effort_teardown(self, services: tuple[str, ...]) -> None:
        """Called from prepare() when initialize fails for any connector.

        Tries to tear down already-initialized daemons and stop all
        services. Any error is swallowed — the caller will get a well-
        typed RunnerStartError regardless.
        """
        for connector_id in tuple(self._active):
            endpoint = self._endpoints.get(connector_id)
            if endpoint is not None:
                with contextlib.suppress(Exception):
                    self._post(
                        endpoint,
                        "/teardown",
                        {},
                        connector_id=connector_id,
                        error_context={},
                    )
        self._active.clear()
        with contextlib.suppress(Exception):
            self._manager.stop(services)


# ----------------------------------------------------------------- helpers


def _step_result_from_payload(payload: dict[str, Any]) -> StepResult:
    """Deserialise a ``StepResult`` JSON payload produced by 03b §3.5.6."""
    nr_raw = payload.get("node_result")
    node_result: NodeResult | None = None
    if isinstance(nr_raw, dict):
        node_result = NodeResult(
            node_id=str(nr_raw["node_id"]),
            voltages=tuple(float(v) for v in nr_raw["voltages"]),
        )
    status_str = str(payload.get("status", "success"))
    try:
        status = StepStatus(status_str)
    except ValueError:
        status = StepStatus.SUCCESS
    timestamp_raw = payload.get("timestamp")
    timestamp = datetime.fromisoformat(timestamp_raw) if isinstance(timestamp_raw, str) else datetime.now(tz=UTC)
    return StepResult(
        step_id=int(payload["step_id"]),
        timestamp=timestamp,
        status=status,
        elapsed_ms=float(payload.get("elapsed_ms", 0.0)),
        node_result=node_result,
        error=payload.get("error"),
    )
