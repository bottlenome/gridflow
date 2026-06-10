"""Tier-Hysteresis Reliability Bonding (THRB) state machine — M11 core.

Each DER has a tier T ∈ {1=Probation, 2=Bronze, 3=Silver, 4=Gold}.
Transitions are intentionally asymmetric (= "probation" hysteresis):

  * On drop event:    T <- max(1, T - d_drop)              (fast demotion)
  * After dt_up_s of continuous online time:
                      T <- min(K, T + 1)                   (slow promotion)

The tier state is purely local per-DER and is updated online from the
event stream; no MILP, no global coordination, no comm.

Theorem 4 (theorems.md §4) shows that under heavy-tail Pareto drop
process with exponent alpha ∈ (1, 2.5), the SLA-violation tail of a
tier-Gold-only standby pool decays as O(N^{-(alpha-1)/alpha}), strictly
better than uniform-priority O(N^{-1/2}) (M10) or design-time MILP
O(1) (M1).
"""

from __future__ import annotations

from dataclasses import dataclass, field

K_MAX = 4   # 1=Probation, 2=Bronze, 3=Silver, 4=Gold


@dataclass
class TierState:
    """Per-DER reliability tier with hysteresis.

    Attributes:
        der_id: DER identifier
        tier:   current tier in 1..K_MAX
        last_promotion_t: epoch sec; promotion eligible only if
                          (now - last_promotion_t) >= dt_up_s
        last_drop_t: most recent drop epoch sec (for diagnostics)
        n_drops: cumulative drop counter
    """

    der_id: str
    tier: int = K_MAX           # start optimistic at Gold (default trust)
    last_promotion_t: float = 0.0
    last_drop_t: float = 0.0
    n_drops: int = 0


def apply_drop(s: TierState, t: float, d_drop: int = 1) -> TierState:
    """Demote on drop (fast).  Returns updated state."""
    return TierState(
        der_id=s.der_id,
        tier=max(1, s.tier - max(1, d_drop)),
        last_promotion_t=t,            # reset promotion clock at drop
        last_drop_t=t,
        n_drops=s.n_drops + 1,
    )


def maybe_promote(s: TierState, t: float, dt_up_s: float,
                  k_max: int = K_MAX) -> TierState:
    """If sustained online >= dt_up_s, promote one tier (slow)."""
    if s.tier >= k_max:
        return s
    if (t - s.last_promotion_t) < dt_up_s:
        return s
    return TierState(
        der_id=s.der_id,
        tier=min(k_max, s.tier + 1),
        last_promotion_t=t,
        last_drop_t=s.last_drop_t,
        n_drops=s.n_drops,
    )


def init_pool_state(pool_ids: tuple[str, ...],
                    k_max: int = K_MAX) -> dict[str, TierState]:
    return {d: TierState(der_id=d, tier=k_max) for d in pool_ids}


def tier_summary(state: dict[str, TierState],
                 k_max: int = K_MAX) -> dict[int, int]:
    """Return histogram tier -> count."""
    h = {k: 0 for k in range(1, k_max + 1)}
    for s in state.values():
        h[s.tier] += 1
    return h
