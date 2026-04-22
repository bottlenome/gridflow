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

import json
import statistics
import time
from collections.abc import Mapping, Sequence
from dataclasses import dataclass, field, replace
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol, runtime_checkable

from gridflow.adapter.benchmark.harness import BenchmarkHarness
from gridflow.adapter.benchmark.metrics import BUILTIN_METRICS, MetricCalculator
from gridflow.domain.error import OrchestratorError, PackNotFoundError
from gridflow.domain.scenario import PackMetadata, ScenarioPack, ScenarioRegistry
from gridflow.domain.util.params import Params, as_params
from gridflow.usecase.evaluation import MetricSpec, _NamedMetric
from gridflow.usecase.orchestrator import Orchestrator, RunRequest
from gridflow.usecase.result import ExperimentResult
from gridflow.usecase.sweep_plan import ChildAssignment, SweepPlan, SweepResult

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
        metric_specs: tuple[MetricSpec, ...] = (),
        results_dir: Path | None = None,
    ) -> None:
        self._registry = registry
        self._orchestrator = orchestrator
        self._aggregator_registry = aggregator_registry
        self._connector_id = connector_id
        self._harness = harness or BenchmarkHarness()
        # metric_specs is the declarative source of truth for metric
        # instantiation when an axis targets a metric kwarg (§5.1.1
        # Option A). If empty, the orchestrator falls back to the
        # pre-built ``harness`` for every child — identical to Phase 1
        # behaviour.
        self._metric_specs = metric_specs
        # When set, every child ExperimentResult is persisted as
        # ``<results_dir>/<experiment_id>.json``. Required for the
        # user-paper use case where downstream tools (e.g.
        # plot_stochastic_hca, custom analysis scripts) need to inspect
        # individual placements.
        self._results_dir = results_dir

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

        # Validate up-front that every axis-targeted metric has a MetricSpec
        # so we can re-instantiate it per child. Failing fast here beats
        # blowing up on child N.
        self._validate_metric_targets(plan)

        start_wall = time.perf_counter()
        experiment_ids: list[str] = []
        per_experiment_metrics_dicts: list[dict[str, float]] = []
        per_experiment_metrics_tuples: list[tuple[tuple[str, float], ...]] = []

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
            # Build a per-child harness if any axis targets a metric;
            # otherwise reuse the shared harness (cheap common path).
            harness = self._harness_for_assignment(assignment)
            summary = harness.evaluate(result)
            per_experiment_metrics_dicts.append(dict(summary.values))
            # Canonical sorted tuple form for the SweepResult field; the dict
            # form is kept solely for the Aggregator Protocol input.
            per_experiment_metrics_tuples.append(tuple(sorted(summary.values, key=lambda kv: kv[0])))
            self._persist_child_result(result)

        aggregated = aggregator.aggregate(per_experiment_metrics_dicts)
        elapsed = time.perf_counter() - start_wall
        return SweepResult(
            sweep_id=plan.sweep_id,
            base_pack_id=plan.base_pack_id,
            plan_hash=plan.plan_hash(),
            experiment_ids=tuple(experiment_ids),
            aggregated_metrics=aggregated,
            per_experiment_metrics=tuple(per_experiment_metrics_tuples),
            assignments=tuple(assignments),
            created_at=datetime.now(tz=UTC),
            elapsed_s=elapsed,
        )

    # ------------------------------------------------------- per-child harness

    def _validate_metric_targets(self, plan: SweepPlan) -> None:
        """Every metric-targeted axis must name a metric we know how to build."""
        spec_names = {spec.name for spec in self._metric_specs}
        for axis in plan.axes:
            from gridflow.usecase.sweep_plan import parse_metric_target

            metric_name = parse_metric_target(axis.target)
            if metric_name is None:
                continue
            if metric_name not in spec_names:
                raise OrchestratorError(
                    f"SweepPlan '{plan.sweep_id}': axis '{axis.name}' targets metric "
                    f"'{metric_name}' but no MetricSpec was provided for it",
                    context={
                        "sweep_id": plan.sweep_id,
                        "axis": axis.name,
                        "target_metric": metric_name,
                        "known_metrics": tuple(sorted(spec_names)),
                    },
                )

    def _harness_for_assignment(self, assignment: ChildAssignment) -> BenchmarkHarness:
        """Return a harness whose metrics reflect this child's kwarg overrides.

        Fast path: if the assignment has no metric_params *and* the
        sweep was wired without metric_specs, the shared harness is
        returned unchanged. Otherwise a per-child harness is built from
        ``self._metric_specs`` with the per-child kwargs merged in.
        """
        if not assignment.metric_params and not self._metric_specs:
            return self._harness

        overrides = dict(assignment.metric_params)
        metrics: list[MetricCalculator] = []
        for spec in self._metric_specs:
            kwargs = dict(spec.kwargs)
            if spec.name in overrides:
                for k, v in overrides[spec.name]:
                    kwargs[k] = v
            metrics.append(_instantiate_metric(spec, kwargs))
        if not metrics:
            # No explicit specs given but overrides present — this is
            # caught earlier by _validate_metric_targets, but we keep
            # this guard to satisfy type narrowing.
            return self._harness
        return BenchmarkHarness(metrics=tuple(metrics))

    # ------------------------------------------------------- helpers

    def _derive_child_pack(
        self,
        base: ScenarioPack,
        plan: SweepPlan,
        index: int,
        assignment: ChildAssignment,
    ) -> ScenarioPack:
        """Build an ephemeral child pack from ``base`` + ``assignment``.

        The child pack carries the base pack's file layout (network_dir,
        timeseries_dir, config_dir) verbatim; only ``PackMetadata.parameters``
        is rewritten to include the per-child pack_params. Per-metric
        kwarg overrides are *not* written into the pack — they are
        applied to the harness in :meth:`_harness_for_assignment`.
        """
        merged = self._merge_parameters(base.metadata.parameters, assignment.pack_params)
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

    def _persist_child_result(self, result: ExperimentResult) -> None:
        """Save a child ExperimentResult JSON to ``results_dir`` (if set)."""
        if self._results_dir is None:
            return
        self._results_dir.mkdir(parents=True, exist_ok=True)
        path = self._results_dir / f"{result.experiment_id}.json"
        path.write_text(
            json.dumps(result.to_dict(), indent=2, sort_keys=True),
            encoding="utf-8",
        )


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


# ----------------------------------------------------------------- helpers


def _builtin_metric_by_name(name: str) -> MetricCalculator | None:
    """Return a BUILTIN_METRICS instance by its ``name`` attribute, or ``None``."""
    for metric in BUILTIN_METRICS:
        if metric.name == name:
            return metric
    return None


def _instantiate_metric(spec: MetricSpec, kwargs: dict[str, object]) -> MetricCalculator:
    """Build a :class:`MetricCalculator` instance from ``spec`` + live ``kwargs``.

    Shared by :meth:`SweepOrchestrator._harness_for_assignment` and
    :class:`gridflow.usecase.evaluation.Evaluator` so metric instantiation
    semantics stay in one place. If the spec has no plugin path the
    name must resolve to a built-in metric.
    """
    from gridflow.adapter.benchmark.metric_registry import load_metric_plugin

    if spec.plugin is None:
        builtin = _builtin_metric_by_name(spec.name)
        if builtin is None:
            raise OrchestratorError(
                f"MetricSpec '{spec.name}' has no plugin and is not a built-in metric",
                context={"name": spec.name},
            )
        # Built-ins do not take kwargs today; reject silent drop.
        if kwargs:
            raise OrchestratorError(
                f"MetricSpec '{spec.name}' is a built-in metric and does not accept kwargs, "
                f"got {sorted(kwargs.keys())}",
                context={"name": spec.name, "kwargs": sorted(kwargs.keys())},
            )
        return builtin
    instance = load_metric_plugin(spec.plugin, kwargs=kwargs)
    if instance.name != spec.name:
        return _NamedMetric(inner=instance, name=spec.name)
    return instance


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
