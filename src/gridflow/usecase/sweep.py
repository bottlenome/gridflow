"""UseCase layer ``SweepOrchestrator`` and ``Aggregator`` Protocol.

Spec: ``docs/phase1_result.md`` §7.13.1.

The sweep orchestrator consumes a :class:`SweepPlan`, expands it into
``N`` parameter assignments, runs each one through the normal
:class:`~gridflow.usecase.orchestrator.Orchestrator`, evaluates built-in
metrics via :class:`BenchmarkHarness`, and reduces the resulting
per-experiment values via a named ``Aggregator``.

Design principles (CLAUDE.md §0.1):
    * Sweep execution is a first-class UseCase responsibility — Docker /
      subprocess / HTTP details stay in Infra.
    * Child packs are *ephemeral derivations* of the base pack: the
      sweep rewrites ``PackMetadata.parameters`` and re-registers the
      child under a deterministic child ``pack_id`` so the
      orchestrator's existing ``Orchestrator.run`` flow can be reused
      unchanged.
    * All reduction logic lives behind an :class:`Aggregator` Protocol
      so future users can plug in e.g. confidence-interval or bootstrap
      estimators without touching the orchestrator.
"""

from __future__ import annotations

import statistics
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from gridflow.adapter.benchmark.harness import BenchmarkHarness
from gridflow.domain.error import OrchestratorError, PackNotFoundError
from gridflow.domain.scenario import PackMetadata, ScenarioPack, ScenarioRegistry
from gridflow.domain.util.params import Params, as_params
from gridflow.usecase.orchestrator import Orchestrator, RunRequest
from gridflow.usecase.result import ExperimentResult
from gridflow.usecase.sweep_plan import SweepPlan, SweepResult

# ----------------------------------------------------------------- Aggregator


@runtime_checkable
class Aggregator(Protocol):
    """Reduce per-experiment metric values into sweep-level statistics.

    Implementations are pure: given a list of ``{metric_name: float}``
    dicts (one per child experiment), return a tuple of
    ``(aggregated_key, value)`` pairs. ``aggregated_key`` is free-form
    but by convention encodes both the source metric name and the
    reduction (e.g. ``voltage_deviation_mean``).
    """

    name: str

    def aggregate(self, per_experiment: Sequence[Mapping[str, float]]) -> tuple[tuple[str, float], ...]: ...


class StatisticsAggregator:
    """Standard descriptive statistics for every metric key.

    For each metric ``m`` in the input, emits
    ``{m}_mean / {m}_median / {m}_min / {m}_max / {m}_stdev``.
    """

    name = "statistics"

    def aggregate(self, per_experiment: Sequence[Mapping[str, float]]) -> tuple[tuple[str, float], ...]:
        if not per_experiment:
            raise ValueError("StatisticsAggregator: input is empty")
        keys: list[str] = sorted({k for d in per_experiment for k in d})
        out: list[tuple[str, float]] = []
        for key in keys:
            values = [float(d[key]) for d in per_experiment if key in d]
            if not values:
                continue
            out.append((f"{key}_mean", float(statistics.fmean(values))))
            out.append((f"{key}_median", float(statistics.median(values))))
            out.append((f"{key}_min", float(min(values))))
            out.append((f"{key}_max", float(max(values))))
            out.append(
                (
                    f"{key}_stdev",
                    float(statistics.pstdev(values)) if len(values) > 1 else 0.0,
                )
            )
        return tuple(out)


class ExtremaAggregator:
    """Cheap min/max-only aggregator for fast smoke checks."""

    name = "extrema"

    def aggregate(self, per_experiment: Sequence[Mapping[str, float]]) -> tuple[tuple[str, float], ...]:
        if not per_experiment:
            raise ValueError("ExtremaAggregator: input is empty")
        keys = sorted({k for d in per_experiment for k in d})
        out: list[tuple[str, float]] = []
        for key in keys:
            values = [float(d[key]) for d in per_experiment if key in d]
            if not values:
                continue
            out.append((f"{key}_min", float(min(values))))
            out.append((f"{key}_max", float(max(values))))
        return tuple(out)


@dataclass
class AggregatorRegistry:
    """Name → :class:`Aggregator` lookup used by the sweep orchestrator."""

    _aggregators: dict[str, Aggregator] = field(default_factory=dict)

    def register(self, aggregator: Aggregator) -> None:
        if aggregator.name in self._aggregators:
            raise ValueError(f"aggregator '{aggregator.name}' already registered")
        self._aggregators[aggregator.name] = aggregator

    def get(self, name: str) -> Aggregator:
        if name not in self._aggregators:
            raise KeyError(f"aggregator '{name}' not registered; known: {tuple(sorted(self._aggregators.keys()))}")
        return self._aggregators[name]

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._aggregators.keys()))


def build_default_aggregator_registry() -> AggregatorRegistry:
    """Factory for the built-in aggregator set used by the CLI."""
    reg = AggregatorRegistry()
    reg.register(StatisticsAggregator())
    reg.register(ExtremaAggregator())
    return reg


# ----------------------------------------------------------------- orchestrator


class SweepOrchestrator:
    """Drive a :class:`SweepPlan` end-to-end through the normal Orchestrator.

    Attributes:
        _registry: Scenario registry — looked up for the base pack and
            used to persist ephemeral child packs.
        _orchestrator: The same UseCase Orchestrator the CLI uses for
            single experiments. The sweep calls it once per expanded
            parameter assignment.
        _aggregator_registry: Name → Aggregator lookup.
        _connector_id: Which connector the child experiments run against.
            Kept as a constructor parameter so callers can sweep the same
            plan across multiple connectors (e.g. OpenDSS vs pandapower)
            by building two orchestrators with different connector IDs.
        _harness: Benchmark harness used to compute per-experiment metrics
            before they are handed to the aggregator.
    """

    def __init__(
        self,
        *,
        registry: ScenarioRegistry,
        orchestrator: Orchestrator,
        aggregator_registry: AggregatorRegistry,
        connector_id: str = "opendss",
        harness: BenchmarkHarness | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator
        self._aggregator_registry = aggregator_registry
        self._connector_id = connector_id
        self._harness = harness or BenchmarkHarness()

    def run(self, plan: SweepPlan) -> SweepResult:
        # Fail fast if the aggregator name is bad — no point expanding 500
        # assignments then failing at the end.
        aggregator = self._aggregator_registry.get(plan.aggregator_name)

        try:
            base_pack = self._registry.get(plan.base_pack_id)
        except PackNotFoundError:
            raise

        assignments = plan.expand()
        if not assignments:
            raise OrchestratorError(
                f"SweepPlan '{plan.sweep_id}' expanded to zero assignments",
                context={"sweep_id": plan.sweep_id},
            )

        start_wall = time.perf_counter()
        experiment_ids: list[str] = []
        per_experiment_metrics: list[dict[str, float]] = []

        for idx, assignment in enumerate(assignments):
            child_pack = self._derive_child_pack(base_pack, plan, idx, assignment)
            self._registry.register(child_pack)
            run_request = RunRequest(
                pack_id=child_pack.pack_id,
                connector_id=self._connector_id,
                total_steps=1,
                seed=base_pack.metadata.seed,
            )
            result: ExperimentResult = self._orchestrator.run(run_request)
            experiment_ids.append(result.experiment_id)
            summary = self._harness.evaluate(result)
            per_experiment_metrics.append(dict(summary.values))

        aggregated = aggregator.aggregate(per_experiment_metrics)
        elapsed = time.perf_counter() - start_wall
        return SweepResult(
            sweep_id=plan.sweep_id,
            base_pack_id=plan.base_pack_id,
            plan_hash=plan.plan_hash(),
            experiment_ids=tuple(experiment_ids),
            aggregated_metrics=aggregated,
            created_at=datetime.now(tz=UTC),
            elapsed_s=elapsed,
        )

    # ------------------------------------------------------- helpers

    def _derive_child_pack(
        self,
        base: ScenarioPack,
        plan: SweepPlan,
        index: int,
        assignment: Params,
    ) -> ScenarioPack:
        """Build an ephemeral child pack from ``base`` + ``assignment``.

        The child pack carries the base pack's file layout (network_dir,
        timeseries_dir, config_dir) verbatim; only ``PackMetadata.parameters``
        is rewritten to include the assigned overrides.
        """
        merged = self._merge_parameters(base.metadata.parameters, assignment)
        child_pack_id = f"{base.name}-sweep{plan.sweep_id[:16]}-{index:05d}@{base.version}"
        child_name = f"{base.name}-sweep{plan.sweep_id[:16]}-{index:05d}"
        new_metadata = PackMetadata(
            name=child_name,
            version=base.metadata.version,
            description=f"Sweep child {index} of {plan.sweep_id}",
            author=base.metadata.author,
            created_at=base.metadata.created_at,
            connector=base.metadata.connector,
            seed=base.metadata.seed,
            parameters=merged,
        )
        return replace(
            base,
            pack_id=child_pack_id,
            name=child_name,
            metadata=new_metadata,
        )

    @staticmethod
    def _merge_parameters(base: Params, overrides: Params) -> Params:
        merged: dict[str, object] = dict(base)
        for k, v in overrides:
            merged[k] = v
        return as_params(merged)


# ----------------------------------------------------------------- convenience


def build_default_sweep_orchestrator(
    *,
    registry: ScenarioRegistry,
    orchestrator: Orchestrator,
    connector_id: str = "opendss",
) -> SweepOrchestrator:
    """CLI-friendly factory wiring the default aggregator registry."""
    return SweepOrchestrator(
        registry=registry,
        orchestrator=orchestrator,
        aggregator_registry=build_default_aggregator_registry(),
        connector_id=connector_id,
    )


# Public re-exports
__all__ = [
    "Aggregator",
    "AggregatorRegistry",
    "ExtremaAggregator",
    "StatisticsAggregator",
    "SweepOrchestrator",
    "build_default_aggregator_registry",
    "build_default_sweep_orchestrator",
]
