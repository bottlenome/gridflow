"""UseCase-layer sweep domain types.

Spec: ``docs/phase1_result.md`` §7.13.1 / ``docs/mvp_scenario_v2.md`` §5.2.

A :class:`SweepPlan` describes *what* to sweep:
    * ``base_pack_id``  — the scenario pack every child experiment derives from
    * ``axes``          — a tuple of parameter axes; each child experiment
                          gets one value per axis substituted into
                          ``pack.parameters``
    * ``aggregator_name`` — how to summarise the per-experiment metrics
                            after all children finish

The :class:`SweepOrchestrator` (separate module) consumes a ``SweepPlan``
and drives the underlying :class:`~gridflow.usecase.orchestrator.Orchestrator`
for each expanded assignment.

Design principles (CLAUDE.md §0.1):
    * All types are ``@dataclass(frozen=True)`` → hashable, deeply immutable
    * Parameter assignments are encoded as the canonical frozen params-tuple
      (``tuple[tuple[str, object], ...]``) to match ``ExecutionPlan`` and
      avoid dict contamination at any layer.
    * Axis-level sampling is *deterministic given a seed*; reproducibility is
      a domain invariant.

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


@runtime_checkable
class ParamAxis(Protocol):
    """One dimension of a parameter sweep.

    Contract:
        * ``name`` — the ``pack.parameters`` key whose value is substituted
          by the samples from this axis.
        * ``sample()`` — deterministic, returns a tuple of values (order
          matters). For random axes, the seed must make this reproducible.
        * ``is_random`` — whether this axis participates in the zipped-random
          group inside :meth:`SweepPlan.expand`.

    ``name`` and ``is_random`` are declared as read-only properties so
    that frozen ``@dataclass`` implementations satisfy mypy --strict
    without needing settable attributes.
    """

    @property
    def name(self) -> str: ...

    @property
    def is_random(self) -> bool: ...

    def sample(self) -> tuple[object, ...]: ...


@dataclass(frozen=True)
class RangeAxis:
    """Deterministic arithmetic progression ``[start, stop)`` with ``step``."""

    name: str
    start: float
    stop: float
    step: float
    is_random: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if self.step <= 0:
            raise ValueError(f"RangeAxis '{self.name}': step must be positive, got {self.step}")
        if self.start >= self.stop:
            raise ValueError(f"RangeAxis '{self.name}': start must be < stop, got start={self.start}, stop={self.stop}")

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
    is_random: bool = field(default=False, init=False)

    def __post_init__(self) -> None:
        if not self.values:
            raise ValueError(f"ChoiceAxis '{self.name}': values must be non-empty")

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

    def sample(self) -> tuple[object, ...]:
        rng = random.Random(self.seed)
        if self.values is not None:
            return tuple(rng.choice(self.values) for _ in range(self.n_samples))
        assert self.low is not None and self.high is not None
        span = self.high - self.low
        return tuple(self.low + rng.random() * span for _ in range(self.n_samples))


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

    def expand(self) -> tuple[Params, ...]:
        """Enumerate parameter assignments for each child experiment.

        Returns a tuple of Params tuples (sorted-pair form) — each inner
        tuple is one child's full parameter overlay.
        """
        # Sample every axis up-front (deterministic).
        samples: list[tuple[object, ...]] = [axis.sample() for axis in self.axes]
        random_indices = [i for i, axis in enumerate(self.axes) if axis.is_random]
        non_random_indices = [i for i, axis in enumerate(self.axes) if not axis.is_random]

        # Zip-group random axes into a single virtual axis with n_samples rows.
        random_rows: list[dict[str, object]] = []
        if random_indices:
            n = len(samples[random_indices[0]])
            for k in range(n):
                row: dict[str, object] = {}
                for i in random_indices:
                    row[self.axes[i].name] = samples[i][k]
                random_rows.append(row)
        else:
            random_rows.append({})

        # Cartesian product over non-random axes, then multiply with random rows.
        # We build it iteratively to keep things O(N) per column.
        cartesian: list[dict[str, object]] = [{}]
        for i in non_random_indices:
            next_cart: list[dict[str, object]] = []
            for prefix in cartesian:
                for value in samples[i]:
                    combined = dict(prefix)
                    combined[self.axes[i].name] = value
                    next_cart.append(combined)
            cartesian = next_cart

        assignments: list[Params] = []
        for base in cartesian:
            for rand_row in random_rows:
                merged: dict[str, object] = {**base, **rand_row}
                # Sort to match the canonical Params convention.
                assignments.append(tuple(sorted(merged.items(), key=lambda kv: kv[0])))
        return tuple(assignments)

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
        created_at: Wall-clock completion time (UTC).
        elapsed_s: Total sweep wall time.
    """

    sweep_id: str
    base_pack_id: str
    plan_hash: str
    experiment_ids: tuple[str, ...]
    aggregated_metrics: tuple[tuple[str, float], ...]
    created_at: datetime
    elapsed_s: float

    def to_dict(self) -> dict[str, object]:
        return {
            "sweep_id": self.sweep_id,
            "base_pack_id": self.base_pack_id,
            "plan_hash": self.plan_hash,
            "experiment_ids": list(self.experiment_ids),
            "aggregated_metrics": dict(self.aggregated_metrics),
            "created_at": self.created_at.isoformat(),
            "elapsed_s": self.elapsed_s,
        }
