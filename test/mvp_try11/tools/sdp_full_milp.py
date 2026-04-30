"""M8 — joint active+standby MILP with grid awareness.

Phase D-3 (NEXT_STEPS.md §5). Where ``solve_sdp_grid_aware`` (M7) takes
the active pool as a fixed input — populated by ``feeder_active_pool``
which deterministically picks the first ``n_active_ev`` residential EVs
— this variant lifts the active assignment into binary decision
variables alongside the standby. The active placement therefore
becomes grid-aware: M8 can refuse to put load-side DERs at buses where
they would crash V_min, and place injection-capable DERs where they
help baseline voltage.

Decision variables (one per DER):
    y_j ∈ {0, 1}    — DER j is recruited into the active pool
    x_j ∈ {0, 1}    — DER j is recruited into the standby pool
                      (active and standby are mutually exclusive: y_j + x_j ≤ 1)

Auxiliary variables (one per trigger axis k in the basis T):
    z_k ∈ {0, 1}    — at least one active DER is exposed to trigger k

The trigger-orthogonality constraint (no standby DER may share an
exposed trigger with the active pool) is quadratic in (y, x) but
linearised via z_k:

    Σ_j e_jk · y_j  ≤ N · z_k          (if any active is exposed → z_k=1)
    z_k             ≤ Σ_j e_jk · y_j   (z_k≤count of exposed actives;
                                         since z_k is binary, z_k=1 ⇒ ≥1 active)
    Σ_j e_jk · x_j  ≤ M · (1 − z_k)    (if z_k=1 → no standby exposed to k)

Voltage / line constraints use the cached DistFlow impact matrices
(``grid_impact``); both active and standby contribute to V_max and
L_max, but only active is allowed to lift V_min (standby is dispatched
on burst, so V at idle steps must already meet V_min from active alone).

Mode names:
  * "M8-full" — joint active+standby with strict grid envelope
"""

from __future__ import annotations

from dataclasses import dataclass

import pulp

from .der_pool import DER, TRIGGER_BASIS_K3, project_exposure
from .feeders import DerBusMap
from .grid_impact import get_impact_matrix
from .sdp_grid_aware import LINE_MAX_PCT, V_MAX_PU, V_MIN_PU


@dataclass(frozen=True)
class SDPFullSolution:
    """Joint active+standby MILP result.

    Attributes:
        active_ids / standby_ids: Selected DER id tuples.
        objective_cost: Total active+standby contract cost.
        active_cost / standby_cost: Per-pool cost split.
        trigger_basis: Trigger axis labels.
        mode: Variant label.
        feasible: True iff CBC reported Optimal.
        overlap_per_trigger: standby exposure count per trigger axis.
        coverage_per_trigger: standby capacity orthogonal to each trigger.
        active_exposed_axes: tuple[bool, ...] aligned with basis — which
            axes ended up exposed by the chosen active pool.
        worst_v_min_pu: Worst-bus V_min under active-only injection
            (i.e. the value the V_min ≥ v_min_pu constraint had to clear).
    """

    active_ids: tuple[str, ...]
    standby_ids: tuple[str, ...]
    objective_cost: float
    active_cost: float
    standby_cost: float
    trigger_basis: tuple[str, ...]
    mode: str
    feasible: bool
    overlap_per_trigger: tuple[tuple[str, int], ...]
    coverage_per_trigger: tuple[tuple[str, float], ...]
    active_exposed_axes: tuple[bool, ...]
    worst_v_min_pu: float


def solve_sdp_full(
    pool: tuple[DER, ...],
    bus_map: DerBusMap,
    feeder_name: str,
    *,
    burst_kw: dict[str, float],
    sla_target_kw: float,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    active_capacity_factor: float = 0.7,
    active_candidate_filter: tuple[str, ...] | None = ("residential_ev",),
    v_max_pu: float = V_MAX_PU,
    v_min_pu: float = V_MIN_PU,
    line_max_pct: float = LINE_MAX_PCT,
    enforce_orthogonality: bool = True,
    time_limit_s: int = 120,
    mode: str = "M8-full",
) -> SDPFullSolution:
    """Solve the joint active+standby MILP.

    Args:
        pool: Candidate DERs (the MILP picks both active and standby
            subsets out of this pool).
        bus_map: DER → bus assignment (built once per (pool, feeder)).
        feeder_name: One of ``feeders.FEEDER_NAMES``; used to fetch
            cached DistFlow impact matrices.
        burst_kw: Per-trigger burst sizes (kW); standby coverage target.
        sla_target_kw: Total contracted SLA (kW). The active pool must
            cover ``active_capacity_factor * sla_target_kw``.
        basis: Trigger axis basis (typically K3).
        active_capacity_factor: Fraction of the SLA the active pool must
            cover by itself (default 0.7, matching the legacy
            ``feeder_active_pool`` sizing of 70 % SLA).
        active_candidate_filter: If provided, only DERs whose
            ``der_type`` is in this set may have ``y_j = 1``. Defaults
            to residential EVs to keep semantics aligned with M1/M7;
            pass ``None`` to allow any DER as active.
        v_max_pu / v_min_pu / line_max_pct: ANSI / IEEE strict envelope.
        enforce_orthogonality: If False, drop trigger-orthogonality.
        time_limit_s: CBC time limit (seconds).
        mode: Variant label for traceability.

    Returns:
        ``SDPFullSolution``. ``feasible=False`` if CBC reports infeasible.
    """
    impact = get_impact_matrix(feeder_name)
    bus_idx_to_pos = {b: i for i, b in enumerate(impact.bus_indices)}
    bus_lookup = dict(bus_map.bus_of)

    n = len(pool)
    if n == 0:
        return SDPFullSolution(
            active_ids=(),
            standby_ids=(),
            objective_cost=0.0,
            active_cost=0.0,
            standby_cost=0.0,
            trigger_basis=basis,
            mode=mode,
            feasible=True,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
            active_exposed_axes=tuple(False for _ in basis),
            worst_v_min_pu=float(min(impact.baseline_v_pu) if impact.baseline_v_pu else 1.0),
        )

    n_imp_buses = len(impact.bus_indices)
    n_imp_lines = len(impact.line_indices)
    K = len(basis)

    # Per-DER impact column (None if the DER's bus is unmapped)
    der_cols: list[int | None] = []
    for d in pool:
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        der_cols.append(bus_idx_to_pos.get(bus))

    # Per-DER trigger exposure (booleans aligned with basis)
    der_exposure = tuple(project_exposure(d, basis) for d in pool)

    # Active candidacy mask
    if active_candidate_filter is None:
        is_active_candidate = [True] * n
    else:
        allowed = set(active_candidate_filter)
        is_active_candidate = [d.der_type in allowed for d in pool]

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    y = [pulp.LpVariable(f"y_{j}", cat="Binary") for j in range(n)]
    x = [pulp.LpVariable(f"x_{j}", cat="Binary") for j in range(n)]
    z = [pulp.LpVariable(f"z_{k}", cat="Binary") for k in range(K)]

    # Pin disallowed actives to 0 (cleaner than dropping the variable)
    for j in range(n):
        if not is_active_candidate[j]:
            prob += y[j] == 0, f"no_active_{j}"

    # Objective: total contract cost
    prob += pulp.lpSum(
        pool[j].contract_cost_active * y[j]
        + pool[j].contract_cost_standby * x[j]
        for j in range(n)
    )

    # (1) Mutual exclusion
    for j in range(n):
        prob += y[j] + x[j] <= 1, f"excl_{j}"

    # (2) Active SLA capacity
    active_target = active_capacity_factor * sla_target_kw
    if active_target > 0:
        prob += pulp.lpSum(
            pool[j].capacity_kw * y[j] for j in range(n)
        ) >= active_target, "active_sla"

    # (3a) z_k binding: z_k ≤ Σ e_jk · y_j   (z_k=1 ⇒ ≥1 exposed active)
    for k in range(K):
        prob += z[k] <= pulp.lpSum(
            der_exposure[j][k] * y[j] for j in range(n)
        ), f"z_lb_{basis[k]}"

    # (3b) z_k binding: Σ e_jk · y_j ≤ N · z_k  (any exposed → z_k=1)
    for k in range(K):
        prob += pulp.lpSum(
            der_exposure[j][k] * y[j] for j in range(n)
        ) <= n * z[k], f"z_ub_{basis[k]}"

    # (4) Trigger orthogonality via z_k (big-M, M = pool size suffices
    # because the LHS is bounded by Σ e_jk · x_j ≤ n)
    if enforce_orthogonality:
        for k in range(K):
            prob += pulp.lpSum(
                der_exposure[j][k] * x[j] for j in range(n)
            ) <= n * (1 - z[k]), f"orth_{basis[k]}"

    # (5) Standby capacity coverage per trigger
    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if der_exposure[j][k] else 1) * pool[j].capacity_kw * x[j]
                for j in range(n)
            ) >= bk, f"cap_{basis[k]}"

    # (6) Voltage upper bound (active + standby simultaneously)
    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        injection_term = pulp.lpSum(
            pool[j].capacity_kw
            * impact.v_impact_per_kw[i][der_cols[j]]
            * (y[j] + x[j])
            for j in range(n)
            if der_cols[j] is not None
        )
        prob += baseline + injection_term <= v_max_pu, f"v_max_b{i}"

    # (7) Voltage lower bound (active only — standby is intermittent)
    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        active_only_term = pulp.lpSum(
            pool[j].capacity_kw * impact.v_impact_per_kw[i][der_cols[j]] * y[j]
            for j in range(n)
            if der_cols[j] is not None
        )
        prob += baseline + active_only_term >= v_min_pu, f"v_min_b{i}"

    # (8) Line loading upper bound (active + standby simultaneously)
    for k_line in range(n_imp_lines):
        baseline = impact.baseline_line_pct[k_line]
        injection_term = pulp.lpSum(
            pool[j].capacity_kw
            * impact.l_impact_per_kw[k_line][der_cols[j]]
            * (y[j] + x[j])
            for j in range(n)
            if der_cols[j] is not None
        )
        prob += baseline + injection_term <= line_max_pct, f"line_max_l{k_line}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return SDPFullSolution(
            active_ids=(),
            standby_ids=(),
            objective_cost=float("inf"),
            active_cost=float("inf"),
            standby_cost=float("inf"),
            trigger_basis=basis,
            mode=mode,
            feasible=False,
            overlap_per_trigger=tuple((t, 0) for t in basis),
            coverage_per_trigger=tuple((t, 0.0) for t in basis),
            active_exposed_axes=tuple(False for _ in basis),
            worst_v_min_pu=float("nan"),
        )

    def _picked(var: pulp.LpVariable) -> bool:
        v = var.value()
        return bool(v is not None and v > 0.5)

    active_ids = tuple(pool[j].der_id for j in range(n) if _picked(y[j]))
    standby_ids = tuple(pool[j].der_id for j in range(n) if _picked(x[j]))

    active_cost = float(
        sum(pool[j].contract_cost_active for j in range(n) if _picked(y[j]))
    )
    standby_cost = float(
        sum(pool[j].contract_cost_standby for j in range(n) if _picked(x[j]))
    )

    overlap = tuple(
        (
            basis[k],
            sum(int(der_exposure[j][k]) for j in range(n) if _picked(x[j])),
        )
        for k in range(K)
    )
    coverage = tuple(
        (
            basis[k],
            sum(
                (0.0 if der_exposure[j][k] else 1.0) * pool[j].capacity_kw
                for j in range(n)
                if _picked(x[j])
            ),
        )
        for k in range(K)
    )
    active_exposed = tuple(
        any(der_exposure[j][k] for j in range(n) if _picked(y[j])) for k in range(K)
    )

    # Compute worst-bus V_min from the chosen active pool (linearised).
    worst_v_min = float("inf")
    for i in range(n_imp_buses):
        baseline = impact.baseline_v_pu[i]
        active_term = sum(
            pool[j].capacity_kw * impact.v_impact_per_kw[i][der_cols[j]]
            for j in range(n)
            if der_cols[j] is not None and _picked(y[j])
        )
        worst_v_min = min(worst_v_min, baseline + active_term)
    if worst_v_min == float("inf"):
        worst_v_min = float(min(impact.baseline_v_pu) if impact.baseline_v_pu else 1.0)

    return SDPFullSolution(
        active_ids=active_ids,
        standby_ids=standby_ids,
        objective_cost=active_cost + standby_cost,
        active_cost=active_cost,
        standby_cost=standby_cost,
        trigger_basis=basis,
        mode=mode,
        feasible=True,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
        active_exposed_axes=active_exposed,
        worst_v_min_pu=float(worst_v_min),
    )
