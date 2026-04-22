"""Post-processing evaluation — re-apply metrics to already-simulated results.

Spec: ``docs/phase1_result.md`` §5.1.1 (Option B).

The research workflow motivating this module: a sweep produces N
simulation results; the researcher then wants to re-compute metrics
with *different* kwargs (e.g. a voltage threshold swept across 11
values) *without* re-running the N simulations. Before this module the
only options were (a) re-run the sweep N times with different built-in
plugins, or (b) write ad-hoc Python to re-open each child JSON. Both
were documented as research-blocking workarounds in
``docs/phase1_result.md`` §5.1.1.

Design principles (CLAUDE.md §0.1):
    * ``EvaluationPlan`` and ``EvaluationResult`` are frozen dataclasses.
    * Metric specs carry the canonical params-tuple kwargs form so the
      plan itself is hashable / reproducible.
    * Simulation and analysis stay as distinct UseCase responsibilities:
      the evaluator never touches a connector.
"""

from __future__ import annotations

import hashlib
import json
import time
from collections.abc import Iterable
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkHarness
from gridflow.adapter.benchmark.metric_registry import (
    MetricRegistry,
    load_metric_plugin,
)
from gridflow.adapter.benchmark.metrics import MetricCalculator
from gridflow.domain.util.params import Params, as_params, params_to_dict
from gridflow.usecase.result import ExperimentResult

# ----------------------------------------------------------------- spec


@dataclass(frozen=True)
class MetricSpec:
    """Declarative description of a single metric invocation.

    Attributes:
        name: Name under which this metric's value is recorded in the
            output. Two specs may resolve to the *same* plugin class
            with different kwargs (e.g. ``hc_090`` / ``hc_095`` both
            resolving to ``HostingCapacityMetric``) — that is exactly
            the use case the evaluator enables.
        plugin: ``module.path:ClassName`` plugin spec, or ``None`` for
            a built-in metric already known to the registry.
        kwargs: Constructor kwargs in canonical sorted params-tuple form.
    """

    name: str
    plugin: str | None = None
    kwargs: Params = ()

    def __post_init__(self) -> None:
        if not self.name:
            raise ValueError("MetricSpec.name must not be empty")

    def to_dict(self) -> dict[str, object]:
        return {
            "name": self.name,
            "plugin": self.plugin,
            "kwargs": params_to_dict(self.kwargs),
        }


@dataclass(frozen=True)
class EvaluationPlan:
    """Frozen, hashable description of a post-processing evaluation.

    Attributes:
        evaluation_id: Human-readable identifier assigned by the caller.
        results: Ordered tuple of ExperimentResult JSON file paths to
            evaluate. (The UseCase accepts rehydrated ExperimentResults
            as well; this field preserves the provenance of file-based
            plans.)
        metrics: Tuple of metric specs to apply to every experiment.
    """

    evaluation_id: str
    results: tuple[Path, ...]
    metrics: tuple[MetricSpec, ...]

    def __post_init__(self) -> None:
        if not self.evaluation_id:
            raise ValueError("EvaluationPlan.evaluation_id must not be empty")
        if not self.metrics:
            raise ValueError(f"EvaluationPlan '{self.evaluation_id}': metrics must be non-empty")
        names = [m.name for m in self.metrics]
        if len(names) != len(set(names)):
            raise ValueError(f"EvaluationPlan '{self.evaluation_id}': duplicate metric names in {names}")

    def plan_hash(self) -> str:
        """Stable content hash for reproducibility audits."""
        parts: list[str] = [self.evaluation_id]
        for path in self.results:
            parts.append(str(path))
        for spec in self.metrics:
            parts.append(spec.name)
            parts.append(spec.plugin or "")
            parts.append(repr(spec.kwargs))
        raw = "|".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


# ----------------------------------------------------------------- result


@dataclass(frozen=True)
class EvaluationResult:
    """Frozen summary of a completed re-evaluation.

    Attributes:
        evaluation_id: Matches the originating ``EvaluationPlan``.
        plan_hash: Content hash of the plan; lets callers detect
            tampering when comparing reruns.
        experiment_ids: Ordered tuple of every evaluated experiment ID.
        per_experiment_metrics: Raw per-experiment metric values,
            positionally aligned with ``experiment_ids`` (same shape as
            :attr:`SweepResult.per_experiment_metrics`).
        created_at: Wall-clock completion time (UTC).
        elapsed_s: Total evaluation wall time.
    """

    evaluation_id: str
    plan_hash: str
    experiment_ids: tuple[str, ...]
    per_experiment_metrics: tuple[tuple[tuple[str, float], ...], ...]
    created_at: datetime
    elapsed_s: float

    def __post_init__(self) -> None:
        if len(self.per_experiment_metrics) != len(self.experiment_ids):
            raise ValueError(
                f"EvaluationResult: per_experiment_metrics length "
                f"({len(self.per_experiment_metrics)}) must match experiment_ids "
                f"length ({len(self.experiment_ids)})"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "evaluation_id": self.evaluation_id,
            "plan_hash": self.plan_hash,
            "experiment_ids": list(self.experiment_ids),
            "per_experiment_metrics": [dict(row) for row in self.per_experiment_metrics],
            "created_at": self.created_at.isoformat(),
            "elapsed_s": self.elapsed_s,
        }


# ----------------------------------------------------------------- usecase


class Evaluator:
    """Re-apply a set of metrics to previously simulated experiment results.

    The Evaluator is deliberately pure: it takes already-computed
    :class:`ExperimentResult` objects (hydrated from JSON by a caller
    adapter) and feeds them through a freshly-built
    :class:`BenchmarkHarness`. No connector, no registry, no IO side
    effects beyond what the caller passes in.
    """

    def __init__(self, *, result_loader: ResultLoader) -> None:
        self._loader = result_loader

    def run(self, plan: EvaluationPlan) -> EvaluationResult:
        start_wall = time.perf_counter()
        metrics = self._build_metrics(plan.metrics)
        harness = BenchmarkHarness(metrics=metrics)

        experiment_ids: list[str] = []
        per_experiment: list[tuple[tuple[str, float], ...]] = []
        for path in plan.results:
            result = self._loader.load(path)
            experiment_ids.append(result.experiment_id)
            summary = harness.evaluate(result)
            per_experiment.append(tuple(sorted(summary.values, key=lambda kv: kv[0])))

        elapsed = time.perf_counter() - start_wall
        return EvaluationResult(
            evaluation_id=plan.evaluation_id,
            plan_hash=plan.plan_hash(),
            experiment_ids=tuple(experiment_ids),
            per_experiment_metrics=tuple(per_experiment),
            created_at=datetime.now(tz=UTC),
            elapsed_s=elapsed,
        )

    @staticmethod
    def _build_metrics(specs: Iterable[MetricSpec]) -> tuple[MetricCalculator, ...]:
        """Turn each MetricSpec into a named MetricCalculator instance.

        A ``MetricRegistry`` is instantiated per-run (not shared)
        because the same plugin class may appear multiple times with
        different kwargs / names — the registry's uniqueness invariant
        would reject the second registration if the harness built-in
        metrics were included. Instead, we build the metric tuple
        directly.
        """
        builtin = MetricRegistry()
        from gridflow.adapter.benchmark.metrics import BUILTIN_METRICS

        for metric in BUILTIN_METRICS:
            builtin.register(metric)

        metrics: list[MetricCalculator] = []
        for spec in specs:
            if spec.plugin is None:
                # Built-in selection by name; the registry enforces that
                # ``spec.name`` resolves to exactly one built-in metric.
                metric = builtin.get(spec.name)
                metrics.append(metric)
                continue
            instance = load_metric_plugin(spec.plugin, kwargs=dict(spec.kwargs))
            # If the spec's name differs from the plugin's default name,
            # wrap so the harness records it under the spec's name.
            if instance.name != spec.name:
                metrics.append(_NamedMetric(inner=instance, name=spec.name))
            else:
                metrics.append(instance)
        return tuple(metrics)


# ----------------------------------------------------------------- loader


class ResultLoader:
    """Pluggable loader for ExperimentResult JSON files.

    Exists so the UseCase does not depend on the CLI's rehydrator;
    callers inject whichever loader matches their storage layer
    (filesystem, S3, database, etc.). The default filesystem loader is
    :class:`FilesystemResultLoader`.
    """

    def load(self, path: Path) -> ExperimentResult:  # pragma: no cover - Protocol
        raise NotImplementedError


class FilesystemResultLoader(ResultLoader):
    """Read an ExperimentResult from a JSON file on disk.

    Uses the CLI's ``_rehydrate_experiment_result`` helper to keep the
    filesystem ↔ domain mapping in one place.
    """

    def load(self, path: Path) -> ExperimentResult:
        # Deferred import to avoid a CLI ↔ UseCase cycle; the CLI's
        # rehydrator is the single source of truth for JSON → domain
        # conversion and is reused here.
        from gridflow.adapter.cli.app import _rehydrate_experiment_result

        data = json.loads(path.read_text(encoding="utf-8"))
        return _rehydrate_experiment_result(data)


# ----------------------------------------------------------------- helpers


class _NamedMetric:
    """Wrap a :class:`MetricCalculator` with a caller-chosen ``name``.

    Needed by :meth:`Evaluator._build_metrics` so the same plugin
    class can appear multiple times in one EvaluationPlan under
    different kwargs / names (e.g. ``hc_090`` / ``hc_095``).
    ``MetricCalculator.name`` is declared as a writable attribute on the
    Protocol, so a plain class (rather than a frozen dataclass) is the
    simplest way to satisfy the contract without upsetting mypy's
    read-only-vs-settable check.
    """

    def __init__(self, *, inner: MetricCalculator, name: str) -> None:
        self.inner = inner
        self.name = name
        self.unit = inner.unit

    def calculate(self, result: ExperimentResult) -> float:
        return self.inner.calculate(result)


def build_evaluation_plan(
    *,
    evaluation_id: str,
    result_paths: Iterable[Path],
    metric_specs: Iterable[MetricSpec],
) -> EvaluationPlan:
    """Convenience builder used by the CLI and the YAML loader."""
    return EvaluationPlan(
        evaluation_id=evaluation_id,
        results=tuple(result_paths),
        metrics=tuple(metric_specs),
    )


def metric_spec_from_dict(raw: dict[str, object]) -> MetricSpec:
    """Parse a MetricSpec from a YAML / JSON dict.

    Expected shape (matches pack.yaml metrics section):

    .. code-block:: yaml

        name: hc_090
        plugin: module:ClassName      # optional (built-in if absent)
        kwargs:                       # optional
          voltage_low: 0.90
    """
    name = raw.get("name")
    if not isinstance(name, str) or not name:
        raise ValueError(f"metric spec: missing/invalid 'name': {raw!r}")
    plugin = raw.get("plugin")
    if plugin is not None and not isinstance(plugin, str):
        raise ValueError(f"metric spec '{name}': 'plugin' must be a string, got {type(plugin).__name__}")
    kwargs_raw = raw.get("kwargs") or {}
    if not isinstance(kwargs_raw, dict):
        raise ValueError(f"metric spec '{name}': 'kwargs' must be a mapping, got {type(kwargs_raw).__name__}")
    return MetricSpec(name=name, plugin=plugin, kwargs=as_params(kwargs_raw))


__all__ = [
    "EvaluationPlan",
    "EvaluationResult",
    "Evaluator",
    "FilesystemResultLoader",
    "MetricSpec",
    "ResultLoader",
    "build_evaluation_plan",
    "metric_spec_from_dict",
]
