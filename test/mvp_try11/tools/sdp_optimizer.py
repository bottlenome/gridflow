"""Sentinel-DER Portfolio (SDP) optimizer.

Spec: ``test/mvp_try11/ideation_record.md`` §6.5.1 + ``implementation_plan.md`` §4.

Given:
  * a DER pool (each DER has a trigger-exposure vector)
  * an active subset ``A`` (DERs already serving the contract)
  * a set of expected per-trigger burst sizes ``B_k`` (kW)
  * the trigger basis ``T`` of dimension ``K``

SDP selects a standby subset ``S \\subseteq pool \\\\ A`` minimising the total
standby contract cost subject to:

  (a) trigger-orthogonality: for every trigger ``k`` exposed by ``A``, the
      standby ``S`` must have *zero* exposure to ``k``.
  (b) capacity-coverage: for every trigger ``k``, the total capacity of
      standby DERs **not exposed** to ``k`` must cover ``B_k``.
  (c) pool disjointness: ``S \\cap A = \\emptyset``.

Variants (implementation_plan.md §4.2):
  M1 — strict-MILP-K3 (canonical)
  M2a/b/c — K=2 / K=3 / K=4
  M3a/b/c — strict / soft (penalty λ) / tolerant (overlap ≤ ε)
  M4a/b — MILP exact / greedy O(N log N) heuristic
  M5    — MILP design + NN dispatch (NN dispatch lives in baselines/b6_naive_nn)
  M6    — same as M1 but on a label-perturbed pool (perturbation done outside)

This module owns the design-side computation. M5's dispatch logic is
realised by combining M1's design with ``b6_naive_nn``'s detector.

Design (CLAUDE.md §0.1):
  * Inputs/outputs are frozen dataclasses; the optimiser is a pure
    function of (pool, A, B, basis, mode).
  * No global state; the same call returns the same result.
  * PuLP is invoked with ``solver=PULP_CBC_CMD(msg=False)`` to keep
    output clean and reproducible.
"""

from __future__ import annotations

from dataclasses import dataclass

import pulp

from .der_pool import DER, TRIGGER_BASIS_K3, project_exposure


@dataclass(frozen=True)
class SDPSolution:
    """Result of an SDP optimisation."""

    standby_ids: tuple[str, ...]
    objective_cost: float
    trigger_basis: tuple[str, ...]
    mode: str
    feasible: bool
    overlap_per_trigger: tuple[tuple[str, int], ...]  # (trigger, count) for diagnostics
    coverage_per_trigger: tuple[tuple[str, float], ...]  # (trigger, kw_orthogonal_to_k)


def _select_active(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
) -> tuple[tuple[DER, ...], tuple[DER, ...]]:
    """Return (active subset, candidate subset = pool \\\\ active)."""
    active: list[DER] = []
    candidates: list[DER] = []
    for d in pool:
        if d.der_id in active_ids:
            active.append(d)
        else:
            candidates.append(d)
    return tuple(active), tuple(candidates)


def _exposed_active_axes(
    active: tuple[DER, ...],
    basis: tuple[str, ...],
) -> tuple[bool, ...]:
    """For each trigger axis, True iff at least one active DER is exposed."""
    if not active:
        return tuple(False for _ in basis)
    exposure_active = tuple(project_exposure(d, basis) for d in active)
    return tuple(
        any(row[k] for row in exposure_active) for k in range(len(basis))
    )


# ----------------------------------------------------------------- M1 / M3a strict


def solve_sdp_strict(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    mode: str = "M1",
) -> SDPSolution:
    """Solve SDP with strict trigger-orthogonality (M1 / M3a).

    Args:
        pool: Full DER pool.
        active_ids: IDs of DERs already in the active set.
        burst_kw: Expected per-trigger burst sizes; keys must be in
            ``basis``. Triggers not in ``burst_kw`` are treated as B_k=0.
        basis: Trigger basis to use for orthogonality.
        mode: Label for traceability ("M1" or e.g. "M3a-strict").

    Returns:
        SDPSolution. ``feasible=False`` if PuLP/CBC can't solve.
    """
    active, candidates = _select_active(pool, active_ids)
    exposed_active = _exposed_active_axes(active, basis)

    n = len(candidates)
    if n == 0:
        return SDPSolution(
            standby_ids=(),
            objective_cost=0.0,
            trigger_basis=basis,
            mode=mode,
            feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    K = len(basis)

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    # Objective: total standby contract cost
    prob += pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )

    # (a) Strict orthogonality: for k where active is exposed, standby exposure must be 0
    for k in range(K):
        if exposed_active[k]:
            prob += pulp.lpSum(
                cand_exposure[i][k] * x[i] for i in range(n)
            ) == 0, f"orth_{basis[k]}"

    # (b) Capacity coverage: for every k, standby kw orthogonal to k >= B_k
    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1) * candidates[i].capacity_kw * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return SDPSolution(
            standby_ids=(),
            objective_cost=float("inf"),
            trigger_basis=basis,
            mode=mode,
            feasible=False,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    selected = tuple(
        candidates[i].der_id for i in range(n) if x[i].value() > 0.5
    )
    cost = float(pulp.value(prob.objective))
    overlap = tuple(
        (basis[k], sum(int(cand_exposure[i][k]) for i in range(n) if x[i].value() > 0.5))
        for k in range(K)
    )
    coverage = tuple(
        (basis[k], sum(
            (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
            for i in range(n) if x[i].value() > 0.5
        ))
        for k in range(K)
    )
    return SDPSolution(
        standby_ids=selected,
        objective_cost=cost,
        trigger_basis=basis,
        mode=mode,
        feasible=True,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )


# ----------------------------------------------------------------- M3b soft


def solve_sdp_soft(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    overlap_penalty: float = 1_000.0,
    mode: str = "M3b-soft",
) -> SDPSolution:
    """Soft-orthogonality variant: orthogonality is penalised, not enforced.

    Useful when the strict formulation is infeasible (e.g. C3 trace where
    multiple triggers fire simultaneously and a feasible orthogonal
    standby cannot meet capacity coverage).
    """
    active, candidates = _select_active(pool, active_ids)
    exposed_active = _exposed_active_axes(active, basis)

    n = len(candidates)
    if n == 0:
        return SDPSolution(
            standby_ids=(),
            objective_cost=0.0,
            trigger_basis=basis,
            mode=mode,
            feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    K = len(basis)

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    # Objective: cost + penalty * sum of orthogonality violations
    cost_term = pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )
    penalty_term = pulp.lpSum(
        overlap_penalty * cand_exposure[i][k] * x[i]
        for k in range(K) if exposed_active[k]
        for i in range(n)
    )
    prob += cost_term + penalty_term

    # Capacity coverage stays hard: SLA still has to be met
    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1) * candidates[i].capacity_kw * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return SDPSolution(
            standby_ids=(), objective_cost=float("inf"),
            trigger_basis=basis, mode=mode, feasible=False,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    selected = tuple(
        candidates[i].der_id for i in range(n) if x[i].value() > 0.5
    )
    # Recompute pure cost (without penalty) for fair reporting
    pure_cost = sum(
        candidates[i].contract_cost_standby for i in range(n) if x[i].value() > 0.5
    )
    overlap = tuple(
        (basis[k], sum(int(cand_exposure[i][k]) for i in range(n) if x[i].value() > 0.5))
        for k in range(K)
    )
    coverage = tuple(
        (basis[k], sum(
            (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
            for i in range(n) if x[i].value() > 0.5
        ))
        for k in range(K)
    )
    return SDPSolution(
        standby_ids=selected,
        objective_cost=pure_cost,
        trigger_basis=basis,
        mode=mode,
        feasible=True,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )


# ----------------------------------------------------------------- M3c tolerant


def solve_sdp_tolerant(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    overlap_tol: int = 1,
    mode: str = "M3c-tolerant",
) -> SDPSolution:
    """Tolerant variant: standby may have at most ``overlap_tol`` exposed
    DERs per active-exposed trigger axis. Covers C3 case where strict
    orthogonality is too rigid."""
    active, candidates = _select_active(pool, active_ids)
    exposed_active = _exposed_active_axes(active, basis)

    n = len(candidates)
    if n == 0:
        return SDPSolution(
            standby_ids=(), objective_cost=0.0,
            trigger_basis=basis, mode=mode, feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    K = len(basis)

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    prob += pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )

    for k in range(K):
        if exposed_active[k]:
            prob += pulp.lpSum(
                cand_exposure[i][k] * x[i] for i in range(n)
            ) <= overlap_tol, f"orth_tol_{basis[k]}"

    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1) * candidates[i].capacity_kw * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    solver = pulp.PULP_CBC_CMD(msg=False)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return SDPSolution(
            standby_ids=(), objective_cost=float("inf"),
            trigger_basis=basis, mode=mode, feasible=False,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    selected = tuple(
        candidates[i].der_id for i in range(n) if x[i].value() > 0.5
    )
    cost = float(pulp.value(prob.objective))
    overlap = tuple(
        (basis[k], sum(int(cand_exposure[i][k]) for i in range(n) if x[i].value() > 0.5))
        for k in range(K)
    )
    coverage = tuple(
        (basis[k], sum(
            (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
            for i in range(n) if x[i].value() > 0.5
        ))
        for k in range(K)
    )
    return SDPSolution(
        standby_ids=selected,
        objective_cost=cost,
        trigger_basis=basis,
        mode=mode,
        feasible=True,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )


# ----------------------------------------------------------------- M4b greedy


def solve_sdp_greedy(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    mode: str = "M4b-greedy",
) -> SDPSolution:
    """O(N log N) greedy heuristic.

    Strategy:
      1. Filter candidates to only those whose exposure is fully orthogonal
         to active-exposed axes (= strict-feasible candidates).
      2. For each trigger ``k`` requiring coverage, greedily add the
         cheapest-per-kW orthogonal candidate until the coverage target
         is met.
    """
    active, candidates = _select_active(pool, active_ids)
    exposed_active = _exposed_active_axes(active, basis)

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    K = len(basis)

    # Filter: orthogonal to all active-exposed axes
    orth_idx = tuple(
        i for i in range(len(candidates))
        if all((not exposed_active[k]) or (not cand_exposure[i][k])
               for k in range(K))
    )

    selected: list[int] = []
    used = set()
    feasible = True

    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk <= 0:
            continue
        # Within orth_idx, those orthogonal to trigger k specifically
        eligible = [i for i in orth_idx if not cand_exposure[i][k] and i not in used]
        # Cheapest per kW
        eligible.sort(
            key=lambda i: candidates[i].contract_cost_standby / max(1.0, candidates[i].capacity_kw)
        )
        covered = 0.0
        for i in eligible:
            if covered >= bk:
                break
            if i in used:
                continue
            selected.append(i)
            used.add(i)
            covered += candidates[i].capacity_kw
        if covered < bk:
            feasible = False

    selected_ids = tuple(candidates[i].der_id for i in sorted(set(selected)))
    cost = sum(candidates[i].contract_cost_standby for i in set(selected))
    overlap = tuple(
        (basis[k],
         sum(int(cand_exposure[i][k]) for i in set(selected)))
        for k in range(K)
    )
    coverage = tuple(
        (basis[k],
         sum(
             (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
             for i in set(selected)
         ))
        for k in range(K)
    )
    return SDPSolution(
        standby_ids=selected_ids,
        objective_cost=cost if feasible else float("inf"),
        trigger_basis=basis,
        mode=mode,
        feasible=feasible,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )
