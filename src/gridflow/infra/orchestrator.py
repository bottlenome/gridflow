"""Infrastructure runners implementing :class:`OrchestratorRunner`.

Two flavours ship with MVP:
    * :class:`InProcessOrchestratorRunner` — drives the connector directly
      inside the current Python process. Fast, deterministic, used by the
      CLI ``gridflow run`` default path.
    * :class:`ContainerOrchestratorRunner` — stub that documents the future
      Docker-based execution path (phase0_result §7.2 5.6). It currently
      raises ``ContainerError`` so callers fail fast if they ask for it.
"""

from __future__ import annotations

from gridflow.domain.error import ContainerError, OpenDSSError, SimulationError
from gridflow.domain.scenario import ScenarioPack
from gridflow.usecase.interfaces import (
    ConnectorInterface,
    ConnectorStepOutput,
    OrchestratorRunner,
)


class InProcessOrchestratorRunner(OrchestratorRunner):
    """Drive a connector in the current process."""

    def run_connector(
        self, connector: ConnectorInterface, pack: ScenarioPack, total_steps: int
    ) -> tuple[ConnectorStepOutput, ...]:
        connector.initialize(pack)
        outputs: list[ConnectorStepOutput] = []
        try:
            for step_index in range(total_steps):
                outputs.append(connector.step(step_index))
        except OpenDSSError:
            raise
        except Exception as exc:
            raise SimulationError(
                f"Connector '{connector.name}' step failed",
                context={"connector": connector.name, "pack_id": pack.pack_id},
                cause=exc,
            ) from exc
        finally:
            connector.teardown()
        return tuple(outputs)


class ContainerOrchestratorRunner(OrchestratorRunner):
    """Future Docker-based runner. Not implemented for MVP.

    Present as a type anchor so DI wiring can reference it now; attempting to
    call :meth:`run_connector` raises ``ContainerError``.
    """

    def run_connector(
        self, connector: ConnectorInterface, pack: ScenarioPack, total_steps: int
    ) -> tuple[ConnectorStepOutput, ...]:
        raise ContainerError(
            "ContainerOrchestratorRunner is not implemented in MVP. Use InProcessOrchestratorRunner instead.",
            context={"connector": connector.name, "pack_id": pack.pack_id},
        )
