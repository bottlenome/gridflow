"""B1 — Static overprovisioning baseline.

Strategy: contract enough standby DERs so that the *total* standby
capacity is ``overprov_factor`` times the active capacity, with no
trigger-orthogonality reasoning. DERs are picked by cheapest-cost-per-kW
to keep the comparison fair.

This represents the industry-default "just pad the contract" approach.
"""

from __future__ import annotations

from ..der_pool import DER
from .common import BaselineSolution


def solve_b1_static_overprov(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    *,
    overprov_factor: float = 0.30,
) -> BaselineSolution:
    """Select standby = the cheapest-per-kW DERs adding up to
    ``overprov_factor * active_capacity``."""
    active_cap = sum(d.capacity_kw for d in pool if d.der_id in active_ids)
    target_cap = overprov_factor * active_cap

    candidates = [d for d in pool if d.der_id not in active_ids]
    candidates.sort(
        key=lambda d: d.contract_cost_standby / max(1.0, d.capacity_kw)
    )

    selected: list[DER] = []
    total_cap = 0.0
    for d in candidates:
        if total_cap >= target_cap:
            break
        selected.append(d)
        total_cap += d.capacity_kw

    feasible = total_cap >= target_cap
    cost = sum(d.contract_cost_standby for d in selected)
    return BaselineSolution(
        standby_ids=tuple(d.der_id for d in selected),
        objective_cost=cost,
        method_label="B1-static_overprov",
        feasible=feasible,
    )
