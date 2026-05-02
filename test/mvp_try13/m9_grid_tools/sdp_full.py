"""M9-grid — Bayes-Robust Trigger-Orthogonal Grid-Aware Portfolio (try13).

Combines try11's M7 (trigger-orth + DistFlow grid) and try12's M9
(trigger-orth + Bayes-posterior expected-loss) into a single MILP.

Constraints (all 5 families):
  (A) Trigger orthogonality (M1):  ∀k ∈ E(A): Σ_{j: tilde_e_jk=1} x_j = 0
  (B) Capacity coverage (M1):      ∀k:        Σ_{j: tilde_e_jk=0} cap_j x_j ≥ B_k
  (C) Bayes-robust (M9):           ∀k ∈ E(A): Σ_j π_jk cap_j x_j ≤ θ_k
  (D) Voltage upper (M7):          ∀i:        V_baseline + active_term + Σ cap V_imp x ≤ V_max
  (E) Line loading upper (M7):     ∀k:        L_baseline + active_term + Σ cap L_imp x ≤ L_max

Provides: combined feeder safety + statistical robustness + cost optimality.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pulp

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
_TRY12 = _HERE.parent.parent / "mvp_try12"
for p in (_TRY11, _TRY12):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.der_pool import DER, TRIGGER_BASIS_K3, project_exposure  # noqa: E402
from tools.feeders import DerBusMap  # noqa: E402
from tools.grid_impact import get_impact_matrix  # noqa: E402
from tools.sdp_grid_aware import LINE_MAX_PCT, V_MAX_PU  # noqa: E402

from m9_tools.sdp_bayes_robust import (  # noqa: E402
    DEFAULT_PRIOR_BY_TYPE_AXIS,
    bayes_posterior,
)


@dataclass(frozen=True)
class M9GridSolution:
    standby_ids: tuple[str, ...]
    objective_cost: float
    expected_loss_per_axis: tuple[tuple[str, float], ...]
    threshold_per_axis: tuple[tuple[str, float], ...]
    epsilon: float
    feasible: bool
    mode: str
    trigger_basis: tuple[str, ...]
    overlap_per_trigger: tuple[tuple[str, int], ...]
    coverage_per_trigger: tuple[tuple[str, float], ...]


def solve_sdp_full(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    bus_map: DerBusMap,
    feeder_name: str,
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    epsilon: float = 0.05,
    prior_by_type_axis: dict[tuple[str, str], float] | None = None,
    expected_loss_threshold_kw: dict[str, float] | None = None,
    expected_loss_threshold_fraction: float = 0.05,
    v_max_pu: float = V_MAX_PU,
    line_max_pct: float = LINE_MAX_PCT,
    enforce_orthogonality: bool = True,
    mode: str = "M9-grid",
    time_limit_s: int = 120,
) -> M9GridSolution:
    """M9-grid: M7 + M9 in a single MILP."""
    impact = get_impact_matrix(feeder_name)
    bus_idx_to_pos = {b: i for i, b in enumerate(impact.bus_indices)}
    bus_lookup = dict(bus_map.bus_of)
    prior = dict(prior_by_type_axis or DEFAULT_PRIOR_BY_TYPE_AXIS)

    active = tuple(d for d in pool if d.der_id in active_ids)
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    n = len(candidates)
    K = len(basis)

    # Active-side contribution (constants)
    n_imp_buses = len(impact.bus_indices)
    n_imp_lines = len(impact.line_indices)
    active_v = [0.0] * n_imp_buses
    active_l = [0.0] * n_imp_lines
    for d in active:
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        col = bus_idx_to_pos.get(bus)
        if col is None:
            continue
        for i in range(n_imp_buses):
            active_v[i] += d.capacity_kw * impact.v_impact_per_kw[i][col]
        for k in range(n_imp_lines):
            active_l[k] += d.capacity_kw * impact.l_impact_per_kw[k][col]

    # Candidate columns + exposures + Bayes π
    cand_cols: list[int | None] = []
    for d in candidates:
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        cand_cols.append(bus_idx_to_pos.get(bus))
    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    exposed_active = tuple(
        any(project_exposure(d, basis)[k] for d in active) for k in range(K)
    )
    pi: list[tuple[float, ...]] = []
    for d in candidates:
        row = []
        for ax in basis:
            p_ja = prior.get((d.der_type, ax), 0.05)
            row.append(bayes_posterior(epsilon, p_ja))
        pi.append(tuple(row))

    if expected_loss_threshold_kw is None:
        theta = {ax: expected_loss_threshold_fraction * float(burst_kw.get(ax, 0.0))
                 for ax in basis}
    else:
        theta = {ax: float(expected_loss_threshold_kw.get(ax, 0.0)) for ax in basis}

    if n == 0:
        return _empty_result(basis, theta, epsilon, mode, feasible=True)

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    prob += pulp.lpSum(candidates[i].contract_cost_standby * x[i] for i in range(n))

    # (A) Orthogonality
    if enforce_orthogonality:
        for k in range(K):
            if exposed_active[k]:
                prob += pulp.lpSum(
                    cand_exposure[i][k] * x[i] for i in range(n)
                ) == 0, f"orth_{basis[k]}"

    # (B) Capacity coverage
    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1) * candidates[i].capacity_kw * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    # (C) Bayes-robust expected-loss
    for k in range(K):
        if not exposed_active[k]:
            continue
        ax = basis[k]
        prob += pulp.lpSum(
            pi[i][k] * candidates[i].capacity_kw * x[i]
            for i in range(n)
            if not cand_exposure[i][k]
        ) <= theta[ax], f"bayes_loss_{ax}"

    # (D) Voltage upper bound at every bus
    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.v_impact_per_kw[i][cand_cols[k]] * x[k]
            for k in range(n) if cand_cols[k] is not None
        )
        prob += baseline + active_v[i] + cand_term <= v_max_pu, f"v_max_b{i}"

    # (E) Line loading upper bound at every line
    for k_line in range(n_imp_lines):
        baseline = impact.baseline_line_pct[k_line]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.l_impact_per_kw[k_line][cand_cols[k]] * x[k]
            for k in range(n) if cand_cols[k] is not None
        )
        prob += baseline + active_l[k_line] + cand_term <= line_max_pct, f"line_max_l{k_line}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return _empty_result(basis, theta, epsilon, mode, feasible=False)

    def _picked(i: int) -> bool:
        v = x[i].value()
        return bool(v is not None and v > 0.5)

    selected = tuple(candidates[i].der_id for i in range(n) if _picked(i))
    cost = float(pulp.value(prob.objective))

    expected_loss = tuple(
        (
            basis[k],
            float(sum(
                pi[i][k] * candidates[i].capacity_kw
                for i in range(n)
                if _picked(i) and not cand_exposure[i][k]
            )),
        )
        for k in range(K) if exposed_active[k]
    )
    threshold_active = tuple(
        (basis[k], theta[basis[k]]) for k in range(K) if exposed_active[k]
    )
    overlap = tuple(
        (basis[k], sum(int(cand_exposure[i][k]) for i in range(n) if _picked(i)))
        for k in range(K)
    )
    coverage = tuple(
        (
            basis[k],
            float(sum(
                (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
                for i in range(n)
                if _picked(i)
            )),
        )
        for k in range(K)
    )

    return M9GridSolution(
        standby_ids=selected,
        objective_cost=cost,
        expected_loss_per_axis=expected_loss,
        threshold_per_axis=threshold_active,
        epsilon=epsilon,
        feasible=True,
        mode=mode,
        trigger_basis=basis,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )


def _empty_result(basis, theta, epsilon, mode, *, feasible: bool) -> M9GridSolution:
    return M9GridSolution(
        standby_ids=(),
        objective_cost=0.0 if feasible else float("inf"),
        expected_loss_per_axis=(),
        threshold_per_axis=tuple((ax, theta[ax]) for ax in basis),
        epsilon=epsilon,
        feasible=feasible,
        mode=mode,
        trigger_basis=basis,
        overlap_per_trigger=tuple((ax, 0) for ax in basis),
        coverage_per_trigger=tuple((ax, 0.0) for ax in basis),
    )
