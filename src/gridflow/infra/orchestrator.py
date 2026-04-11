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
from collections.abc import Callable
from datetime import UTC, datetime

from gridflow.domain.error import (
    ConnectorError,
    ConnectorNotFoundError,
    OpenDSSError,
    SimulationError,
)
from gridflow.domain.util.params import Params
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
    """Docker-Compose-backed runner stub (spec 03d §3.8.2).

    Full implementation lands in a later unit — right now the class only
    needs to satisfy the new :class:`OrchestratorRunner` Protocol so that
    DI wiring and type checking succeed. Every method raises a concrete
    error so accidental use fails loudly.
    """

    def prepare(self, plan: ExecutionPlan) -> None:
        from gridflow.domain.error import ContainerError

        raise ContainerError(
            "ContainerOrchestratorRunner.prepare is not implemented yet",
            context={"experiment_id": plan.experiment_id},
        )

    def run_connector(
        self,
        connector_id: str,
        step: int,
        context: Params,
    ) -> StepResult:
        from gridflow.domain.error import ContainerError

        del context
        raise ContainerError(
            "ContainerOrchestratorRunner.run_connector is not implemented yet",
            context={"connector_id": connector_id, "step": step},
        )

    def health_check(self, connector_id: str) -> HealthStatus:
        return HealthStatus(
            healthy=False,
            message=f"ContainerOrchestratorRunner is not implemented (connector_id={connector_id})",
        )

    def teardown(self) -> None:
        # No-op for the stub — nothing was prepared.
        return
