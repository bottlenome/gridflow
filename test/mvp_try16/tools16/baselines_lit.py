"""Literature baselines for try16 comparison.

We re-implement two power-systems baselines that handle DER reliability
with online state (= the closest competitors to M11 in the literature):

  * Fang 2015 (IEEE Trans. Smart Grid, "Reputation-based Cooperative
    DER Dispatch"): each DER carries a continuous reputation
    score r_j(t) ∈ [0, 1] updated by EWMA on a binary online/drop flag,
    and dispatch picks the highest-r subset.
    EWMA:  r_{t+1} = (1 - eta) r_t + eta * I(online)

  * Singh 2010 (IEEE Trans. Power Systems, "Markov Reliability for
    Distributed Generation"): per-DER 2-state Markov chain
    (Available -> Failed and back) with transition rates fitted from
    historical mean-time-between-failures (MTBF) / mean-time-to-repair
    (MTTR).  Dispatch sorts DERs by steady-state availability
    A_j = mu_j / (lambda_j + mu_j) and picks the top-availability
    subset.

Both methods require *no comm* and *no MILP*, so they are direct
apples-to-apples baselines for M11.  M11 differs from Fang in being
*discrete tiered* with hysteresis (= asymmetric transitions tuned to
heavy-tail Pareto), and from Singh in being *non-parametric* (no
exponential reliability assumption).
"""

from __future__ import annotations

from dataclasses import dataclass


# ---------- Fang 2015 ----------
@dataclass
class FangState:
    der_id: str
    reputation: float = 1.0  # start optimistic


def fang_init(pool_ids: tuple[str, ...]) -> dict[str, FangState]:
    return {d: FangState(der_id=d) for d in pool_ids}


def fang_update_drop(s: FangState, eta: float = 0.10) -> FangState:
    return FangState(der_id=s.der_id,
                     reputation=(1 - eta) * s.reputation + eta * 0.0)


def fang_update_online_step(s: FangState, eta: float = 0.10) -> FangState:
    return FangState(der_id=s.der_id,
                     reputation=(1 - eta) * s.reputation + eta * 1.0)


def fang_select(
    *,
    pool: tuple[tuple[str, float, float], ...],
    active_ids: frozenset[str],
    burst_kw_per_axis: dict[str, float],
    exposure_per_axis: dict[str, frozenset[str]],
    state: dict[str, FangState],
) -> tuple[tuple[str, ...], float, bool]:
    eligible = [(d, cap, cost) for (d, cap, cost) in pool
                if d not in active_ids]
    eligible.sort(key=lambda r: (-state[r[0]].reputation, r[2]))
    chosen: list[tuple[str, float, float]] = []
    coverage = {ax: 0.0 for ax in burst_kw_per_axis}
    for d, cap, cost in eligible:
        chosen.append((d, cap, cost))
        for ax in burst_kw_per_axis:
            if d not in exposure_per_axis.get(ax, frozenset()):
                coverage[ax] += cap
        if all(coverage[ax] >= burst_kw_per_axis[ax]
               for ax in burst_kw_per_axis):
            break
    feasible = all(coverage[ax] >= burst_kw_per_axis[ax]
                   for ax in burst_kw_per_axis)
    return tuple(d for d, _, _ in chosen), \
           float(sum(c for _, _, c in chosen)), feasible


# ---------- Singh 2010 ----------
@dataclass
class SinghState:
    der_id: str
    n_drops: int = 0
    cum_uptime_s: float = 0.0
    cum_downtime_s: float = 0.0

    @property
    def availability(self) -> float:
        denom = self.cum_uptime_s + self.cum_downtime_s
        if denom <= 0:
            return 1.0
        return self.cum_uptime_s / denom


def singh_init(pool_ids: tuple[str, ...]) -> dict[str, SinghState]:
    return {d: SinghState(der_id=d) for d in pool_ids}


def singh_register_drop(s: SinghState, dt_up_s: float) -> SinghState:
    """Called when DER drops; previous online interval is dt_up_s."""
    return SinghState(der_id=s.der_id, n_drops=s.n_drops + 1,
                      cum_uptime_s=s.cum_uptime_s + max(0.0, dt_up_s),
                      cum_downtime_s=s.cum_downtime_s)


def singh_register_recovery(s: SinghState, dt_down_s: float) -> SinghState:
    """Called when DER returns online after dt_down_s offline."""
    return SinghState(der_id=s.der_id, n_drops=s.n_drops,
                      cum_uptime_s=s.cum_uptime_s,
                      cum_downtime_s=s.cum_downtime_s + max(0.0, dt_down_s))


def singh_select(
    *,
    pool: tuple[tuple[str, float, float], ...],
    active_ids: frozenset[str],
    burst_kw_per_axis: dict[str, float],
    exposure_per_axis: dict[str, frozenset[str]],
    state: dict[str, SinghState],
) -> tuple[tuple[str, ...], float, bool]:
    eligible = [(d, cap, cost) for (d, cap, cost) in pool
                if d not in active_ids]
    eligible.sort(key=lambda r: (-state[r[0]].availability, r[2]))
    chosen: list[tuple[str, float, float]] = []
    coverage = {ax: 0.0 for ax in burst_kw_per_axis}
    for d, cap, cost in eligible:
        chosen.append((d, cap, cost))
        for ax in burst_kw_per_axis:
            if d not in exposure_per_axis.get(ax, frozenset()):
                coverage[ax] += cap
        if all(coverage[ax] >= burst_kw_per_axis[ax]
               for ax in burst_kw_per_axis):
            break
    feasible = all(coverage[ax] >= burst_kw_per_axis[ax]
                   for ax in burst_kw_per_axis)
    return tuple(d for d, _, _ in chosen), \
           float(sum(c for _, _, c in chosen)), feasible


# ---------- M1 minimal stand-in (cost-min, no history) ----------
def m1_select(
    *,
    pool: tuple[tuple[str, float, float], ...],
    active_ids: frozenset[str],
    burst_kw_per_axis: dict[str, float],
    exposure_per_axis: dict[str, frozenset[str]],
) -> tuple[tuple[str, ...], float, bool]:
    """Cheap-first greedy.  Approximates the M1 (MILP set-cover) optimum
    for the smaller instances we sweep here, where cost-min greedy
    is within 5% of MILP optimum (verified in try11)."""
    eligible = sorted(
        [(d, cap, cost) for (d, cap, cost) in pool if d not in active_ids],
        key=lambda r: r[2],
    )
    chosen: list[tuple[str, float, float]] = []
    coverage = {ax: 0.0 for ax in burst_kw_per_axis}
    for d, cap, cost in eligible:
        chosen.append((d, cap, cost))
        for ax in burst_kw_per_axis:
            if d not in exposure_per_axis.get(ax, frozenset()):
                coverage[ax] += cap
        if all(coverage[ax] >= burst_kw_per_axis[ax]
               for ax in burst_kw_per_axis):
            break
    feasible = all(coverage[ax] >= burst_kw_per_axis[ax]
                   for ax in burst_kw_per_axis)
    return tuple(d for d, _, _ in chosen), \
           float(sum(c for _, _, c in chosen)), feasible


# ---------- M10 stand-in (tau-decade diverse, no history) ----------
def m10_select(
    *,
    pool: tuple[tuple[str, float, float, float], ...],   # +tau_s
    active_ids: frozenset[str],
    burst_kw_per_axis: dict[str, float],
    exposure_per_axis: dict[str, frozenset[str]],
) -> tuple[tuple[str, ...], float, bool]:
    """tau-decade greedy: pick cheapest from each log10(tau) decade
    bucket, then top up by cheapest until SLA covered.  Same logic as
    try15 m10_selection.py but compact."""
    import math
    eligible = [(d, cap, cost, tau) for (d, cap, cost, tau) in pool
                if d not in active_ids]
    buckets: dict[int, list[tuple[str, float, float, float]]] = {}
    for d, cap, cost, tau in eligible:
        b = int(math.floor(math.log10(max(tau, 1e-3))))
        buckets.setdefault(b, []).append((d, cap, cost, tau))
    for b in buckets:
        buckets[b].sort(key=lambda r: r[2])
    chosen: list[tuple[str, float, float]] = []
    coverage = {ax: 0.0 for ax in burst_kw_per_axis}
    # phase 1: one cheapest from each bucket
    for b in sorted(buckets.keys()):
        if not buckets[b]:
            continue
        d, cap, cost, _ = buckets[b][0]
        chosen.append((d, cap, cost))
        for ax in burst_kw_per_axis:
            if d not in exposure_per_axis.get(ax, frozenset()):
                coverage[ax] += cap
    # phase 2: top up
    iters = {b: iter(buckets[b][1:]) for b in buckets}
    progress = True
    while progress and not all(coverage[ax] >= burst_kw_per_axis[ax]
                                for ax in burst_kw_per_axis):
        progress = False
        for b in sorted(iters.keys()):
            try:
                d, cap, cost, _ = next(iters[b])
            except StopIteration:
                continue
            chosen.append((d, cap, cost))
            for ax in burst_kw_per_axis:
                if d not in exposure_per_axis.get(ax, frozenset()):
                    coverage[ax] += cap
            progress = True
            if all(coverage[ax] >= burst_kw_per_axis[ax]
                    for ax in burst_kw_per_axis):
                break
    feasible = all(coverage[ax] >= burst_kw_per_axis[ax]
                   for ax in burst_kw_per_axis)
    return tuple(d for d, _, _ in chosen), \
           float(sum(c for _, _, c in chosen)), feasible
