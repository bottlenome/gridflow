"""M10 — Time-Constant Diversified VPP Pool selection (try15 contribution).

Greedy heuristic, NOT a MILP (= exits the try11-14 set-cover paradigm).
Selects standby DERs that:

  1. Are observation-orthogonal to E(A) (= trigger-orth, same as try11)
  2. Cover the burst capacity Σ cap ≥ B_k for each axis
  3. Maximise log-τ standard deviation across the chosen set

Algorithm (O(N log N)):

  step 1: candidates = pool \\ active that are not observation-exposed
                       to any E(A) axis (= orthogonality)
  step 2: bucket candidates by τ-decade (10s, 30s, 100s, 300s, 1000s)
  step 3: greedy round-robin over buckets, picking the cheapest still-
          unfulfilled candidate from each bucket, until capacity-cover
          for every axis is satisfied
  step 4: stop, return the selection

This guarantees all τ-decades present in the candidate pool are
represented (= maximum log-τ diversity given capacity constraint).
"""

from __future__ import annotations

import math
import sys
from dataclasses import dataclass
from pathlib import Path

_TRY11 = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

from tools.der_pool import DER, TRIGGER_BASIS_K3, project_exposure  # noqa: E402

from tools15.tau_pool import TauPool, tau_diversity  # noqa: E402


@dataclass(frozen=True)
class M10Solution:
    standby_ids: tuple[str, ...]
    objective_cost: float
    tau_diversity_log: float
    coverage_per_trigger: tuple[tuple[str, float], ...]
    feasible: bool
    mode: str
    trigger_basis: tuple[str, ...]


def _tau_decade(tau_s: float) -> int:
    """Bucket τ_s into a decade index (10**1 ≤ τ < 10**2 → 1, etc.)."""
    if tau_s <= 0:
        return 0
    return int(math.floor(math.log10(tau_s)))


def select_m10(
    tau_pool: TauPool,
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    enforce_orthogonality: bool = True,
    mode: str = "M10-tau-diverse",
) -> M10Solution:
    """Greedy τ-diversified standby selection."""
    pool = tau_pool.pool
    active = tuple(d for d in pool if d.der_id in active_ids)
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    K = len(basis)

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    exposed_active = tuple(
        any(project_exposure(d, basis)[k] for d in active) for k in range(K)
    )

    # Orthogonal candidates: not observation-exposed to any E(A) axis
    eligible: list[tuple[int, DER]] = []
    for i, d in enumerate(candidates):
        if enforce_orthogonality:
            if any(exposed_active[k] and cand_exposure[i][k] for k in range(K)):
                continue
        eligible.append((i, d))

    # Bucket eligible by τ-decade
    buckets: dict[int, list[tuple[int, DER]]] = {}
    for i, d in eligible:
        tau = tau_pool.tau_for(d.der_id)
        buckets.setdefault(_tau_decade(tau), []).append((i, d))

    # Within each bucket, sort by cost (cheap first)
    for bk in buckets:
        buckets[bk].sort(key=lambda p: p[1].contract_cost_standby)

    # Round-robin greedy: traverse buckets, pick cheapest, until capacity-cover.
    chosen: list[tuple[int, DER]] = []
    chosen_ids: set[str] = set()

    def _coverage(k: int) -> float:
        if exposed_active[k]:
            return sum(
                d.capacity_kw for _, d in chosen
                if not project_exposure(d, basis)[k]
            )
        return sum(
            (0.0 if project_exposure(d, basis)[k] else 1.0) * d.capacity_kw
            for _, d in chosen
        )

    def _need_more(k: int) -> bool:
        bk = float(burst_kw.get(basis[k], 0.0))
        return bk > 0 and _coverage(k) < bk

    sorted_buckets = sorted(buckets.keys())
    bucket_iters = {bk: iter(buckets[bk]) for bk in sorted_buckets}

    # Phase 1: force τ-diversity — one cheapest DER from each decade
    # bucket present in candidates. This is the *defining* behavior
    # of M10 (= guaranteed τ-diversification).
    for bk in sorted_buckets:
        try:
            _, d = next(bucket_iters[bk])
        except StopIteration:
            continue
        if d.der_id in chosen_ids:
            continue
        chosen.append((-1, d))
        chosen_ids.add(d.der_id)

    # Phase 2: top-up with cheapest remaining DERs (round-robin)
    # until capacity-cover is satisfied.
    progress = True
    while progress and any(_need_more(k) for k in range(K)):
        progress = False
        for bk in sorted_buckets:
            try:
                _, d = next(bucket_iters[bk])
            except StopIteration:
                continue
            if d.der_id in chosen_ids:
                continue
            chosen.append((-1, d))
            chosen_ids.add(d.der_id)
            progress = True
            if not any(_need_more(k) for k in range(K)):
                break

    feasible = not any(_need_more(k) for k in range(K))
    standby_ids = tuple(d.der_id for _, d in chosen)
    cost = float(sum(d.contract_cost_standby for _, d in chosen))
    diversity = tau_diversity(tau_pool, standby_ids)
    coverage = tuple(
        (basis[k], _coverage(k)) for k in range(K)
    )
    return M10Solution(
        standby_ids=standby_ids,
        objective_cost=cost,
        tau_diversity_log=diversity,
        coverage_per_trigger=coverage,
        feasible=feasible,
        mode=mode,
        trigger_basis=basis,
    )
