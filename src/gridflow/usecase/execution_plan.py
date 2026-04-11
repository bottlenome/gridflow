"""UseCase-layer ``ExecutionPlan`` + ``StepConfig``.

Spec: docs/detailed_design/03b_usecase_classes.md §3.3.4 / §3.3.5.

``ExecutionPlan`` is the UseCase-layer view of an in-flight experiment.
It is passed to :meth:`OrchestratorRunner.prepare` so the runner can
provision its execution backend (in-process connector instances, Docker
services, remote workers, …). Being a pure, frozen dataclass it is
hashable and safe to cache / log.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from gridflow.domain.scenario import ScenarioPack
from gridflow.domain.util.params import Params


@dataclass(frozen=True)
class StepConfig:
    """Per-step configuration inside an :class:`ExecutionPlan`.

    Phase 1 MVP carries only ``step_id``; future phases may add per-step
    overrides (time deltas, context parameters) without breaking the
    surrounding :class:`ExecutionPlan` shape.
    """

    step_id: int


@dataclass(frozen=True)
class ExecutionPlan:
    """Frozen, hashable description of "what to run" for an experiment.

    Attributes:
        experiment_id: Unique experiment identifier assigned by the
            :class:`Orchestrator` before :meth:`OrchestratorRunner.prepare`
            is called.
        pack: Scenario Pack the experiment is based on.
        steps: Ordered tuple of :class:`StepConfig` entries describing the
            per-step schedule.
        connectors: Tuple of connector IDs that must be available for this
            experiment (e.g. ``("opendss",)``). The runner is responsible
            for resolving these IDs to concrete backends.
        parameters: Free-form run parameters in the canonical frozen
            params-tuple form (CLAUDE.md §0.1).
    """

    experiment_id: str
    pack: ScenarioPack
    steps: tuple[StepConfig, ...]
    connectors: tuple[str, ...]
    parameters: Params = field(default_factory=tuple)
