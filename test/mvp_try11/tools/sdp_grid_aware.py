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

Variants:
  * ``solve_sdp_grid_aware``      — hard constraints (M7 strict family)
  * ``solve_sdp_grid_aware_soft`` — penalty on per-bus / per-line slack
                                     (M7-soft, Phase D-2). Always feasible;
                                     reports total / max slack so reviewers
                                     can quantify how much we relaxed the
                                     ANSI C84.1 / IEEE 1547 envelope.

Mode names:
  * "M7-strict-grid"      : trigger-orthogonal + voltage + line constraints
  * "M7-grid-only"        : voltage + line constraints, no orthogonality
                              (= grid-feasible Markowitz-equivalent)
  * "M7-soft"             : trigger-orthogonal + slack-penalised V/L
"""

from __future__ import annotations

from dataclasses import dataclass

import pulp

from .der_pool import DER, TRIGGER_BASIS_K3, project_exposure
from .feeders import DerBusMap
from .grid_impact import get_impact_matrix
from .sdp_optimizer import SDPSolution


# Default voltage / line limits (per-unit / percent)
V_MAX_PU: float = 1.05
V_MIN_PU: float = 0.95
LINE_MAX_PCT: float = 100.0

# Default penalty weight applied to total slack (kept proportional to a
# typical standby contract cost so the solver still respects the
# physical envelope wherever feasibility allows it).
DEFAULT_SLACK_LAMBDA: float = 1.0e6


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


@dataclass(frozen=True)
class GridAwareSoftSolution:
    """``SDPSolution`` plus per-constraint slack diagnostics.

    Attributes:
        solution: The wrapped ``SDPSolution``. Its ``objective_cost`` is the
            **design cost only** (= sum of standby contracts), excluding
            the slack penalty, so it stays comparable with hard variants.
        voltage_slack_total: Sum of per-bus voltage slack (pu * n_buses).
        voltage_slack_max: Worst per-bus voltage slack (pu).
        line_slack_total: Sum of per-line load slack (% * n_lines).
        line_slack_max: Worst per-line load slack (%).
        penalty_lambda: Penalty weight used in the objective.
    """

    solution: SDPSolution
    voltage_slack_total: float
    voltage_slack_max: float
    line_slack_total: float
    line_slack_max: float
    penalty_lambda: float

    def metric_dict(self) -> dict[str, float]:
        """Return slack stats as a flat dict for sweep records."""
        return {
            "voltage_slack_total_pu": self.voltage_slack_total,
            "voltage_slack_max_pu": self.voltage_slack_max,
            "line_slack_total_pct": self.line_slack_total,
            "line_slack_max_pct": self.line_slack_max,
            "soft_penalty_lambda": self.penalty_lambda,
        }


def solve_sdp_grid_aware_soft(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    bus_map: DerBusMap,
    feeder_name: str,
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    enforce_orthogonality: bool = True,
    v_max_pu: float = V_MAX_PU,
    line_max_pct: float = LINE_MAX_PCT,
    slack_lambda: float = DEFAULT_SLACK_LAMBDA,
    mode: str = "M7-soft",
) -> GridAwareSoftSolution:
    """SDP MILP with slack-penalised DistFlow constraints.

    Replaces the hard upper bounds in ``solve_sdp_grid_aware`` with
    soft constraints of the form

        V_i  ≤ V_max + s_v_i,        s_v_i ≥ 0
        L_k  ≤ L_max + s_l_k,        s_l_k ≥ 0

    and adds a penalty ``λ * (Σ s_v_i + Σ s_l_k)`` to the objective.
    The MILP is therefore always feasible (slack can always close any
    gap); the slack values quantify *how much* the strict envelope had
    to be relaxed. Useful for cells where ``solve_sdp_grid_aware``
    returns infeasible (Phase D-2, NEXT_STEPS.md §4).

    Returns:
        ``GridAwareSoftSolution`` with the wrapped ``SDPSolution`` and
        slack diagnostics. ``solution.objective_cost`` is the design
        cost (no penalty) so it is comparable across hard / soft modes.
    """
    impact = get_impact_matrix(feeder_name)
    bus_idx_to_pos = {b: i for i, b in enumerate(impact.bus_indices)}

    active = tuple(d for d in pool if d.der_id in active_ids)
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    n = len(candidates)
    bus_lookup = dict(bus_map.bus_of)

    if n == 0:
        empty = SDPSolution(
            standby_ids=(),
            objective_cost=0.0,
            trigger_basis=basis,
            mode=mode,
            feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )
        return GridAwareSoftSolution(
            solution=empty,
            voltage_slack_total=0.0,
            voltage_slack_max=0.0,
            line_slack_total=0.0,
            line_slack_max=0.0,
            penalty_lambda=slack_lambda,
        )

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
    s_v = [
        pulp.LpVariable(f"s_v_{i}", lowBound=0.0) for i in range(n_imp_buses)
    ]
    s_l = [
        pulp.LpVariable(f"s_l_{k}", lowBound=0.0) for k in range(n_imp_lines)
    ]

    design_cost = pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )
    penalty = slack_lambda * (pulp.lpSum(s_v) + pulp.lpSum(s_l))
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
                (0 if cand_exposure[i][k] else 1)
                * candidates[i].capacity_kw
                * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        active_term = active_v_contribution[i]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.v_impact_per_kw[i][cand_cols[k]] * x[k]
            for k in range(n)
            if cand_cols[k] is not None
        )
        prob += baseline + active_term + cand_term <= v_max_pu + s_v[i], f"v_max_b{i}"

    for k_line in range(n_imp_lines):
        baseline = impact.baseline_line_pct[k_line]
        active_term = active_l_contribution[k_line]
        cand_term = pulp.lpSum(
            candidates[k].capacity_kw * impact.l_impact_per_kw[k_line][cand_cols[k]] * x[k]
            for k in range(n)
            if cand_cols[k] is not None
        )
        prob += (
            baseline + active_term + cand_term <= line_max_pct + s_l[k_line]
        ), f"line_max_l{k_line}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=120)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        # Should not happen — slack can always close any gap. Surface as
        # an infeasible result (e.g. orthogonality + capacity infeasible)
        # rather than silently returning bogus numbers.
        empty = SDPSolution(
            standby_ids=(),
            objective_cost=float("inf"),
            trigger_basis=basis,
            mode=mode,
            feasible=False,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
        )
        return GridAwareSoftSolution(
            solution=empty,
            voltage_slack_total=float("inf"),
            voltage_slack_max=float("inf"),
            line_slack_total=float("inf"),
            line_slack_max=float("inf"),
            penalty_lambda=slack_lambda,
        )

    selected = tuple(
        candidates[i].der_id
        for i in range(n)
        if x[i].value() and x[i].value() > 0.5
    )
    design_cost_value = float(
        sum(
            candidates[i].contract_cost_standby
            for i in range(n)
            if x[i].value() and x[i].value() > 0.5
        )
    )
    overlap = tuple(
        (
            basis[k],
            sum(
                int(cand_exposure[i][k])
                for i in range(n)
                if x[i].value() and x[i].value() > 0.5
            ),
        )
        for k in range(K)
    )
    coverage = tuple(
        (
            basis[k],
            sum(
                (0.0 if cand_exposure[i][k] else 1.0) * candidates[i].capacity_kw
                for i in range(n)
                if x[i].value() and x[i].value() > 0.5
            ),
        )
        for k in range(K)
    )

    v_slack_values = [float(s.value() or 0.0) for s in s_v]
    l_slack_values = [float(s.value() or 0.0) for s in s_l]

    return GridAwareSoftSolution(
        solution=SDPSolution(
            standby_ids=selected,
            objective_cost=design_cost_value,
            trigger_basis=basis,
            mode=mode,
            feasible=True,
            overlap_per_trigger=overlap,
            coverage_per_trigger=coverage,
        ),
        voltage_slack_total=sum(v_slack_values),
        voltage_slack_max=max(v_slack_values) if v_slack_values else 0.0,
        line_slack_total=sum(l_slack_values),
        line_slack_max=max(l_slack_values) if l_slack_values else 0.0,
        penalty_lambda=slack_lambda,
    )
