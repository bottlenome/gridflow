"""B3 — Wasserstein-ball distributionally-robust optimization (DRO).

Wasserstein DRO replaces the empirical distribution P̂ by a ball
:math:`B_τ(P̂)` of radius τ in the Wasserstein-1 metric and solves

    min_x  sup_{Q ∈ B_τ(P̂)}  E_Q[ shortfall(x, ξ) ] + cost(x).

For piecewise-linear losses on a finite empirical sample, this dualises
to (Esfahani 2018, Theorem 4.2) a tractable LP/MILP. We use a simplified
form: ``shortfall_s + τ * λ`` with a Lipschitz penalty λ on the
shortfall mapping. This is the canonical "DRO of the SP" and represents
the system B in §4.1.

Implementation: identical to B2's MILP with an additional ``τ * λ`` term
in the objective (representing the worst-case adversarial perturbation
within the Wasserstein ball).
"""

from __future__ import annotations

import random

import pulp

from ..der_pool import DER
from .common import BaselineSolution


def solve_b3_wasserstein_dro(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    *,
    n_scenarios: int = 200,
    sla_target_kw: float = 5_000.0,
    wasserstein_radius: float = 0.1,
    lipschitz_const: float = 1.0,
    seed: int = 0,
) -> BaselineSolution:
    """SP with a Wasserstein-radius worst-case penalty on shortfall."""
    rng = random.Random(seed)
    n = len(pool)
    triggers = ("commute", "weather", "market", "comm_fault")
    triggers_with_bk = [t for t in triggers if burst_kw.get(t, 0.0) > 0] or list(triggers)
    scenarios: list[tuple[bool, ...]] = []
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

    prob = pulp.LpProblem("b3_dro", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]
    active_indices = {i for i, d in enumerate(pool) if d.der_id in active_ids}
    for i in active_indices:
        prob += x[i] == 0, f"force_off_active_{i}"

    shortfall = [pulp.LpVariable(f"sf_{s}", lowBound=0) for s in range(n_scenarios)]
    # DRO worst-case shift: an additional uniform shift λ_dro ≥ 0 added
    # to every shortfall, paid for at rate ``wasserstein_radius`` (the
    # ball radius drives the cost of worst-case perturbation).
    lambda_dro = pulp.LpVariable("lambda_dro", lowBound=0)

    cost = pulp.lpSum(pool[i].contract_cost_standby * x[i] for i in range(n))
    penalty = 1e6 / n_scenarios
    prob += (
        cost
        + penalty * pulp.lpSum(shortfall)
        + wasserstein_radius * lipschitz_const * lambda_dro * 1e6
    )

    for s, status in enumerate(scenarios):
        active_avail = sum(
            pool[i].capacity_kw for i in active_indices if status[i]
        )
        standby_avail_expr = pulp.lpSum(
            (1 if status[i] else 0) * pool[i].capacity_kw * x[i]
            for i in range(n) if i not in active_indices
        )
        prob += shortfall[s] >= sla_target_kw - active_avail - standby_avail_expr + lambda_dro

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=120)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return BaselineSolution(
            standby_ids=(), objective_cost=float("inf"),
            method_label="B3-wasserstein_dro", feasible=False,
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
        method_label="B3-wasserstein_dro",
        feasible=True,
    )
