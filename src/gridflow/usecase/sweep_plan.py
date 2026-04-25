"""UseCase-layer sweep domain types.

Spec: ``docs/phase1_result.md`` §7.13.1 / ``docs/mvp_scenario_v2.md`` §5.2 /
``docs/phase1_result.md`` §5.1.1 (Option A — metric parametric evaluation).

A :class:`SweepPlan` describes *what* to sweep:
    * ``base_pack_id``  — the scenario pack every child experiment derives from
    * ``axes``          — a tuple of parameter axes; each child experiment
                          gets one value per axis substituted into either
                          ``pack.metadata.parameters`` or a metric's kwargs,
                          depending on the axis ``target``
    * ``aggregator_name`` — how to summarise the per-experiment metrics
                            after all children finish

The :class:`SweepOrchestrator` (separate module) consumes a ``SweepPlan``
and drives the underlying :class:`~gridflow.usecase.orchestrator.Orchestrator`
for each expanded assignment.

Design principles (CLAUDE.md §0.1):
    * All types are ``@dataclass(frozen=True)`` → hashable, deeply immutable.
    * Parameter assignments are encoded as the canonical frozen params-tuple
      (``tuple[tuple[str, object], ...]``) to match ``ExecutionPlan`` and
      avoid dict contamination at any layer.
    * Axis-level sampling is *deterministic given a seed*; reproducibility is
      a domain invariant.
    * Axes may target either the pack's parameter dict or a *named metric's*
      kwargs — see :class:`ChildAssignment`. The split is structural, not a
      naming convention, so the two concerns do not leak into each other.

Grid expansion semantics:
    * Non-random axes (``RangeAxis``, ``ChoiceAxis``) contribute a cartesian
      product.
    * Random axes (``RandomSampleAxis``) contribute *zipped* draws — i.e. all
      random axes in the same plan must share the same ``n_samples`` and the
      i-th sample from each is paired with the others at position i.
    * The final expansion is cartesian(non-random) x zipped(random).
"""

from __future__ import annotations

import hashlib
import random
from dataclasses import dataclass, field
from datetime import datetime
from typing import Protocol, runtime_checkable

from gridflow.domain.util.params import Params

# ----------------------------------------------------------------- axes


#: Target string used by an axis with no explicit target — pack parameter.
TARGET_PACK: str = "pack"

#: Prefix for metric-targeted axes; full form is ``"metric:<metric_name>"``.
TARGET_METRIC_PREFIX: str = "metric:"


@runtime_checkable
class ParamAxis(Protocol):
    """One dimension of a parameter sweep.

    Contract:
        * ``name`` — the parameter key whose value is substituted by the
          samples from this axis. Interpretation depends on ``target``:

          - ``target == "pack"`` (default) — key in
            ``pack.metadata.parameters``.
          - ``target == "metric:<metric_name>"`` — kwarg key of the
            metric registered under ``<metric_name>``. This lets a
            single sweep vary a metric parameter (e.g. a voltage
            threshold) *without* re-running the simulation — the
            research workflow documented in
            ``docs/phase1_result.md`` §5.1.1 (Option A).
        * ``sample()`` — deterministic, returns a tuple of values (order
          matters). For random axes, the seed must make this reproducible.
        * ``is_random`` — whether this axis participates in the zipped-random
          group inside :meth:`SweepPlan.expand`.
        * ``target`` — see above; defaults to ``"pack"``.

    ``name`` / ``is_random`` / ``target`` are declared as read-only properties
    so that frozen ``@dataclass`` implementations satisfy mypy --strict
    without needing settable attributes.
    """

    @property
    def name(self) -> str: ...

    @property
    def is_random(self) -> bool: ...

    @property
    def target(self) -> str: ...

    def sample(self) -> tuple[object, ...]: ...


@dataclass(frozen=True)
class RangeAxis:
    """Deterministic arithmetic progression ``[start, stop)`` with ``step``."""

    name: str
    start: float
    stop: float
    step: float
    target: str = TARGET_PACK
    is_random: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.step <= 0:
            raise ValueError(f"RangeAxis '{self.name}': step must be positive, got {self.step}")
        if self.start >= self.stop:
            raise ValueError(f"RangeAxis '{self.name}': start must be < stop, got start={self.start}, stop={self.stop}")
        _validate_target(self.target, self.name)

    def sample(self) -> tuple[object, ...]:
        # Accumulate exactly as start + i*step to avoid float drift on
        # large spans. Stop is exclusive.
        values: list[object] = []
        i = 0
        while True:
            current = self.start + i * self.step
            if current >= self.stop:
                break
            values.append(current)
            i += 1
        return tuple(values)


@dataclass(frozen=True)
class ChoiceAxis:
    """Explicit discrete choice (deterministic, no sampling)."""

    name: str
    values: tuple[object, ...]
    target: str = TARGET_PACK
    is_random: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(f"ChoiceAxis '{self.name}': values must be non-empty")
        _validate_target(self.target, self.name)

    def sample(self) -> tuple[object, ...]:
        return self.values


@dataclass(frozen=True)
class RandomSampleAxis:
    """Stochastic sampler over a numeric range or a categorical set.

    Exactly one of the following must be given:

        * ``low`` + ``high`` — continuous uniform on [low, high)
        * ``values``         — discrete uniform (with replacement)

    ``seed`` + ``n_samples`` fully determine the returned tuple.
    """

    name: str
    n_samples: int
    seed: int
    low: float | None = None
    high: float | None = None
    values: tuple[object, ...] | None = None
    target: str = TARGET_PACK
    is_random: bool = field(default=True, init=False)

    def __post_init__(self) -> None:
        if self.n_samples <= 0:
            raise ValueError(f"RandomSampleAxis '{self.name}': n_samples must be positive, got {self.n_samples}")
        has_numeric = self.low is not None and self.high is not None
        has_categorical = self.values is not None
        if has_numeric and has_categorical:
            raise ValueError(f"RandomSampleAxis '{self.name}': pass either (low, high) or values, not both")
        if not has_numeric and not has_categorical:
            raise ValueError(f"RandomSampleAxis '{self.name}': need either (low, high) or values")
        if has_numeric:
            assert self.low is not None and self.high is not None  # for mypy
            if self.low >= self.high:
                raise ValueError(
                    f"RandomSampleAxis '{self.name}': low must be < high, got low={self.low}, high={self.high}"
                )
        if has_categorical:
            assert self.values is not None
            if not self.values:
                raise ValueError(f"RandomSampleAxis '{self.name}': values must be non-empty")
        _validate_target(self.target, self.name)

    def sample(self) -> tuple[object, ...]:
        rng = random.Random(self.seed)
        if self.values is not None:
            return tuple(rng.choice(self.values) for _ in range(self.n_samples))
        assert self.low is not None and self.high is not None
        span = self.high - self.low
        return tuple(self.low + rng.random() * span for _ in range(self.n_samples))


# ----------------------------------------------------------------- targets


def _validate_target(target: str, axis_name: str) -> None:
    """Reject target strings that neither name the pack nor a metric."""
    if target == TARGET_PACK:
        return
    if target.startswith(TARGET_METRIC_PREFIX):
        metric_name = target[len(TARGET_METRIC_PREFIX) :]
        if not metric_name:
            raise ValueError(f"axis '{axis_name}': target 'metric:' must be followed by a metric name")
        return
    raise ValueError(
        f"axis '{axis_name}': target {target!r} is not recognised; expected '{TARGET_PACK}' or 'metric:<metric_name>'"
    )


def parse_metric_target(target: str) -> str | None:
    """Return the metric name if ``target`` is of the form ``metric:<name>``, else ``None``."""
    if target.startswith(TARGET_METRIC_PREFIX):
        return target[len(TARGET_METRIC_PREFIX) :]
    return None


# ----------------------------------------------------------------- assignment


@dataclass(frozen=True)
class ChildAssignment:
    """Per-child axis overlay grouped by target domain.

    Attributes:
        pack_params: Overrides for ``pack.metadata.parameters`` (axes
            with ``target == "pack"``).
        metric_params: Per-metric kwarg overrides, keyed by metric name
            (axes with ``target == "metric:<metric_name>"``). The outer
            tuple is sorted by metric name; each inner Params is the
            sorted kwarg overrides for that metric.

    Keeping the two groups separate structurally (rather than encoding
    them in one flat Params with prefixed keys) is the §0.1
    "spec-first layer boundary" choice: pack parameter overrides and
    metric kwarg overrides have different consumers and different
    lifetimes, so they live in different slots.
    """

    pack_params: Params
    metric_params: tuple[tuple[str, Params], ...] = ()

    def __post_init__(self) -> None:
        names = [name for name, _ in self.metric_params]
        if len(names) != len(set(names)):
            raise ValueError(f"ChildAssignment: duplicate metric names in metric_params: {names}")
        if list(names) != sorted(names):
            raise ValueError(f"ChildAssignment: metric_params must be sorted by metric name, got {names}")

    def to_dict(self) -> dict[str, object]:
        from gridflow.domain.util.params import params_to_dict

        return {
            "pack_params": params_to_dict(self.pack_params),
            "metric_params": {name: params_to_dict(kwargs) for name, kwargs in self.metric_params},
        }


# ----------------------------------------------------------------- plan


@dataclass(frozen=True)
class SweepPlan:
    """Frozen, hashable description of a parameter sweep.

    Attributes:
        sweep_id: Human-readable identifier assigned by the caller.
        base_pack_id: ScenarioPack the sweep derives children from.
        axes: Parameter axes. See module docstring for expansion semantics.
        aggregator_name: Registered aggregator used to reduce per-experiment
            metrics into sweep-level statistics.
        seed: Master seed for the sweep (future use — axes carry their own
            seeds today, but this enables a future "derive axis seeds from
            plan seed" policy without a plan-shape change).
    """

    sweep_id: str
    base_pack_id: str
    axes: tuple[ParamAxis, ...]
    aggregator_name: str
    seed: int | None = None

    def __post_init__(self) -> None:
        if not self.axes:
            raise ValueError(f"SweepPlan '{self.sweep_id}': axes must be non-empty")
        names = [axis.name for axis in self.axes]
        if len(names) != len(set(names)):
            raise ValueError(f"SweepPlan '{self.sweep_id}': duplicate axis names in {names}")
        random_axes = [axis for axis in self.axes if axis.is_random]
        if random_axes:
            counts = {axis.name: getattr(axis, "n_samples", None) for axis in random_axes}
            unique_counts = set(counts.values())
            if len(unique_counts) != 1:
                raise ValueError(f"SweepPlan '{self.sweep_id}': random axes must share n_samples, got {counts}")

    def expand(self) -> tuple[ChildAssignment, ...]:
        """Enumerate per-child assignments, split by target domain.

        Returns one :class:`ChildAssignment` per child experiment; each
        carries (possibly empty) ``pack_params`` and per-metric kwarg
        overrides derived from the axis targets.
        """
        # Sample every axis up-front (deterministic).
        samples: list[tuple[object, ...]] = [axis.sample() for axis in self.axes]
        random_indices = [i for i, axis in enumerate(self.axes) if axis.is_random]
        non_random_indices = [i for i, axis in enumerate(self.axes) if not axis.is_random]

        # Zip-group random axes: each row is an ordered list of (axis_idx, value) pairs.
        random_rows: list[list[tuple[int, object]]] = []
        if random_indices:
            n = len(samples[random_indices[0]])
            for k in range(n):
                row: list[tuple[int, object]] = [(i, samples[i][k]) for i in random_indices]
                random_rows.append(row)
        else:
            random_rows.append([])

        # Cartesian product over non-random axes — elements are lists of
        # (axis_idx, value) pairs. Preserving axis_idx lets us route each
        # value to the right target when we materialise ChildAssignment.
        cartesian: list[list[tuple[int, object]]] = [[]]
        for i in non_random_indices:
            next_cart: list[list[tuple[int, object]]] = []
            for prefix in cartesian:
                for value in samples[i]:
                    next_cart.append([*prefix, (i, value)])
            cartesian = next_cart

        assignments: list[ChildAssignment] = []
        for base_row in cartesian:
            for rand_row in random_rows:
                all_pairs: list[tuple[int, object]] = [*base_row, *rand_row]
                assignments.append(self._materialise_assignment(all_pairs))
        return tuple(assignments)

    def _materialise_assignment(self, pairs: list[tuple[int, object]]) -> ChildAssignment:
        """Split flat (axis_idx, value) pairs into the ChildAssignment structure."""
        pack_kvs: dict[str, object] = {}
        metric_buckets: dict[str, dict[str, object]] = {}
        for axis_idx, value in pairs:
            axis = self.axes[axis_idx]
            metric_name = parse_metric_target(axis.target)
            if metric_name is None:
                pack_kvs[axis.name] = value
            else:
                metric_buckets.setdefault(metric_name, {})[axis.name] = value

        pack_params: Params = tuple(sorted(pack_kvs.items(), key=lambda kv: kv[0]))
        metric_params: tuple[tuple[str, Params], ...] = tuple(
            (metric_name, tuple(sorted(kwargs.items(), key=lambda kv: kv[0])))
            for metric_name, kwargs in sorted(metric_buckets.items(), key=lambda item: item[0])
        )
        return ChildAssignment(pack_params=pack_params, metric_params=metric_params)

    def plan_hash(self) -> str:
        """Stable content hash of the plan (for SweepResult provenance)."""
        parts: list[str] = [self.sweep_id, self.base_pack_id, self.aggregator_name, str(self.seed)]
        for axis in self.axes:
            parts.append(type(axis).__name__)
            parts.append(axis.name)
            parts.append(repr(axis.sample()))
        raw = "|".join(parts).encode("utf-8")
        return hashlib.sha256(raw).hexdigest()[:16]


# ----------------------------------------------------------------- result


@dataclass(frozen=True)
class SweepResult:
    """Frozen, hashable summary of a completed sweep.

    Attributes:
        sweep_id: Matches the originating SweepPlan.
        base_pack_id: Base pack all children derive from.
        plan_hash: Content hash of the SweepPlan; lets callers detect plan
            tampering when comparing reruns.
        experiment_ids: Ordered tuple of every child experiment ID.
        aggregated_metrics: Sweep-level reduced metrics in params-tuple form.
        per_experiment_metrics: Raw per-experiment metric values in
            **column-oriented** form. Each outer entry is a
            ``(metric_name, values)`` pair where ``values`` is a tuple
            of N floats positionally aligned with :attr:`experiment_ids`
            (i.e. ``values[i]`` is the metric value for the experiment
            ``experiment_ids[i]``). The outer tuple is sorted by
            ``metric_name`` for deterministic round-trip. Column form is
            chosen because the documented downstream consumers
            (sensitivity analysis, quantile, bootstrap, histogram —
            ``docs/phase1_result.md`` §5.1.2) all operate "one metric,
            many experiments" which is O(1) lookup + O(N) iterate in
            this layout vs O(N·M) in row-oriented form.
        assignments: Per-child parameter assignment, positionally aligned
            with :attr:`experiment_ids`. Each entry is the
            :class:`ChildAssignment` used to derive the child pack and
            per-child metric kwargs. Lets downstream tools (e.g.
            ``gridflow evaluate``) recover *which* axis values produced
            which experiment without re-running ``SweepPlan.expand``.
        created_at: Wall-clock completion time (UTC).
        elapsed_s: Total sweep wall time.
    """

    sweep_id: str
    base_pack_id: str
    plan_hash: str
    experiment_ids: tuple[str, ...]
    aggregated_metrics: tuple[tuple[str, float], ...]
    per_experiment_metrics: tuple[tuple[str, tuple[float, ...]], ...]
    assignments: tuple[ChildAssignment, ...]
    created_at: datetime
    elapsed_s: float

    def __post_init__(self) -> None:
        n = len(self.experiment_ids)
        # Column-oriented invariant: every metric vector must have length
        # N (positionally aligned with experiment_ids), names must be
        # unique, and the outer sequence must be sorted by metric name.
        names = [name for name, _ in self.per_experiment_metrics]
        if len(names) != len(set(names)):
            raise ValueError(f"SweepResult: duplicate metric names in per_experiment_metrics: {names}")
        if list(names) != sorted(names):
            raise ValueError(f"SweepResult: per_experiment_metrics must be sorted by metric name, got {names}")
        for name, values in self.per_experiment_metrics:
            if len(values) != n:
                raise ValueError(
                    f"SweepResult: per_experiment_metrics['{name}'] has {len(values)} values but experiment_ids has {n}"
                )
        if len(self.assignments) != n:
            raise ValueError(
                f"SweepResult: assignments length ({len(self.assignments)}) must match experiment_ids length ({n})"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "sweep_id": self.sweep_id,
            "base_pack_id": self.base_pack_id,
            "plan_hash": self.plan_hash,
            "experiment_ids": list(self.experiment_ids),
            "aggregated_metrics": dict(self.aggregated_metrics),
            # Column-oriented: ``{metric_name: [v0, v1, ...]}`` —
            # pandas-friendly ``orient="list"`` shape.
            "per_experiment_metrics": {name: list(values) for name, values in self.per_experiment_metrics},
            "assignments": [a.to_dict() for a in self.assignments],
            "created_at": self.created_at.isoformat(),
            "elapsed_s": self.elapsed_s,
        }
