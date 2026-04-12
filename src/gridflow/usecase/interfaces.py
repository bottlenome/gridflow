"""Use-case level Protocols shared between orchestration and adapter layers.

These Protocols live in the Use Case layer so Domain stays dependency-free
and Adapter/Infra concrete classes can implement them structurally.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Protocol, runtime_checkable

from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import ScenarioPack
from gridflow.domain.util.params import Params

if TYPE_CHECKING:
    from gridflow.usecase.execution_plan import ExecutionPlan
    from gridflow.usecase.result import StepResult


@dataclass(frozen=True)
class ConnectorStepOutput:
    """One step's worth of data emitted by a Connector.

    Frozen so it composes cleanly with :class:`~gridflow.usecase.result.StepResult`.

    Attributes:
        step: Monotonic step index (0-based).
        node_result: Node voltages captured at this step. ``None`` when the
            connector emits no node data (e.g. initialization-only step).
        converged: ``True`` iff the underlying solver reached convergence.
        metadata: Free-form extra info (iterations, residuals, …).
    """

    step: int
    node_result: NodeResult | None
    converged: bool
    metadata: tuple[tuple[str, object], ...] = ()


@dataclass(frozen=True)
class HealthStatus:
    """Connector / runner health probe result.

    Spec: docs/detailed_design/03b_usecase_classes.md §3.5.5.

    Attributes:
        healthy: ``True`` when the probed component is operational.
        message: Human-readable status detail (empty string allowed).
    """

    healthy: bool
    message: str


@runtime_checkable
class ConnectorInterface(Protocol):
    """Contract for simulation connectors (OpenDSS, pandapower, …).

    Life-cycle:
        1. :meth:`initialize` — called once per experiment, loads network data.
        2. :meth:`step` — called per time step; returns a
           :class:`ConnectorStepOutput`.
        3. :meth:`teardown` — called once per experiment; releases resources.

    Implementations must be self-contained: no cross-call global state that
    would break :meth:`initialize` / :meth:`teardown` symmetry.
    """

    name: str

    def initialize(self, pack: ScenarioPack) -> None:
        """Load the circuit described by ``pack``."""
        ...

    def step(self, step_index: int) -> ConnectorStepOutput:
        """Execute a single solver step and return node-level results."""
        ...

    def teardown(self) -> None:
        """Release any solver / OS resources."""
        ...


@runtime_checkable
class OrchestratorRunner(Protocol):
    """Physical-execution-backend boundary for the UseCase ``Orchestrator``.

    Spec: docs/detailed_design/03b_usecase_classes.md §3.3.3.

    The runner contract hides whether execution happens in-process, in a
    Docker container, over REST, or on a remote worker. ``Orchestrator``
    depends only on this Protocol and therefore knows nothing about
    Docker / subprocess / HTTP.

    Error contract (spec 03d §3.8.2):
        * ``prepare()`` raises ``RunnerStartError`` on backend
          start-up failure.
        * ``run_connector()`` raises ``ConnectorCommunicationError`` on
          transport failure and ``ConnectorNotFoundError`` when the
          ``connector_id`` is unknown to the runner. Solver failures
          inside the connector surface as ``SimulationError``.
        * ``teardown()`` is best-effort: errors are logged but not raised.
    """

    def prepare(self, plan: ExecutionPlan) -> None:
        """Provision the backend (start containers, instantiate connectors, …)."""
        ...

    def run_connector(
        self,
        connector_id: str,
        step: int,
        context: Params,
    ) -> StepResult:
        """Execute one step against ``connector_id`` and return the result."""
        ...

    def health_check(self, connector_id: str) -> HealthStatus:
        """Report the health of a registered connector."""
        ...

    def teardown(self) -> None:
        """Release every backend resource acquired by :meth:`prepare`."""
        ...
