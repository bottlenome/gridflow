"""YAML / dict loader for :class:`SweepPlan`.

Spec: ``docs/mvp_scenario_v2.md`` §5.2 + ``docs/phase1_result.md`` §5.1.1
(Option A — axis ``target`` and top-level ``metrics:`` section).

YAML schema (``sweep_plan.yaml``):

.. code-block:: yaml

    sweep:
      id: demo                          # str
      base_pack_id: ieee13@1.0.0        # str
      aggregator: statistics            # registered Aggregator name
      seed: 42                          # optional int

    axes:
      - name: pv_kw
        type: range                     # range | choice | random_uniform | random_choice
        start: 100
        stop: 500
        step: 100
                                        # implicit target: pack
      - name: voltage_low
        type: range
        start: 0.90
        stop: 0.96
        step: 0.01
        target: "metric:hc_metric"      # overrides kwargs of metric 'hc_metric'
      - name: bus
        type: choice
        values: ["671", "675"]
      - name: pv_kw_random
        type: random_uniform
        low: 100
        high: 500
        n_samples: 500
        seed: 42
      - name: bus_random
        type: random_choice
        values: ["671", "675", "634"]
        n_samples: 500
        seed: 42

    # Optional — required when any axis has target 'metric:<name>'.
    metrics:
      - name: voltage_deviation         # built-in (no plugin)
      - name: hc_metric
        plugin: my_pkg.my_mod:HostingCapacityMetric
        kwargs:
          voltage_low: 0.95
          voltage_high: 1.05

The loader translates this to the typed dataclass tree
(:class:`SweepPlan` with concrete :class:`ParamAxis` instances plus the
:class:`gridflow.usecase.evaluation.MetricSpec` tuple used by the
sweep orchestrator for per-child metric re-instantiation) and raises
:class:`SweepPlanLoadError` on any schema violation. The actual sweep
semantics live in :mod:`gridflow.usecase.sweep_plan` and
:mod:`gridflow.usecase.sweep`.
"""

from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import yaml

from gridflow.usecase.evaluation import MetricSpec, metric_spec_from_dict
from gridflow.usecase.sweep_plan import (
    TARGET_PACK,
    ChoiceAxis,
    ParamAxis,
    RandomSampleAxis,
    RangeAxis,
    SweepPlan,
)


class SweepPlanLoadError(ValueError):
    """Raised when sweep plan YAML / dict input is malformed."""


@dataclass(frozen=True)
class LoadedSweepPlan:
    """Bundle of what the YAML loader produces.

    The YAML file can declare *both* a SweepPlan and the MetricSpec
    tuple used for §5.1.1 Option A metric-targeted axes; returning the
    two together lets the CLI wire them in one call without a second
    parse.
    """

    plan: SweepPlan
    metric_specs: tuple[MetricSpec, ...]


def load_sweep_plan_from_yaml(path: Path) -> SweepPlan:
    """Parse ``path`` as a sweep plan YAML and build a :class:`SweepPlan`.

    Thin wrapper around :func:`load_sweep_plan_bundle_from_yaml` that
    discards the metric specs — kept for backward compatibility with
    callers that only care about the plan itself.
    """
    return load_sweep_plan_bundle_from_yaml(path).plan


def load_sweep_plan_bundle_from_yaml(path: Path) -> LoadedSweepPlan:
    """Parse ``path`` into a :class:`LoadedSweepPlan` (plan + metric specs)."""
    if not path.exists():
        raise SweepPlanLoadError(f"sweep plan file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise SweepPlanLoadError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise SweepPlanLoadError(f"{path}: sweep plan top-level must be a mapping, got {type(raw).__name__}")
    return load_sweep_plan_bundle_from_dict(raw)


def load_sweep_plan_from_dict(data: Mapping[str, Any]) -> SweepPlan:
    """Build a :class:`SweepPlan` from a parsed dict (no metric specs)."""
    return load_sweep_plan_bundle_from_dict(data).plan


def load_sweep_plan_bundle_from_dict(data: Mapping[str, Any]) -> LoadedSweepPlan:
    """Build a :class:`LoadedSweepPlan` from a parsed dict."""
    sweep_section = data.get("sweep")
    if not isinstance(sweep_section, Mapping):
        raise SweepPlanLoadError(f"missing or invalid 'sweep' section: got {type(sweep_section).__name__}")

    axes_section = data.get("axes")
    if not isinstance(axes_section, list):
        raise SweepPlanLoadError(f"missing or invalid 'axes' section: got {type(axes_section).__name__}")

    sweep_id = _require_str(sweep_section, "id", "sweep")
    base_pack_id = _require_str(sweep_section, "base_pack_id", "sweep")
    aggregator_name = _require_str(sweep_section, "aggregator", "sweep")
    seed_raw = sweep_section.get("seed")
    seed = int(seed_raw) if seed_raw is not None else None

    axes: list[ParamAxis] = []
    for index, axis_dict in enumerate(axes_section):
        if not isinstance(axis_dict, Mapping):
            raise SweepPlanLoadError(f"axes[{index}] must be a mapping, got {type(axis_dict).__name__}")
        axes.append(_build_axis(axis_dict, index))

    metrics_section = data.get("metrics")
    metric_specs: tuple[MetricSpec, ...] = ()
    if metrics_section is not None:
        if not isinstance(metrics_section, list):
            raise SweepPlanLoadError(f"'metrics' section must be a list, got {type(metrics_section).__name__}")
        specs: list[MetricSpec] = []
        for idx, spec_raw in enumerate(metrics_section):
            if not isinstance(spec_raw, Mapping):
                raise SweepPlanLoadError(f"metrics[{idx}] must be a mapping, got {type(spec_raw).__name__}")
            try:
                specs.append(metric_spec_from_dict(dict(spec_raw)))
            except ValueError as exc:
                raise SweepPlanLoadError(f"metrics[{idx}]: {exc}") from exc
        metric_specs = tuple(specs)

    try:
        plan = SweepPlan(
            sweep_id=sweep_id,
            base_pack_id=base_pack_id,
            axes=tuple(axes),
            aggregator_name=aggregator_name,
            seed=seed,
        )
    except ValueError as exc:
        raise SweepPlanLoadError(f"invalid SweepPlan: {exc}") from exc
    return LoadedSweepPlan(plan=plan, metric_specs=metric_specs)


# ----------------------------------------------------------------- helpers


def _require_str(d: Mapping[str, Any], key: str, section: str) -> str:
    value = d.get(key)
    if value is None:
        raise SweepPlanLoadError(f"{section}.{key}: required field is missing")
    if not isinstance(value, str):
        raise SweepPlanLoadError(f"{section}.{key}: expected str, got {type(value).__name__}")
    return value


def _require_field(d: Mapping[str, Any], key: str, axis_index: int, axis_type: str) -> Any:
    if key not in d:
        raise SweepPlanLoadError(f"axes[{axis_index}] ({axis_type}): missing required field '{key}'")
    return d[key]


def _build_axis(d: Mapping[str, Any], index: int) -> ParamAxis:
    axis_type = d.get("type")
    if not isinstance(axis_type, str):
        raise SweepPlanLoadError(f"axes[{index}]: 'type' must be a string, got {type(axis_type).__name__}")
    name = _require_field(d, "name", index, axis_type)
    if not isinstance(name, str):
        raise SweepPlanLoadError(f"axes[{index}]: 'name' must be a string, got {type(name).__name__}")

    target_raw = d.get("target", TARGET_PACK)
    if not isinstance(target_raw, str):
        raise SweepPlanLoadError(f"axes[{index}]: 'target' must be a string, got {type(target_raw).__name__}")
    target = target_raw

    try:
        if axis_type == "range":
            return RangeAxis(
                name=name,
                start=float(_require_field(d, "start", index, axis_type)),
                stop=float(_require_field(d, "stop", index, axis_type)),
                step=float(_require_field(d, "step", index, axis_type)),
                target=target,
            )
        if axis_type == "choice":
            values = _require_field(d, "values", index, axis_type)
            if not isinstance(values, list):
                raise SweepPlanLoadError(f"axes[{index}] ({axis_type}): 'values' must be a list")
            return ChoiceAxis(name=name, values=tuple(values), target=target)
        if axis_type == "random_uniform":
            return RandomSampleAxis(
                name=name,
                low=float(_require_field(d, "low", index, axis_type)),
                high=float(_require_field(d, "high", index, axis_type)),
                n_samples=int(_require_field(d, "n_samples", index, axis_type)),
                seed=int(_require_field(d, "seed", index, axis_type)),
                target=target,
            )
        if axis_type == "random_choice":
            values = _require_field(d, "values", index, axis_type)
            if not isinstance(values, list):
                raise SweepPlanLoadError(f"axes[{index}] ({axis_type}): 'values' must be a list")
            return RandomSampleAxis(
                name=name,
                values=tuple(values),
                n_samples=int(_require_field(d, "n_samples", index, axis_type)),
                seed=int(_require_field(d, "seed", index, axis_type)),
                target=target,
            )
    except SweepPlanLoadError:
        raise
    except (TypeError, ValueError) as exc:
        raise SweepPlanLoadError(f"axes[{index}] ({axis_type}): {exc}") from exc

    raise SweepPlanLoadError(
        f"axes[{index}]: unknown axis type {axis_type!r}; "
        "expected one of range / choice / random_uniform / random_choice"
    )
