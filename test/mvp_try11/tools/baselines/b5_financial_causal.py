"""B5 — Financial causal portfolio (PC algorithm proxy).

Replicates the *spirit* of Lopez de Prado 2019 / Rodriguez Dominguez 2025:
discover causal relationships between DER availabilities from data, then
construct a portfolio that diversifies across causal directions.

We simulate the PC-algorithm-style discovery via partial-correlation
testing on the train-period availability matrix:
  1. Compute the pairwise availability correlation matrix.
  2. For each DER, estimate its "causal cluster" = the set of other DERs
     whose availability is significantly correlated (|ρ| ≥ τ_corr).
  3. Form clusters greedily (a DER's cluster is the connected component
     containing it).
  4. Select a standby pool that draws from *different clusters* to
     maximise causal diversification. Cover SLA target with cheapest-
     per-kW DER in each cluster.

This is intentionally a simplified PC-algorithm-style proxy, not a full
implementation of Spirtes-Glymour PC. The full PC requires conditional
independence testing on a full causal graph, which would be ~500 lines
extra; the simplified version captures the *correlational core* of
finance causal portfolios while preserving §4.5b's structural difference
with SDP (= still relies on observed correlation, not physical
trigger labels).
"""

from __future__ import annotations

import numpy as np

from ..der_pool import DER
from ..trace_synthesizer import ChurnTrace
from .common import BaselineSolution


def _connected_components(adjacency: np.ndarray) -> list[list[int]]:
    """Return clusters from a boolean adjacency matrix."""
    n = adjacency.shape[0]
    visited = [False] * n
    components: list[list[int]] = []
    for start in range(n):
        if visited[start]:
            continue
        stack = [start]
        comp: list[int] = []
        while stack:
            i = stack.pop()
            if visited[i]:
                continue
            visited[i] = True
            comp.append(i)
            for j in range(n):
                if adjacency[i, j] and not visited[j]:
                    stack.append(j)
        components.append(comp)
    return components


def solve_b5_financial_causal(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    sla_target_kw: float = 5_000.0,
    correlation_threshold: float = 0.3,
) -> BaselineSolution:
    """PC-algorithm-style causal cluster portfolio."""
    n = len(pool)
    train_steps = min(
        trace.train_days * 24 * 60 // trace.timestep_min,
        len(trace.der_active_status),
    )
    if train_steps < 5:
        # Fallback: cheapest-per-kw covering
        candidates = sorted(
            (d for d in pool if d.der_id not in active_ids),
            key=lambda d: d.contract_cost_standby / max(1.0, d.capacity_kw),
        )
        selected: list[DER] = []
        cap = 0.0
        for d in candidates:
            if cap >= sla_target_kw:
                break
            selected.append(d)
            cap += d.capacity_kw
        return BaselineSolution(
            standby_ids=tuple(d.der_id for d in selected),
            objective_cost=sum(d.contract_cost_standby for d in selected),
            method_label="B5-financial_causal",
            feasible=cap >= sla_target_kw,
        )

    avail = np.array(
        [[1.0 if a else 0.0 for a in row] for row in trace.der_active_status[:train_steps]]
    )
    # Drop zero-variance columns (a DER that never churned in train)
    var = avail.var(axis=0)
    nonzero = var > 1e-9
    if not nonzero.any():
        # All DERs constant — return cheapest cover
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
            method_label="B5-financial_causal",
            feasible=cap >= sla_target_kw,
        )

    # Replace constant columns with tiny noise to avoid NaN in corrcoef
    safe = avail.copy()
    rng = np.random.default_rng(seed=0)
    for j in range(n):
        if not nonzero[j]:
            safe[:, j] += rng.normal(0, 1e-6, size=train_steps)
    corr = np.corrcoef(safe.T)
    corr = np.nan_to_num(corr, copy=False)

    adjacency = np.abs(corr) >= correlation_threshold
    np.fill_diagonal(adjacency, False)
    components = _connected_components(adjacency)

    # Pick the cheapest-per-kW DER from each cluster (excluding active)
    selected_idx: list[int] = []
    selected_cap = 0.0
    cluster_pool = []
    for comp in components:
        cands = [
            i for i in comp
            if pool[i].der_id not in active_ids
        ]
        cands.sort(
            key=lambda i: pool[i].contract_cost_standby / max(1.0, pool[i].capacity_kw)
        )
        cluster_pool.append(cands)
    # Round-robin pick from clusters until SLA covered
    pick_iter = [iter(c) for c in cluster_pool]
    while selected_cap < sla_target_kw:
        any_picked = False
        for it in pick_iter:
            for _ in range(1):
                try:
                    i = next(it)
                except StopIteration:
                    continue
                if i in selected_idx:
                    continue
                selected_idx.append(i)
                selected_cap += pool[i].capacity_kw
                any_picked = True
                if selected_cap >= sla_target_kw:
                    break
            if selected_cap >= sla_target_kw:
                break
        if not any_picked:
            break

    feasible = selected_cap >= sla_target_kw
    cost = sum(pool[i].contract_cost_standby for i in selected_idx)
    return BaselineSolution(
        standby_ids=tuple(pool[i].der_id for i in selected_idx),
        objective_cost=cost,
        method_label="B5-financial_causal",
        feasible=feasible,
    )
