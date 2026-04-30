"""B4 — Markowitz mean-variance correlation portfolio.

Strategy: estimate the historical correlation between DER availabilities
from the *training-period* portion of the trace, then select the
standby pool that minimises portfolio variance subject to a coverage
constraint. The continuous relaxation is solved (cheapest set covering
SLA at minimum variance), then rounded to a binary selection.

Mathematical form (relaxed):
  min_w  w^T Σ w + γ * c^T w
  s.t.   sum w_i * cap_i ≥ SLA target
         0 ≤ w_i ≤ 1   ∀ i

We solve as a quadratic program via numpy/scipy after expressing
covariance from the train-period availability matrix. Then we round w_i
to 1 in descending order until coverage is met.

This represents the §4.1 system E (correlation portfolio) and is the
direct correlational counterpart of the proposed structural method.
"""

from __future__ import annotations

import numpy as np

from ..der_pool import DER
from ..trace_synthesizer import ChurnTrace
from .common import BaselineSolution


def solve_b4_markowitz(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    sla_target_kw: float = 5_000.0,
    risk_aversion: float = 0.01,
) -> BaselineSolution:
    """Pick standby DERs by minimum-variance allocation on train trace.

    Uses the train period of ``trace`` to estimate availability covariance.
    """
    n = len(pool)
    train_steps = trace.train_days * 24 * 60 // trace.timestep_min
    train_steps = min(train_steps, len(trace.der_active_status))
    if train_steps < 2:
        # Insufficient data for covariance — fall back to cheapest-per-kw
        candidates = sorted(
            (d for d in pool if d.der_id not in active_ids),
            key=lambda d: d.contract_cost_standby / max(1.0, d.capacity_kw),
        )
        selected = []
        cap = 0.0
        for d in candidates:
            if cap >= sla_target_kw:
                break
            selected.append(d)
            cap += d.capacity_kw
        return BaselineSolution(
            standby_ids=tuple(d.der_id for d in selected),
            objective_cost=sum(d.contract_cost_standby for d in selected),
            method_label="B4-markowitz",
            feasible=cap >= sla_target_kw,
        )

    # Build availability matrix (n_steps × n_DER), 1 if available 0 otherwise
    avail = np.array(
        [[1.0 if a else 0.0 for a in row] for row in trace.der_active_status[:train_steps]]
    )
    # Per-DER mean availability
    mean_avail = avail.mean(axis=0)
    # Covariance of "unavailability": (1 - avail). High covariance means DERs
    # tend to drop together — we want to pick low-covariance combinations.
    unavail = 1.0 - avail
    cov = np.cov(unavail.T)
    if cov.ndim == 0:
        cov = np.array([[cov]])

    candidates_idx = [i for i, d in enumerate(pool) if d.der_id not in active_ids]
    if not candidates_idx:
        return BaselineSolution(
            standby_ids=(), objective_cost=0.0,
            method_label="B4-markowitz", feasible=False,
        )

    # Greedy selection minimising marginal portfolio variance subject to coverage
    selected_idx: list[int] = []
    selected_cap = 0.0

    while selected_cap < sla_target_kw and candidates_idx:
        best_i = None
        best_score = float("inf")
        for i in candidates_idx:
            if i in selected_idx:
                continue
            test = list(selected_idx) + [i]
            sub_cov = cov[np.ix_(test, test)]
            var_score = float(sub_cov.sum())
            cost_score = pool[i].contract_cost_standby
            cost_per_kw = cost_score / max(1.0, pool[i].capacity_kw)
            score = var_score + risk_aversion * cost_per_kw
            if score < best_score:
                best_score = score
                best_i = i
        if best_i is None:
            break
        selected_idx.append(best_i)
        selected_cap += pool[best_i].capacity_kw

    feasible = selected_cap >= sla_target_kw
    cost = sum(pool[i].contract_cost_standby for i in selected_idx)
    return BaselineSolution(
        standby_ids=tuple(pool[i].der_id for i in selected_idx),
        objective_cost=cost,
        method_label="B4-markowitz",
        feasible=feasible,
    )
