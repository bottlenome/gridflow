"""B2 — Two-stage stochastic programming baseline.

Strategy: generate ``n_scenarios`` random churn scenarios from the trace
distribution; for each scenario compute the active output reduction;
solve a single LP/MILP that minimises *expected* shortfall + standby
cost, where shortfall = max(0, SLA - active_after_churn - standby_after_churn).

Implementation note: We reuse the trace synthesiser's logic to produce
scenarios. Each scenario is a snapshot of (which DERs are inactive) at a
random sampled timestep.
"""

from __future__ import annotations

import random

import pulp

from ..der_pool import DER, project_exposure
from .common import BaselineSolution


def solve_b2_stochastic_program(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    *,
    n_scenarios: int = 200,
    sla_target_kw: float = 5_000.0,
    seed: int = 0,
) -> BaselineSolution:
    """Solve a sample-average approximation of the 2-stage SP.

    Each of ``n_scenarios`` scenarios randomly knocks out a subset of
    DERs based on the per-trigger burst probabilities encoded in
    ``burst_kw`` (the burst on trigger k probabilistically inactivates
    each DER exposed to k). The MILP picks a standby set ``x`` minimising
        cost(x) + λ * mean_s shortfall_s
    with shortfall_s = max(0, SLA - active_active_kw_s - standby_active_kw_s_x).
    """
    rng = random.Random(seed)
    n = len(pool)

    # Generate scenarios: each is a tuple of n booleans (False = knocked out)
    scenarios: list[tuple[bool, ...]] = []
    triggers = ("commute", "weather", "market", "comm_fault")
    # For each scenario, randomly choose ONE trigger to fire (uniform over
    # those with non-zero burst_kw) and apply with magnitude 0.7
    triggers_with_bk = [t for t in triggers if burst_kw.get(t, 0.0) > 0]
    if not triggers_with_bk:
        triggers_with_bk = list(triggers)
    for _ in range(n_scenarios):
        trig = rng.choice(triggers_with_bk)
        axis_idx = triggers.index(trig)
        status = []
        for d in pool:
            if d.trigger_exposure[axis_idx] and rng.random() < 0.7:
                status.append(False)
            else:
                status.append(True)
        scenarios.append(tuple(status))

    # MILP
    prob = pulp.LpProblem("b2_sp", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    # Force active members fixed: x_i = 0 for i in active
    active_indices = {i for i, d in enumerate(pool) if d.der_id in active_ids}
    for i in active_indices:
        prob += x[i] == 0, f"force_off_active_{i}"

    # Per-scenario shortfall variables
    shortfall = [
        pulp.LpVariable(f"sf_{s}", lowBound=0)
        for s in range(n_scenarios)
    ]

    # Objective: cost + penalty * mean shortfall
    cost = pulp.lpSum(pool[i].contract_cost_standby * x[i] for i in range(n))
    penalty = 1e6 / n_scenarios  # large penalty per kW shortfall
    prob += cost + penalty * pulp.lpSum(shortfall)

    # Per-scenario shortfall constraint: shortfall >= SLA - active_avail_s
    # - sum of standby_x_active_in_scenario
    for s, status in enumerate(scenarios):
        active_avail = sum(
            pool[i].capacity_kw for i in active_indices if status[i]
        )
        standby_avail_expr = pulp.lpSum(
            (1 if status[i] else 0) * pool[i].capacity_kw * x[i]
            for i in range(n) if i not in active_indices
        )
        prob += shortfall[s] >= sla_target_kw - active_avail - standby_avail_expr

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=120)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return BaselineSolution(
            standby_ids=(), objective_cost=float("inf"),
            method_label="B2-stochastic_program", feasible=False,
        )
    selected = tuple(
        pool[i].der_id for i in range(n) if x[i].value() and x[i].value() > 0.5
    )
    pure_cost = sum(
        pool[i].contract_cost_standby for i in range(n)
        if x[i].value() and x[i].value() > 0.5
    )
    return BaselineSolution(
        standby_ids=selected,
        objective_cost=pure_cost,
        method_label="B2-stochastic_program",
        feasible=True,
    )
