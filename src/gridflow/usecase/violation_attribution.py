"""Voltage-violation attribution — separate controller-induced from pre-existing.

Issue #24, closing the try11 "5x reduction" misjudgment. There, a controller's
benefit was overstated because the reported voltage-violation rate *combined*
two things that must not be combined:

    * baseline_only — buses that already breach the band under the existing
      load, which no dispatch controller can fix (not its responsibility);
    * dispatch_induced — buses the controller itself pushed out of band (its
      responsibility).

Reporting the sum as "the controller's result" made a ~100% pre-existing
condition look like a controller effect. This module decomposes a candidate's
violations against a no-control *baseline* into those two attributions plus the
total, so the controller is only ever credited/charged for what it actually
caused.

Design (CLAUDE.md §0.1):
    * Pure UseCase — inputs are two already-computed :class:`ExperimentResult`
      objects (baseline = no-control, candidate = with-control).
    * The envelope ``(v_min, v_max)`` is a **required** argument, never a
      default. Comparing a rate measured under a relaxed band against a strict
      band was the sibling misjudgment; forcing the band to be named at the
      call site — and stamping it into the report — makes that impossible to
      do by accident.
    * Attribution is per aligned sample (same node, same step). A structural
      mismatch between baseline and candidate is a hard error, not a silent
      partial comparison — attributing across different networks would itself
      be a misjudgment.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import GridflowError
from gridflow.usecase.result import ExperimentResult


class ViolationAttributionError(GridflowError):
    """Raised when attribution cannot run (bad envelope, misaligned results)."""

    error_code = "E-30300"


@dataclass(frozen=True)
class ViolationAttribution:
    """Per-cause voltage-violation rates for a candidate vs a no-control baseline.

    ``total_rate == baseline_only_rate + dispatch_induced_rate`` always holds.
    Rates are fractions of the aligned voltage samples.
    """

    v_min: float
    v_max: float
    n_samples: int
    total_rate: float
    baseline_only_rate: float
    dispatch_induced_rate: float

    def to_dict(self) -> dict[str, object]:
        # The envelope is stamped into every serialised report so a rate can
        # never be read without the band it was measured under.
        return {
            "envelope": {"v_min": self.v_min, "v_max": self.v_max},
            "n_samples": self.n_samples,
            "total_rate": self.total_rate,
            "baseline_only_rate": self.baseline_only_rate,
            "dispatch_induced_rate": self.dispatch_induced_rate,
        }


class ViolationAttributor:
    """Decompose candidate voltage violations by cause against a baseline."""

    def attribute(
        self,
        *,
        baseline: ExperimentResult,
        candidate: ExperimentResult,
        v_min: float,
        v_max: float,
    ) -> ViolationAttribution:
        """Attribute ``candidate``'s violations relative to no-control ``baseline``.

        Args:
            baseline: The no-control experiment (existing load only).
            candidate: The with-control experiment being credited/charged.
            v_min, v_max: Voltage envelope (pu). Required — no default band.

        Raises:
            ViolationAttributionError: ``v_min > v_max``; or the two results do
                not align (different node ids, or different voltage-vector
                lengths for a shared node); or there are no samples to compare.
        """
        if v_min > v_max:
            raise ViolationAttributionError(f"envelope v_min ({v_min}) must be <= v_max ({v_max})")

        base_nodes = _voltages_by_node(baseline)
        cand_nodes = _voltages_by_node(candidate)
        if set(base_nodes) != set(cand_nodes):
            raise ViolationAttributionError(
                "baseline and candidate have different node sets; cannot attribute "
                f"violations across mismatched networks (baseline={sorted(base_nodes)}, "
                f"candidate={sorted(cand_nodes)})"
            )

        n_samples = 0
        total = 0
        baseline_only = 0
        dispatch_induced = 0
        for node_id, cand_voltages in cand_nodes.items():
            base_voltages = base_nodes[node_id]
            if len(base_voltages) != len(cand_voltages):
                raise ViolationAttributionError(
                    f"node '{node_id}' has {len(base_voltages)} baseline samples but "
                    f"{len(cand_voltages)} candidate samples; cannot align"
                )
            for base_v, cand_v in zip(base_voltages, cand_voltages, strict=True):
                n_samples += 1
                cand_violates = cand_v < v_min or cand_v > v_max
                if not cand_violates:
                    continue
                base_v_out = base_v < v_min or base_v > v_max
                total += 1
                if base_v_out:
                    # Already out of band under existing load → not the
                    # controller's doing.
                    baseline_only += 1
                else:
                    # Went out of band only under dispatch → the controller's.
                    dispatch_induced += 1

        if n_samples == 0:
            raise ViolationAttributionError("no voltage samples to attribute (both results are empty)")

        return ViolationAttribution(
            v_min=v_min,
            v_max=v_max,
            n_samples=n_samples,
            total_rate=total / n_samples,
            baseline_only_rate=baseline_only / n_samples,
            dispatch_induced_rate=dispatch_induced / n_samples,
        )


# ----------------------------------------------------------------- helpers


def _voltages_by_node(result: ExperimentResult) -> dict[str, tuple[float, ...]]:
    """Concatenate a node's voltages from aggregate + per-step sources.

    Mirrors the sample collection of the voltage metrics so attribution and
    the ``voltage_violation_rate`` metric see the same population.
    """
    by_node: dict[str, list[float]] = {}
    for nr in result.node_results:
        by_node.setdefault(nr.node_id, []).extend(nr.voltages)
    for step in result.steps:
        if step.node_result is not None:
            by_node.setdefault(step.node_result.node_id, []).extend(step.node_result.voltages)
    return {node_id: tuple(voltages) for node_id, voltages in by_node.items()}


__all__ = [
    "ViolationAttribution",
    "ViolationAttributionError",
    "ViolationAttributor",
]
