"""Use-case layer Orchestrator (business logic only).

Spec: docs/detailed_design/03b_usecase_classes.md §3.3.2.

Responsibility split (CLAUDE.md §0.3, spec 03b §3.3):
    * :class:`Orchestrator` — **UseCase** — decides *what* to run: resolves
      the pack, builds an :class:`ExecutionPlan`, drives the injected
      :class:`OrchestratorRunner`, assembles an :class:`ExperimentResult`,
      and manages pack lifecycle status. It knows nothing about Docker,
      subprocess, or REST.
    * :class:`InProcessOrchestratorRunner` / :class:`ContainerOrchestratorRunner`
      — **Infra** — know *how* to physically execute connectors
      (in-process vs. Docker Compose + REST).

The two halves communicate through the
:class:`gridflow.usecase.interfaces.OrchestratorRunner` Protocol which
takes an :class:`ExecutionPlan` in ``prepare()`` and a
``(connector_id, step, context)`` triple in ``run_connector()`` so the
runner never sees a live :class:`ConnectorInterface` object.
"""

from __future__ import annotations

import time
import uuid
from dataclasses import dataclass
from datetime import UTC, datetime

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.error import OrchestratorError, PackNotFoundError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import PackStatus, ScenarioRegistry
from gridflow.domain.util.params import as_params
from gridflow.usecase.execution_plan import ExecutionPlan, StepConfig
from gridflow.usecase.interfaces import OrchestratorRunner
from gridflow.usecase.result import ExperimentResult, StepResult


@dataclass(frozen=True)
class RunRequest:
    """Inputs needed to start an experiment.

    Attributes:
        pack_id: Registered Scenario Pack identifier.
        connector_id: Connector registered with the
            :class:`OrchestratorRunner` (e.g. ``"opendss"``). The runner
            resolves the ID to a physical backend.
        total_steps: Number of solver steps to run (``> 0``).
        seed: Optional override for the scenario seed.
        experiment_id: Optional pre-assigned experiment identifier.
            When ``None`` the orchestrator generates one.
    """

    pack_id: str
    connector_id: str = "opendss"
    total_steps: int = 1
    seed: int | None = None
    experiment_id: str | None = None


class Orchestrator:
    """High-level "run an experiment" use case.

    Lifecycle (spec 03b §3.3.2):
        1. Resolve the pack via the injected :class:`ScenarioRegistry`.
           Fail fast with :class:`PackNotFoundError`.
        2. Validate request (``total_steps > 0``).
        3. Transition pack → ``RUNNING``.
        4. Build an :class:`ExecutionPlan` and call ``runner.prepare``.
        5. Loop over steps, calling ``runner.run_connector`` once per
           ``(connector_id, step_config)`` pair.
        6. Always call ``runner.teardown`` (best-effort) before exiting.
        7. On success, transition pack → ``COMPLETED`` and build an
           :class:`ExperimentResult`.

    Runner errors surface to the caller unchanged so the caller can act
    on the error code (e.g. retry vs. reconfigure).
    """

    def __init__(self, *, registry: ScenarioRegistry, runner: OrchestratorRunner) -> None:
        self._registry = registry
        self._runner = runner

    def run(self, request: RunRequest) -> ExperimentResult:
        if request.total_steps <= 0:
            raise OrchestratorError(
                f"total_steps must be positive, got {request.total_steps}",
                context={"pack_id": request.pack_id},
            )

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

        pack = self._registry.update_status(pack.pack_id, PackStatus.RUNNING)

        experiment_id = request.experiment_id or f"exp-{uuid.uuid4().hex[:12]}"
        plan = ExecutionPlan(
            experiment_id=experiment_id,
            pack=pack,
            steps=tuple(StepConfig(step_id=i) for i in range(request.total_steps)),
            connectors=(request.connector_id,),
            parameters=as_params({"total_steps": request.total_steps}),
        )

        start_wall = time.perf_counter()
        step_results: list[StepResult] = []
        try:
            self._runner.prepare(plan)
            try:
                for step_cfg in plan.steps:
                    for connector_id in plan.connectors:
                        step_result = self._runner.run_connector(connector_id, step_cfg.step_id, ())
                        step_results.append(step_result)
            finally:
                self._runner.teardown()
        except PackNotFoundError:
            raise
        except OrchestratorError:
            raise
        except Exception as exc:
            # Surface runner / connector errors as-is when they are already
            # well-typed; wrap stray exceptions in OrchestratorError.
            from gridflow.domain.error import GridflowError

            if isinstance(exc, GridflowError):
                raise
            raise OrchestratorError(
                f"Experiment '{experiment_id}' failed",
                context={"pack_id": pack.pack_id, "experiment_id": experiment_id},
                cause=exc,
            ) from exc

        elapsed_s = time.perf_counter() - start_wall
        self._registry.update_status(pack.pack_id, PackStatus.COMPLETED)

        node_results = _aggregate_node_results(tuple(step_results))
        metadata = ExperimentMetadata(
            experiment_id=experiment_id,
            created_at=datetime.now(tz=UTC),
            scenario_pack_id=pack.pack_id,
            connector=request.connector_id,
            seed=request.seed if request.seed is not None else pack.metadata.seed,
            parameters=as_params({"total_steps": request.total_steps}),
        )
        return ExperimentResult(
            experiment_id=experiment_id,
            metadata=metadata,
            steps=tuple(step_results),
            node_results=node_results,
            elapsed_s=elapsed_s,
        )


# ----------------------------------------------------------------- helpers


def _aggregate_node_results(steps: tuple[StepResult, ...]) -> tuple[NodeResult, ...]:
    """Collapse per-step voltage snapshots into a single final NodeResult.

    Mirrors the pre-refactor aggregation: experiment results carry the
    final step's bus voltages as an aggregate ``NodeResult``. Extending
    to per-step time-series is a later-phase concern.
    """
    if not steps:
        return ()
    final = steps[-1].node_result
    return (final,) if final is not None else ()
