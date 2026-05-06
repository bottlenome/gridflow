"""M11 — Tier-Hysteresis Reliability Bonding (THRB) selection.

Given the per-DER tier state, M11 picks the cheapest standby subset
that satisfies SLA capacity per trigger axis, with strict tier
preference (= tier-K first, ties broken by cost ascending).

Algorithm (O(N log N) per call):

    1. Filter candidates = pool \ active_set
    2. For each tier T from K_MAX down to 1:
         sort tier-T candidates by cost ascending
         greedy-add until SLA covered (per axis); if covered, return.
    3. If coverage incomplete after Probation tier, return the partial
       selection with feasible=False so the caller can downgrade SLA.

Compared to M1 (try11) it requires no MILP; compared to M10 (try15)
it adds *online* state (tier) on top of the same greedy structure.
The full SLA-tail bound proof is in theorems.md §4.
"""

from __future__ import annotations

from dataclasses import dataclass

from .tier_state import K_MAX, TierState


@dataclass(frozen=True)
class M11Solution:
    standby_ids: tuple[str, ...]
    objective_cost: float
    coverage_per_axis_kw: tuple[tuple[str, float], ...]
    feasible: bool
    tier_histogram_picked: tuple[tuple[int, int], ...]


def select_m11(
    *,
    pool: tuple[tuple[str, float, float], ...],   # (der_id, capacity_kw, cost_kw)
    active_ids: frozenset[str],
    burst_kw_per_axis: dict[str, float],
    exposure_per_axis: dict[str, frozenset[str]],
    tier_state: dict[str, TierState],
) -> M11Solution:
    """Greedy tier-priority selection.

    Args:
        pool: tuple of (der_id, capacity_kw, contract_cost_per_kw)
        active_ids: DERs already serving the active pool
        burst_kw_per_axis: required standby capacity per trigger axis
        exposure_per_axis: which DERs are observation-exposed to each axis
                           (M11 only counts non-exposed contributions, same
                           as M1/M10 trigger-orth convention)
        tier_state: per-DER TierState

    Returns:
        M11Solution with standby_ids, cost, per-axis coverage, feasibility.
    """
    eligible = [
        (d, cap, cost) for (d, cap, cost) in pool if d not in active_ids
    ]
    by_tier: dict[int, list[tuple[str, float, float]]] = {
        k: [] for k in range(1, K_MAX + 1)
    }
    for d, cap, cost in eligible:
        t = tier_state.get(d, TierState(der_id=d)).tier
        by_tier[t].append((d, cap, cost))
    for t in by_tier:
        by_tier[t].sort(key=lambda r: r[2])  # cheapest first

    chosen: list[tuple[str, float, float]] = []
    chosen_ids: set[str] = set()
    coverage = {ax: 0.0 for ax in burst_kw_per_axis}

    def _is_exposed(der_id: str, ax: str) -> bool:
        return der_id in exposure_per_axis.get(ax, frozenset())

    def _all_axes_covered() -> bool:
        return all(coverage[ax] >= burst_kw_per_axis[ax]
                   for ax in burst_kw_per_axis)

    for tier in range(K_MAX, 0, -1):
        if _all_axes_covered():
            break
        for d, cap, cost in by_tier[tier]:
            if d in chosen_ids:
                continue
            chosen.append((d, cap, cost))
            chosen_ids.add(d)
            for ax in burst_kw_per_axis:
                if not _is_exposed(d, ax):
                    coverage[ax] += cap
            if _all_axes_covered():
                break

    feasible = _all_axes_covered()
    standby_ids = tuple(d for d, _, _ in chosen)
    cost_total = float(sum(cost for _, _, cost in chosen))

    th: dict[int, int] = {k: 0 for k in range(1, K_MAX + 1)}
    for d in standby_ids:
        th[tier_state.get(d, TierState(der_id=d)).tier] += 1
    return M11Solution(
        standby_ids=standby_ids,
        objective_cost=cost_total,
        coverage_per_axis_kw=tuple(
            (ax, coverage[ax]) for ax in burst_kw_per_axis
        ),
        feasible=feasible,
        tier_histogram_picked=tuple(sorted(th.items())),
    )
