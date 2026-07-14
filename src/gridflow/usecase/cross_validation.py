"""EngineCrossValidator — cross-check one pack across multiple solver engines.

Issue #20 / research-integrity guard. gridflow ships both an OpenDSS and a
pandapower connector, but nothing compared them: a trial could solve a network
on a single engine, read a quirk of *that* solver (a numerical artifact, a
local optimum, an outright bug) as a physical result, and never notice — the
try13->try14 "cigre_lv is infeasible" episode was exactly this. The ad-hoc fix
lived in a research ``tools/run_cross_solver.sh`` bash script; this promotes it
to a first-class, tested use case.

Design (CLAUDE.md §0.1):
    * Pure UseCase — no Connector, no Registry, no runner. Inputs are
      already-computed :class:`ExperimentResult` objects, one per engine
      (the CLI runs the same pack through each engine and hands the results
      here). This mirrors :class:`SensitivityAnalyzer`'s post-processing shape
      and keeps the validator trivially testable.
    * Frozen, hashable report so the whole chain stays round-trippable.

Verdict: two engines *agree* when every shared node's voltage matches within a
caller-set tolerance AND both solvers converged on every step. Structural
disagreement (a node present in one engine but not the other, or voltage
vectors of different length) is always a mismatch — silently comparing only
the overlap would hide exactly the divergence we are looking for.
"""

from __future__ import annotations

import math
from collections.abc import Sequence
from dataclasses import dataclass

from gridflow.domain.error import GridflowError
from gridflow.usecase.result import ExperimentResult, StepStatus

#: Sentinel step index for a structural mismatch (missing node / length
#: difference) that is not tied to a single time step.
_STRUCTURAL_STEP = -1


class CrossValidationError(GridflowError):
    """Raised when cross-validation cannot run (too few engines, bad tol)."""

    error_code = "E-30200"


@dataclass(frozen=True)
class NodeMismatch:
    """One node/step where a candidate engine diverged from the reference.

    ``step == -1`` marks a *structural* mismatch (the node is missing on one
    side, or the two voltage vectors have different lengths); ``abs_diff`` is
    then ``inf`` and ``reference_value`` / ``value`` are ``nan``.
    """

    node_id: str
    step: int
    reference_value: float
    value: float
    abs_diff: float

    def to_dict(self) -> dict[str, object]:
        return {
            "node_id": self.node_id,
            "step": self.step,
            "reference_value": self.reference_value,
            "value": self.value,
            "abs_diff": self.abs_diff,
            "structural": self.step == _STRUCTURAL_STEP,
        }


@dataclass(frozen=True)
class EngineComparison:
    """A candidate engine measured against the reference engine."""

    engine: str
    reference_engine: str
    max_abs_diff: float
    mismatches: tuple[NodeMismatch, ...]

    @property
    def agree(self) -> bool:
        return not self.mismatches

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "reference_engine": self.reference_engine,
            "max_abs_diff": self.max_abs_diff,
            "agree": self.agree,
            "mismatches": [m.to_dict() for m in self.mismatches],
        }


@dataclass(frozen=True)
class EngineConvergence:
    """Per-engine convergence summary (non-``SUCCESS`` step ids)."""

    engine: str
    non_converged_steps: tuple[int, ...]

    @property
    def all_converged(self) -> bool:
        return not self.non_converged_steps

    def to_dict(self) -> dict[str, object]:
        return {
            "engine": self.engine,
            "all_converged": self.all_converged,
            "non_converged_steps": list(self.non_converged_steps),
        }


@dataclass(frozen=True)
class CrossValidationReport:
    """Result of comparing one pack solved on multiple engines."""

    pack_id: str
    reference_engine: str
    tol: float
    comparisons: tuple[EngineComparison, ...]
    convergence: tuple[EngineConvergence, ...]

    @property
    def agree(self) -> bool:
        """True iff every candidate matched within tol AND all engines converged."""
        return all(c.agree for c in self.comparisons) and all(cv.all_converged for cv in self.convergence)

    def to_dict(self) -> dict[str, object]:
        return {
            "pack_id": self.pack_id,
            "reference_engine": self.reference_engine,
            "tol": self.tol,
            "agree": self.agree,
            "comparisons": [c.to_dict() for c in self.comparisons],
            "convergence": [cv.to_dict() for cv in self.convergence],
        }


class EngineCrossValidator:
    """Compare a pack's :class:`ExperimentResult` across ≥2 solver engines.

    Stateless — the caller owns the per-engine results and runs them.
    """

    def validate(
        self,
        *,
        pack_id: str,
        results_by_engine: Sequence[tuple[str, ExperimentResult]],
        tol: float,
    ) -> CrossValidationReport:
        """Cross-check ``results_by_engine`` (the first entry is the reference).

        Args:
            pack_id: Provenance label written to the report.
            results_by_engine: ``(engine_name, result)`` pairs. The first is the
                reference every other engine is measured against.
            tol: Maximum absolute per-node voltage difference (pu) still
                considered agreement. Must be ≥ 0.

        Raises:
            CrossValidationError: Fewer than two engines, a negative tol, or
                duplicate engine names.
        """
        if len(results_by_engine) < 2:
            raise CrossValidationError(
                f"cross-validation needs at least 2 engines, got {len(results_by_engine)}",
                context={"pack_id": pack_id},
            )
        if tol < 0 or math.isnan(tol):
            raise CrossValidationError(f"tol must be a non-negative number, got {tol}")
        names = [engine for engine, _ in results_by_engine]
        if len(names) != len(set(names)):
            raise CrossValidationError(f"engine names must be unique, got {names}")

        reference_engine, reference_result = results_by_engine[0]
        reference_nodes = _nodes_by_id(reference_result)

        comparisons: list[EngineComparison] = []
        convergence: list[EngineConvergence] = []
        for engine, result in results_by_engine:
            convergence.append(EngineConvergence(engine=engine, non_converged_steps=_non_converged_steps(result)))
            # The reference is not compared against itself — that is trivially
            # zero and would clutter the report.
            if engine == reference_engine:
                continue
            comparisons.append(self._compare(reference_engine, reference_nodes, engine, result, tol))

        return CrossValidationReport(
            pack_id=pack_id,
            reference_engine=reference_engine,
            tol=tol,
            comparisons=tuple(comparisons),
            convergence=tuple(convergence),
        )

    @staticmethod
    def _compare(
        reference_engine: str,
        reference_nodes: dict[str, tuple[float, ...]],
        engine: str,
        result: ExperimentResult,
        tol: float,
    ) -> EngineComparison:
        candidate_nodes = _nodes_by_id(result)
        mismatches: list[NodeMismatch] = []
        max_abs_diff = 0.0

        for node_id, ref_voltages in reference_nodes.items():
            if node_id not in candidate_nodes:
                mismatches.append(_structural(node_id))
                continue
            cand_voltages = candidate_nodes[node_id]
            if len(cand_voltages) != len(ref_voltages):
                mismatches.append(_structural(node_id))
                continue
            for step, (ref_v, cand_v) in enumerate(zip(ref_voltages, cand_voltages, strict=True)):
                diff = abs(ref_v - cand_v)
                max_abs_diff = max(max_abs_diff, diff)
                if diff > tol:
                    mismatches.append(
                        NodeMismatch(
                            node_id=node_id,
                            step=step,
                            reference_value=ref_v,
                            value=cand_v,
                            abs_diff=diff,
                        )
                    )

        # Nodes the candidate has but the reference does not are also a
        # divergence — the two engines disagree on the network's shape.
        for node_id in candidate_nodes:
            if node_id not in reference_nodes:
                mismatches.append(_structural(node_id))

        return EngineComparison(
            engine=engine,
            reference_engine=reference_engine,
            max_abs_diff=max_abs_diff,
            mismatches=tuple(mismatches),
        )


# ----------------------------------------------------------------- helpers


def _nodes_by_id(result: ExperimentResult) -> dict[str, tuple[float, ...]]:
    """Map ``node_id → voltages`` for a result (last-wins on duplicate ids)."""
    return {nr.node_id: nr.voltages for nr in result.node_results}


def _non_converged_steps(result: ExperimentResult) -> tuple[int, ...]:
    """Step ids whose status is not ``SUCCESS`` (the runner marks a failed
    solve as ``ERROR`` with a 'did not converge' message)."""
    return tuple(step.step_id for step in result.steps if step.status is not StepStatus.SUCCESS)


def _structural(node_id: str) -> NodeMismatch:
    return NodeMismatch(
        node_id=node_id,
        step=_STRUCTURAL_STEP,
        reference_value=math.nan,
        value=math.nan,
        abs_diff=math.inf,
    )


__all__ = [
    "CrossValidationError",
    "CrossValidationReport",
    "EngineComparison",
    "EngineConvergence",
    "EngineCrossValidator",
    "NodeMismatch",
]
