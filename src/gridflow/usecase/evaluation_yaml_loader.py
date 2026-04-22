"""YAML loader for :class:`EvaluationPlan`.

Spec: ``docs/phase1_result.md`` §5.1.1 (Option B).

YAML schema (``evaluation.yaml``):

.. code-block:: yaml

    evaluation:
      id: hc_sweep_eval         # str
      results:                  # list of result paths (absolute or
        - results/exp-001.json  # relative to the YAML file's directory)
        - results/exp-002.json
      # OR
      results_dir: results/     # all *.json in the directory are evaluated
      # OR
      sweep_result: results/sweep.json   # load experiment IDs from a
                                          # SweepResult JSON

    metrics:
      - name: voltage_deviation         # built-in
      - name: hc_090                    # custom instance
        plugin: my_pkg.my_mod:HostingCapacityMetric
        kwargs:
          voltage_low: 0.90
      - name: hc_095
        plugin: my_pkg.my_mod:HostingCapacityMetric
        kwargs:
          voltage_low: 0.95

At most one of ``results`` / ``results_dir`` / ``sweep_result`` may be
provided; an EvaluationPlan with zero result paths is rejected.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from gridflow.usecase.evaluation import (
    EvaluationPlan,
    MetricSpec,
    build_evaluation_plan,
    metric_spec_from_dict,
)


class EvaluationPlanLoadError(ValueError):
    """Raised when evaluation plan YAML / dict input is malformed."""


def load_evaluation_plan_from_yaml(path: Path) -> EvaluationPlan:
    """Parse ``path`` as an evaluation plan YAML and build an EvaluationPlan."""
    if not path.exists():
        raise EvaluationPlanLoadError(f"evaluation plan file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise EvaluationPlanLoadError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise EvaluationPlanLoadError(f"{path}: evaluation plan top-level must be a mapping, got {type(raw).__name__}")
    return load_evaluation_plan_from_dict(raw, base_dir=path.parent)


def load_evaluation_plan_from_dict(
    data: Mapping[str, Any],
    *,
    base_dir: Path | None = None,
) -> EvaluationPlan:
    """Build an :class:`EvaluationPlan` from a parsed dict.

    Args:
        data: Parsed YAML / JSON mapping.
        base_dir: Directory to resolve relative result paths against
            (typically the YAML file's directory). Defaults to
            ``Path.cwd()``.
    """
    eval_section = data.get("evaluation")
    if not isinstance(eval_section, Mapping):
        raise EvaluationPlanLoadError(f"missing or invalid 'evaluation' section: got {type(eval_section).__name__}")

    metrics_section = data.get("metrics")
    if not isinstance(metrics_section, list):
        raise EvaluationPlanLoadError(f"missing or invalid 'metrics' section: got {type(metrics_section).__name__}")

    evaluation_id = eval_section.get("id")
    if not isinstance(evaluation_id, str) or not evaluation_id:
        raise EvaluationPlanLoadError("evaluation.id: required non-empty string field is missing")

    result_paths = _resolve_result_paths(eval_section, base_dir=base_dir or Path.cwd())
    if not result_paths:
        raise EvaluationPlanLoadError(f"evaluation '{evaluation_id}': zero result paths resolved")

    metric_specs: list[MetricSpec] = []
    for idx, spec_raw in enumerate(metrics_section):
        if not isinstance(spec_raw, Mapping):
            raise EvaluationPlanLoadError(f"metrics[{idx}] must be a mapping, got {type(spec_raw).__name__}")
        try:
            metric_specs.append(metric_spec_from_dict(dict(spec_raw)))
        except ValueError as exc:
            raise EvaluationPlanLoadError(f"metrics[{idx}]: {exc}") from exc

    try:
        return build_evaluation_plan(
            evaluation_id=evaluation_id,
            result_paths=result_paths,
            metric_specs=metric_specs,
        )
    except ValueError as exc:
        raise EvaluationPlanLoadError(f"invalid EvaluationPlan: {exc}") from exc


# ----------------------------------------------------------------- helpers


def _resolve_result_paths(
    eval_section: Mapping[str, Any],
    *,
    base_dir: Path,
) -> tuple[Path, ...]:
    """Apply the exclusive-or rule on the three source fields."""
    sources = [k for k in ("results", "results_dir", "sweep_result") if k in eval_section]
    if len(sources) != 1:
        raise EvaluationPlanLoadError(
            f"evaluation: exactly one of 'results' / 'results_dir' / 'sweep_result' is required, got {sources}"
        )
    source = sources[0]
    if source == "results":
        raw = eval_section["results"]
        if not isinstance(raw, list):
            raise EvaluationPlanLoadError(f"evaluation.results must be a list, got {type(raw).__name__}")
        return tuple(_resolve_path(base_dir, str(p)) for p in raw)
    if source == "results_dir":
        raw_dir = eval_section["results_dir"]
        if not isinstance(raw_dir, str):
            raise EvaluationPlanLoadError(f"evaluation.results_dir must be a string, got {type(raw_dir).__name__}")
        dir_path = _resolve_path(base_dir, raw_dir)
        if not dir_path.is_dir():
            raise EvaluationPlanLoadError(f"evaluation.results_dir: not a directory: {dir_path}")
        return tuple(sorted(dir_path.glob("*.json")))
    # source == "sweep_result"
    raw_sweep = eval_section["sweep_result"]
    if not isinstance(raw_sweep, str):
        raise EvaluationPlanLoadError(f"evaluation.sweep_result must be a string, got {type(raw_sweep).__name__}")
    sweep_path = _resolve_path(base_dir, raw_sweep)
    return _load_paths_from_sweep_result(sweep_path, base_dir=base_dir)


def _resolve_path(base_dir: Path, raw: str) -> Path:
    """Resolve ``raw`` relative to ``base_dir`` (unless ``raw`` is absolute)."""
    p = Path(raw)
    if p.is_absolute():
        return p
    return (base_dir / p).resolve()


def _load_paths_from_sweep_result(sweep_path: Path, *, base_dir: Path) -> tuple[Path, ...]:
    """Read experiment IDs from a SweepResult JSON and map them to result JSON paths.

    The convention matches :func:`SweepOrchestrator._persist_child_result`
    (``<results_dir>/<experiment_id>.json``). We search for each
    experiment ID under the sweep file's directory first, then under
    ``base_dir``.
    """
    if not sweep_path.exists():
        raise EvaluationPlanLoadError(f"evaluation.sweep_result: file not found: {sweep_path}")
    try:
        payload = json.loads(sweep_path.read_text(encoding="utf-8"))
    except json.JSONDecodeError as exc:
        raise EvaluationPlanLoadError(f"evaluation.sweep_result: malformed JSON in {sweep_path}: {exc}") from exc
    if not isinstance(payload, dict):
        raise EvaluationPlanLoadError(
            f"evaluation.sweep_result: top-level must be an object, got {type(payload).__name__}"
        )
    experiment_ids = payload.get("experiment_ids")
    if not isinstance(experiment_ids, list):
        raise EvaluationPlanLoadError(
            f"evaluation.sweep_result: 'experiment_ids' must be a list, got {type(experiment_ids).__name__}"
        )
    candidates = [sweep_path.parent, base_dir]
    paths: list[Path] = []
    for exp_id in experiment_ids:
        found: Path | None = None
        for candidate_dir in candidates:
            maybe = candidate_dir / f"{exp_id}.json"
            if maybe.exists():
                found = maybe
                break
        if found is None:
            raise EvaluationPlanLoadError(
                f"evaluation.sweep_result: result for experiment_id '{exp_id}' not found "
                f"under {[str(d) for d in candidates]}"
            )
        paths.append(found)
    return tuple(paths)


__all__ = [
    "EvaluationPlanLoadError",
    "load_evaluation_plan_from_dict",
    "load_evaluation_plan_from_yaml",
]
