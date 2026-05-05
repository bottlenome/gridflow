"""M9-grid-soft — slack-penalised version of M9-grid (try14 contribution).

try13's M9-grid imposes the per-axis Bayes-posterior expected-loss
constraint Σ π_jk cap_j x_j ≤ θ_k as a hard MILP constraint, which
turns the optimisation infeasible when the feeder envelope cannot
accommodate any standby that respects all of (orth, capacity, voltage,
line-load, expected-loss). Examples: cigre_lv at α=0.70 strict.

This soft variant relaxes the expected-loss constraint with a slack:

    ∀k ∈ E(A): Σ π_jk cap_j x_j ≤ θ_k + s_k,  s_k ≥ 0

and adds λ · Σ s_k to the objective. Always feasible (slack closes any
gap); the slack values quantify how much the posterior bound was
relaxed. Useful when the feeder is at the edge of its operating
envelope and the designer wants graceful degradation instead of a
hard infeasibility report.

Companion of try13's M9-grid; same five constraint families, only
expected-loss is softened.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pulp

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
_TRY12 = _HERE.parent.parent / "mvp_try12"
_TRY13 = _HERE.parent.parent / "mvp_try13"
for p in (_TRY11, _TRY12, _TRY13):
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
class M9GridSoftSolution:
    standby_ids: tuple[str, ...]
    objective_cost: float  # design cost only (penalty excluded)
    expected_loss_per_axis: tuple[tuple[str, float], ...]
    threshold_per_axis: tuple[tuple[str, float], ...]
    slack_per_axis: tuple[tuple[str, float], ...]
    epsilon: float
    feasible: bool
    mode: str
    trigger_basis: tuple[str, ...]
    overlap_per_trigger: tuple[tuple[str, int], ...]
    coverage_per_trigger: tuple[tuple[str, float], ...]


def solve_sdp_full_soft(
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
    slack_lambda: float = 1.0e6,
    v_max_pu: float = V_MAX_PU,
    line_max_pct: float = LINE_MAX_PCT,
    enforce_orthogonality: bool = True,
    mode: str = "M9-grid-soft",
    time_limit_s: int = 120,
) -> M9GridSoftSolution:
    """M9-grid with slack-penalised expected-loss constraint."""
    impact = get_impact_matrix(feeder_name)
    bus_idx_to_pos = {b: i for i, b in enumerate(impact.bus_indices)}
    bus_lookup = dict(bus_map.bus_of)
    prior = dict(prior_by_type_axis or DEFAULT_PRIOR_BY_TYPE_AXIS)

    active = tuple(d for d in pool if d.der_id in active_ids)
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    n = len(candidates)
    K = len(basis)

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
        return _empty(basis, theta, epsilon, mode, feasible=True)

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    s = {ax: pulp.LpVariable(f"s_{ax}", lowBound=0.0) for ax in basis if exposed_active[basis.index(ax)]}

    design_cost = pulp.lpSum(candidates[i].contract_cost_standby * x[i] for i in range(n))
    penalty = slack_lambda * pulp.lpSum(s.values()) if s else 0.0
    prob += design_cost + penalty

    if enforce_orthogonality:
        for k in range(K):
            if exposed_active[k]:
                prob += pulp.lpSum(
                    cand_exposure[i][k] * x[i] for i in range(n)
                ) == 0, f"orth_{basis[k]}"

    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1) * candidates[i].capacity_kw * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    # SOFT Bayes-robust expected-loss
    for k in range(K):
        if not exposed_active[k]:
            continue
        ax = basis[k]
        prob += pulp.lpSum(
            pi[i][k] * candidates[i].capacity_kw * x[i]
            for i in range(n)
            if not cand_exposure[i][k]
        ) <= theta[ax] + s[ax], f"bayes_loss_{ax}"

    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.v_impact_per_kw[i][cand_cols[k]] * x[k]
            for k in range(n) if cand_cols[k] is not None
        )
        prob += baseline + active_v[i] + cand_term <= v_max_pu, f"v_max_b{i}"

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
        return _empty(basis, theta, epsilon, mode, feasible=False)

    def _picked(i: int) -> bool:
        v = x[i].value()
        return bool(v is not None and v > 0.5)

    selected = tuple(candidates[i].der_id for i in range(n) if _picked(i))
    cost = float(sum(candidates[i].contract_cost_standby for i in range(n) if _picked(i)))

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
    slack_active = tuple(
        (basis[k], float(s[basis[k]].value() or 0.0)) for k in range(K) if exposed_active[k]
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

    return M9GridSoftSolution(
        standby_ids=selected,
        objective_cost=cost,
        expected_loss_per_axis=expected_loss,
        threshold_per_axis=threshold_active,
        slack_per_axis=slack_active,
        epsilon=epsilon,
        feasible=True,
        mode=mode,
        trigger_basis=basis,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )


def _empty(basis, theta, epsilon, mode, *, feasible) -> M9GridSoftSolution:
    return M9GridSoftSolution(
        standby_ids=(),
        objective_cost=0.0 if feasible else float("inf"),
        expected_loss_per_axis=(),
        threshold_per_axis=tuple((ax, theta[ax]) for ax in basis),
        slack_per_axis=(),
        epsilon=epsilon,
        feasible=feasible,
        mode=mode,
        trigger_basis=basis,
        overlap_per_trigger=tuple((ax, 0) for ax in basis),
        coverage_per_trigger=tuple((ax, 0.0) for ax in basis),
    )
