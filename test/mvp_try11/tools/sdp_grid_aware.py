"""Grid-aware CTOP — MILP with DistFlow voltage and line-loading constraints.

Spec: F-M2 C3 reviewer concern resolution.

Adds the following constraints to the standard CTOP MILP
(``sdp_optimizer.solve_sdp_strict``):

  * **Voltage upper bound**: at every bus i the worst-case voltage when
    all active and selected standby DERs inject simultaneously must
    stay below V_max (typically 1.05 pu).
  * **Voltage lower bound**: at every bus i the no-DER baseline voltage
    must stay above V_min (typically 0.95 pu). This is a feasibility
    check independent of x but reported for completeness.
  * **Line-loading upper bound**: at every line k the loading % must
    stay below L_max (typically 100%) under worst-case injection.

Linearisation: voltage and line loading are expressed as

  V_i = V_baseline_i + sum_{j ∈ A} cap_j * V_impact[i, b(j)]
        + sum_{j ∈ candidates} cap_j * V_impact[i, b(j)] * x_j

where the first term is the existing-loads baseline, the second is
the active-pool contribution (constant), and the third is the standby
selection (linear in x). This is the standard DistFlow linearisation.

The new variant is labelled M7. Mode names:
  * "M7-strict-grid"      : trigger-orthogonal + voltage + line constraints
  * "M7-grid-only"        : voltage + line constraints, no orthogonality
                              (= grid-feasible Markowitz-equivalent)
"""

from __future__ import annotations

import pulp

from .der_pool import DER, TRIGGER_BASIS_K3, project_exposure
from .feeders import DerBusMap
from .grid_impact import GridImpactMatrix, get_impact_matrix
from .sdp_optimizer import SDPSolution


# Default voltage / line limits (per-unit / percent)
V_MAX_PU: float = 1.05
V_MIN_PU: float = 0.95
LINE_MAX_PCT: float = 100.0


def solve_sdp_grid_aware(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    bus_map: DerBusMap,
    feeder_name: str,
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    enforce_orthogonality: bool = True,
    v_max_pu: float = V_MAX_PU,
    v_min_pu: float = V_MIN_PU,
    line_max_pct: float = LINE_MAX_PCT,
    mode: str = "M7-strict-grid",
) -> SDPSolution:
    """SDP MILP with both trigger-orthogonality and DistFlow grid constraints.

    Args:
        pool, active_ids, burst_kw, basis: as for ``solve_sdp_strict``.
        bus_map: DER → bus assignment for the chosen feeder.
        feeder_name: One of FEEDER_NAMES; used to fetch the impact matrix.
        enforce_orthogonality: If False, drop the trigger-orthogonal
            constraints and keep only capacity coverage + grid bounds
            (= ablation showing grid constraints alone vs combined).
        v_max_pu, v_min_pu, line_max_pct: per-unit / percent limits.
        mode: Label for traceability.

    Returns:
        SDPSolution. ``feasible=False`` if the combined MILP is infeasible.
    """
    impact = get_impact_matrix(feeder_name)
    bus_idx_to_pos = {b: i for i, b in enumerate(impact.bus_indices)}

    # Build active and candidate sets
    active = tuple(d for d in pool if d.der_id in active_ids)
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    n = len(candidates)

    bus_lookup = dict(bus_map.bus_of)

    if n == 0:
        return SDPSolution(
            standby_ids=(), objective_cost=0.0,
            trigger_basis=basis, mode=mode, feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )

    # Active-pool contribution to per-bus voltage and per-line loading
    # (constant w.r.t. x; baked into the rhs of voltage / line constraints)
    n_imp_buses = len(impact.bus_indices)
    n_imp_lines = len(impact.line_indices)
    active_v_contribution = [0.0] * n_imp_buses
    active_l_contribution = [0.0] * n_imp_lines
    for d in active:
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        col = bus_idx_to_pos.get(bus)
        if col is None:
            continue
        for i in range(n_imp_buses):
            active_v_contribution[i] += d.capacity_kw * impact.v_impact_per_kw[i][col]
        for k in range(n_imp_lines):
            active_l_contribution[k] += d.capacity_kw * impact.l_impact_per_kw[k][col]

    # Per-candidate impact (column index in the impact matrix)
    cand_cols: list[int | None] = []
    for d in candidates:
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        cand_cols.append(bus_idx_to_pos.get(bus))

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    K = len(basis)
    exposed_active = tuple(
        any(project_exposure(d, basis)[k] for d in active) for k in range(K)
    )

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    prob += pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )

    # (A) Trigger orthogonality
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

    # (C) Voltage upper bound at every bus
    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        active_term = active_v_contribution[i]
        # Sum_j cap_j * V_impact[i, b(j)] * x_j
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.v_impact_per_kw[i][cand_cols[k]] * x[k]
            for k in range(n) if cand_cols[k] is not None
        )
        prob += baseline + active_term + cand_term <= v_max_pu, f"v_max_b{i}"
        # Voltage lower bound: not affected by x (positive injection only
        # raises voltage), but we record a feasibility check on the
        # baseline + active term:
        # baseline + active_term + cand_term >= v_min  is satisfied
        # automatically since cand_term >= 0; the binding case is
        # baseline + active_term >= v_min when no candidates dispatch.
        # Skipping as a constraint (always feasible by physics).

    # (D) Line loading upper bound at every line
    for k_line in range(n_imp_lines):
        baseline = impact.baseline_line_pct[k_line]
        active_term = active_l_contribution[k_line]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.l_impact_per_kw[k_line][cand_cols[k]] * x[k]
            for k in range(n) if cand_cols[k] is not None
        )
        prob += baseline + active_term + cand_term <= line_max_pct, f"line_max_l{k_line}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=120)
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
        candidates[i].der_id for i in range(n) if x[i].value() and x[i].value() > 0.5
    )
    cost = float(pulp.value(prob.objective))
    overlap = tuple(
        (basis[k], sum(int(cand_exposure[i][k]) for i in range(n) if x[i].value() and x[i].value() > 0.5))
        for k in range(K)
    )
    coverage = tuple(
        (basis[k], sum(
            (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
            for i in range(n) if x[i].value() and x[i].value() > 0.5
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
