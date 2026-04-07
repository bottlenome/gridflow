"""Use-case layer Orchestrator (business logic only).

Responsibility split (phase0_result §7.2 5.6, CLAUDE.md §0.3):
    * :class:`Orchestrator` — **UseCase** — decides *what* to run: resolves the
      pack from the registry, drives the runner, assembles the ExperimentResult,
      transitions lifecycle status. No Docker / subprocess / solver calls.
    * :class:`~gridflow.infra.orchestrator.InProcessOrchestratorRunner` and
      :class:`~gridflow.infra.orchestrator.ContainerOrchestratorRunner` — **Infra** —
      know *how* to execute a connector (in-process vs. Docker).

The two halves communicate through
:class:`~gridflow.usecase.interfaces.OrchestratorRunner`.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.error import OrchestratorError, PackNotFoundError, SimulationError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackStatus, ScenarioRegistry
from gridflow.domain.util.params import as_params
from gridflow.usecase.interfaces import (
    ConnectorInterface,
    ConnectorStepOutput,
    OrchestratorRunner,
)
from gridflow.usecase.result import ExperimentResult, StepResult, StepStatus


@dataclass(frozen=True)
class RunRequest:
    """Inputs needed to start an experiment."""

    pack_id: str
    connector: ConnectorInterface
    total_steps: int = 1
    seed: int | None = None
    experiment_id: str | None = None


class Orchestrator:
    """High-level "run an experiment" use case."""

    def __init__(self, *, registry: ScenarioRegistry, runner: OrchestratorRunner) -> None:
        self._registry = registry
        self._runner = runner

    def run(self, request: RunRequest) -> ExperimentResult:
        """Drive a full experiment and return the aggregated result.

        Lifecycle:
            1. Fetch the pack; fail fast with ``PackNotFoundError``.
            2. Transition pack → ``RUNNING``.
            3. Invoke the runner.
            4. Transition pack → ``COMPLETED`` on success.
            5. Build an :class:`ExperimentResult`.

        Failures during execution re-raise as ``SimulationError`` /
        ``OrchestratorError`` with the pack lifecycle left at ``RUNNING`` so
        operators can inspect and retry.
        """
        try:
            pack = self._registry.get(request.pack_id)
        except PackNotFoundError:
            raise
        except Exception as exc:  # pragma: no cover - defensive
            raise OrchestratorError(
                f"Failed to resolve pack '{request.pack_id}'",
                context={"pack_id": request.pack_id},
                cause=exc,
            ) from exc

        if request.total_steps <= 0:
            raise OrchestratorError(
                f"total_steps must be positive, got {request.total_steps}",
                context={"pack_id": request.pack_id},
            )

        pack = self._registry.update_status(pack.pack_id, PackStatus.RUNNING)

        experiment_id = request.experiment_id or f"exp-{uuid.uuid4().hex[:12]}"
        start_wall = time.perf_counter()
        try:
            outputs = self._runner.run_connector(request.connector, pack, request.total_steps)
        except OrchestratorError:
            raise
        except Exception as exc:
            raise SimulationError(
                f"Connector '{request.connector.name}' failed for pack '{pack.pack_id}'",
                context={"pack_id": pack.pack_id, "connector": request.connector.name},
                cause=exc,
            ) from exc
        elapsed_s = time.perf_counter() - start_wall

        self._registry.update_status(pack.pack_id, PackStatus.COMPLETED)

        steps = tuple(_output_to_step_result(o) for o in outputs)
        node_results = _aggregate_node_results(outputs)
        metadata = ExperimentMetadata(
            experiment_id=experiment_id,
            created_at=datetime.now(tz=UTC),
            scenario_pack_id=pack.pack_id,
            connector=request.connector.name,
            seed=request.seed if request.seed is not None else pack.metadata.seed,
            parameters=as_params({"total_steps": request.total_steps}),
        )
        return ExperimentResult(
            experiment_id=experiment_id,
            metadata=metadata,
            steps=steps,
            node_results=node_results,
            elapsed_s=elapsed_s,
        )


# ----------------------------------------------------------------- helpers


def _output_to_step_result(output: ConnectorStepOutput) -> StepResult:
    status = StepStatus.SUCCESS if output.converged else StepStatus.ERROR
    return StepResult(
        step_id=output.step,
        timestamp=datetime.now(tz=UTC),
        status=status,
        elapsed_ms=0.0,
        node_result=output.node_result,
        error=None if output.converged else "solver did not converge",
    )


def _aggregate_node_results(outputs: tuple[ConnectorStepOutput, ...]) -> tuple[NodeResult, ...]:
    """Collapse per-step voltage vectors into a single ``NodeResult`` series."""
    if not outputs:
        return ()
    # Every step emits a single __network__ NodeResult whose ``voltages`` is
    # the full bus vector for that step. Stack them into one time-series.
    # For MVP we materialise a single aggregate NodeResult with the bus vector
    # for the FINAL step (most callers only need the converged snapshot).
    final = outputs[-1].node_result
    return (final,) if final is not None else ()
