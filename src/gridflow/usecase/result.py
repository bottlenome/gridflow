"""Use-case layer result types (StepResult, StepStatus, ExperimentResult).

Rationale (phase0_result §7.2 5.3 & 5.5 / detailed_design 03e):
    ``StepResult`` and ``ExperimentResult`` describe the outcome of orchestrated
    execution, which is a Use Case concern rather than a pure Domain concept —
    so both types live in ``gridflow.usecase.result``. The low-level time-series
    fixtures (NodeResult, BranchResult, …) stay in ``gridflow.domain.result``
    because they are value objects attached to the CDL.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result.results import (
    BranchResult,
    GeneratorResult,
    Interruption,
    LoadResult,
    NodeResult,
    RenewableResult,
)


class StepStatus(enum.Enum):
    """Lifecycle status of a single simulation step."""

    SUCCESS = "success"
    WARNING = "warning"
    ERROR = "error"


@dataclass(frozen=True)
class StepResult:
    """Outcome of a single orchestration step.

    Frozen so it is hashable and safe to place in experiment logs.

    Attributes:
        step_id: Monotonic step identifier (0-indexed within an experiment).
        timestamp: Wall-clock time at which the step completed.
        status: Step completion status.
        elapsed_ms: Execution time of the step in milliseconds.
        node_result: Node-level simulation output captured at this step.
            ``None`` when the step produced no node-level data (e.g. a
            setup/teardown step).
        error: Error message when ``status`` is :attr:`StepStatus.ERROR` /
            :attr:`StepStatus.WARNING`. ``None`` on success.
    """

    step_id: int
    timestamp: datetime
    status: StepStatus
    elapsed_ms: float
    node_result: NodeResult | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dict for logging / JSON export."""
        return {
            "step_id": self.step_id,
            "timestamp": self.timestamp.isoformat(),
            "status": self.status.value,
            "elapsed_ms": self.elapsed_ms,
            "node_result": None
            if self.node_result is None
            else {
                "node_id": self.node_result.node_id,
                "voltages": list(self.node_result.voltages),
            },
            "error": self.error,
        }


@dataclass(frozen=True)
class ExperimentResult:
    """Aggregated experiment result.

    Moved from ``gridflow.domain.result`` to the Use Case layer (phase0_result
    §7.2 5.5). The :attr:`metrics` field uses the frozen tuple-of-tuples
    convention to preserve hash-equality.

    Attributes:
        experiment_id: Unique experiment identifier.
        metadata: Experiment metadata.
        steps: Ordered per-step outcomes.
        node_results: Per-node aggregated results.
        branch_results: Per-branch results.
        load_results: Per-load results.
        generator_results: Per-generator results.
        renewable_results: Per-renewable results.
        interruptions: Outage event list.
        metrics: Computed metrics as a tuple of ``(name, value)`` pairs.
        elapsed_s: Total execution time (seconds).
    """

    experiment_id: str
    metadata: ExperimentMetadata
    steps: tuple[StepResult, ...] = ()
    node_results: tuple[NodeResult, ...] = ()
    branch_results: tuple[BranchResult, ...] = ()
    load_results: tuple[LoadResult, ...] = ()
    generator_results: tuple[GeneratorResult, ...] = ()
    renewable_results: tuple[RenewableResult, ...] = ()
    interruptions: tuple[Interruption, ...] = ()
    metrics: tuple[tuple[str, float], ...] = field(default_factory=tuple)
    elapsed_s: float = 0.0

    def metrics_dict(self) -> dict[str, float]:
        """Return a plain ``dict`` view of :attr:`metrics`."""
        return dict(self.metrics)

    def to_dict(self) -> dict[str, object]:
        """Convert to dict for logging / JSON export."""
        return {
            "experiment_id": self.experiment_id,
            "metadata": self.metadata.to_dict(),
            "steps": [s.to_dict() for s in self.steps],
            "node_results": [{"node_id": n.node_id, "voltages": list(n.voltages)} for n in self.node_results],
            "branch_results": [
                {
                    "edge_id": b.edge_id,
                    "currents": list(b.currents),
                    "losses_kw": list(b.losses_kw),
                    "i_rated": b.i_rated,
                }
                for b in self.branch_results
            ],
            "load_results": [
                {
                    "asset_id": load.asset_id,
                    "demands": list(load.demands),
                    "supplied": list(load.supplied),
                }
                for load in self.load_results
            ],
            "generator_results": [
                {
                    "asset_id": g.asset_id,
                    "powers": list(g.powers),
                    "cost_per_unit": g.cost_per_unit,
                    "emission_factor": g.emission_factor,
                }
                for g in self.generator_results
            ],
            "renewable_results": [
                {
                    "asset_id": r.asset_id,
                    "available": list(r.available),
                    "dispatched": list(r.dispatched),
                }
                for r in self.renewable_results
            ],
            "interruptions": [
                {
                    "event_id": i.event_id,
                    "start_time": i.start_time,
                    "end_time": i.end_time,
                    "duration_min": i.duration_min,
                    "customers_affected": i.customers_affected,
                    "cause": i.cause,
                }
                for i in self.interruptions
            ],
            "metrics": self.metrics_dict(),
            "elapsed_s": self.elapsed_s,
        }
