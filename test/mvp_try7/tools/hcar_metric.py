#!/usr/bin/env python3
"""Threshold-Robust Hosting Capacity Analysis (HCA-R) metric.

This module defines and computes the novel HCA-R metric proposed in try5.
The metric characterizes a feeder's stochastic hosting capacity across
the regulatory voltage-standard range (ANSI C84.1 Range A to Range B),
eliminating the threshold-selection ambiguity of fixed-threshold HCA.

Definitions
-----------
Let alpha ∈ [0, 1] parameterize the regulatory voltage threshold:
    theta_low(alpha)  = 0.90 + 0.05 * alpha
    theta_high(alpha) = 1.06 - 0.01 * alpha
At alpha = 0 the thresholds are ANSI Range B (0.90, 1.06);
at alpha = 1 the thresholds are ANSI Range A (0.95, 1.05).

For a given feeder f and Monte Carlo placement ensemble P = {p_1, ..., p_N}:
    HC_f(alpha) = (1/N) * sum_{i=1..N} accept_f(p_i; alpha) * pv_kw(p_i) / 1000
where
    accept_f(p; alpha) = 1 if all bus voltages in f under placement p lie in
                        [theta_low(alpha), theta_high(alpha)], else 0.

The HCA-R metric is the mean HC across the regulatory range:
    HCA-R_f = integral_{0}^{1} HC_f(alpha) d_alpha  (trapezoidal approximation)
Unit: MW.

Supporting metrics:
    HCA-S_f  = HC_f(0) - HC_f(1)     (regulatory sensitivity, MW)
    HCA-RR_f = 1 - HCA-S / HC_f(0)   (regulatory robustness ratio, dimensionless,
                                       in [0, 1]; 1 = perfectly robust)

Bootstrap CI
------------
For each alpha, 1000 bootstrap resamples of P yield HC_f(alpha) samples;
propagated via the same alpha grid to HCA-R, HCA-S, HCA-RR.
"""

from __future__ import annotations

import json
import math
import random
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Placement:
    """A single Monte Carlo PV placement result."""
    pv_kw: float
    voltages: tuple[float, ...]


@dataclass(frozen=True)
class HCARResult:
    """Computed HCA-R / HCA-S / HCA-RR plus bootstrap CIs and alpha grid."""
    alpha_grid: tuple[float, ...]
    hc_curve: tuple[float, ...]          # HC(alpha) at each alpha
    hc_curve_ci95_low: tuple[float, ...]
    hc_curve_ci95_high: tuple[float, ...]
    hcar: float                          # HCA-R (MW)
    hcar_ci95_low: float
    hcar_ci95_high: float
    hcas: float                          # HCA-S (MW)
    hcas_ci95_low: float
    hcas_ci95_high: float
    hcarr: float                         # HCA-RR (0-1)
    hcarr_ci95_low: float
    hcarr_ci95_high: float


def theta_low(alpha: float) -> float:
    """Lower voltage threshold as a function of alpha."""
    return 0.90 + 0.05 * alpha


def theta_high(alpha: float) -> float:
    """Upper voltage threshold as a function of alpha."""
    return 1.06 - 0.01 * alpha


def hc_at_alpha(placements: list[Placement], alpha: float) -> float:
    """Stochastic hosting capacity (MW) at a single alpha."""
    lo = theta_low(alpha)
    hi = theta_high(alpha)
    total = 0.0
    for p in placements:
        if not p.voltages:
            continue
        if min(p.voltages) >= lo and max(p.voltages) <= hi:
            total += p.pv_kw / 1000.0
    return total / len(placements)


def hcar(placements: list[Placement], alpha_grid: list[float]) -> float:
    """HCA-R: trapezoidal integral of HC(alpha) over [0, 1]."""
    hc_values = [hc_at_alpha(placements, a) for a in alpha_grid]
    # Trapezoidal rule: sum of (hc_i + hc_{i+1})/2 * delta
    integral = 0.0
    for i in range(len(alpha_grid) - 1):
        da = alpha_grid[i + 1] - alpha_grid[i]
        integral += 0.5 * (hc_values[i] + hc_values[i + 1]) * da
    # Normalize by range length so HCA-R has units of MW (mean HC)
    span = alpha_grid[-1] - alpha_grid[0]
    return integral / span if span > 0 else 0.0


def hcas(placements: list[Placement], alpha_grid: list[float]) -> float:
    """HCA-S: regulatory sensitivity = HC(0) - HC(1), in MW."""
    return hc_at_alpha(placements, alpha_grid[0]) - hc_at_alpha(placements, alpha_grid[-1])


def hcarr(placements: list[Placement], alpha_grid: list[float]) -> float:
    """HCA-RR: regulatory robustness ratio in [0, 1], dimensionless."""
    hc0 = hc_at_alpha(placements, alpha_grid[0])
    hc1 = hc_at_alpha(placements, alpha_grid[-1])
    if hc0 <= 0:
        return 0.0
    return max(0.0, min(1.0, hc1 / hc0))


def bootstrap_ci(
    placements: list[Placement],
    alpha_grid: list[float],
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> HCARResult:
    """Compute HCA-R/S/RR with bootstrap 95% CI."""
    rng = random.Random(seed)
    n = len(placements)

    # Point estimates
    point_hc_curve = [hc_at_alpha(placements, a) for a in alpha_grid]
    point_hcar = hcar(placements, alpha_grid)
    point_hcas = hcas(placements, alpha_grid)
    point_hcarr = hcarr(placements, alpha_grid)

    # Bootstrap
    hc_boot: list[list[float]] = [[] for _ in alpha_grid]
    hcar_boot: list[float] = []
    hcas_boot: list[float] = []
    hcarr_boot: list[float] = []

    for _ in range(n_bootstrap):
        # Resample indices with replacement
        idx = [rng.randrange(n) for _ in range(n)]
        sample = [placements[i] for i in idx]
        hc_vals = [hc_at_alpha(sample, a) for a in alpha_grid]
        for j, v in enumerate(hc_vals):
            hc_boot[j].append(v)
        hcar_boot.append(hcar(sample, alpha_grid))
        hcas_boot.append(hcas(sample, alpha_grid))
        hcarr_boot.append(hcarr(sample, alpha_grid))

    def _ci(values: list[float]) -> tuple[float, float]:
        s = sorted(values)
        n = len(s)
        return s[int(0.025 * n)], s[int(0.975 * n)]

    hc_ci = [_ci(hc_boot[j]) for j in range(len(alpha_grid))]
    hcar_ci = _ci(hcar_boot)
    hcas_ci = _ci(hcas_boot)
    hcarr_ci = _ci(hcarr_boot)

    return HCARResult(
        alpha_grid=tuple(alpha_grid),
        hc_curve=tuple(point_hc_curve),
        hc_curve_ci95_low=tuple(c[0] for c in hc_ci),
        hc_curve_ci95_high=tuple(c[1] for c in hc_ci),
        hcar=point_hcar,
        hcar_ci95_low=hcar_ci[0],
        hcar_ci95_high=hcar_ci[1],
        hcas=point_hcas,
        hcas_ci95_low=hcas_ci[0],
        hcas_ci95_high=hcas_ci[1],
        hcarr=point_hcarr,
        hcarr_ci95_low=hcarr_ci[0],
        hcarr_ci95_high=hcarr_ci[1],
    )


def load_placements_from_sweep(sweep_json: Path, child_dir: Path) -> list[Placement]:
    """Load child experiments listed in a SweepResult JSON."""
    with sweep_json.open() as f:
        sweep = json.load(f)
    placements: list[Placement] = []
    for exp_id in sweep["experiment_ids"]:
        child_path = child_dir / f"{exp_id}.json"
        with child_path.open() as f:
            child = json.load(f)
        pv_kw = float(child["metadata"]["parameters"].get("pv_kw", 0))
        voltages: list[float] = []
        for nr in child.get("node_results", []):
            voltages.extend(v for v in nr.get("voltages", []) if v > 0)
        for step in child.get("steps", []):
            nr = step.get("node_result")
            if nr:
                voltages.extend(v for v in nr.get("voltages", []) if v > 0)
        placements.append(Placement(pv_kw=pv_kw, voltages=tuple(voltages)))
    return placements


if __name__ == "__main__":
    # Smoke test: load try5 base sweep and compute HCA-R
    import sys

    sweep_path = Path(__file__).parent.parent / "results" / "sweep_base.json"
    child_dir = Path.home() / ".gridflow" / "results"

    print(f"Loading placements from {sweep_path.name}...")
    ps = load_placements_from_sweep(sweep_path, child_dir)
    print(f"  loaded {len(ps)} placements")

    alpha_grid = [i / 10.0 for i in range(11)]  # 0.0, 0.1, ..., 1.0
    print(f"Computing HCA-R with {len(alpha_grid)} alpha points + 1000 bootstrap...")
    result = bootstrap_ci(ps, alpha_grid, n_bootstrap=1000, seed=42)

    print("\n=== HCA Metrics ===")
    print(f"  HCA-R  = {result.hcar:.4f} MW  CI95 [{result.hcar_ci95_low:.4f}, {result.hcar_ci95_high:.4f}]")
    print(f"  HCA-S  = {result.hcas:.4f} MW  CI95 [{result.hcas_ci95_low:.4f}, {result.hcas_ci95_high:.4f}]")
    print(f"  HCA-RR = {result.hcarr:.4f}     CI95 [{result.hcarr_ci95_low:.4f}, {result.hcarr_ci95_high:.4f}]")

    print("\n=== HC(alpha) curve ===")
    print(f"  {'alpha':>6} {'theta_low':>10} {'theta_high':>11} {'HC (MW)':>9} {'CI95 low':>9} {'CI95 high':>10}")
    for i, a in enumerate(result.alpha_grid):
        print(f"  {a:>6.2f} {theta_low(a):>10.3f} {theta_high(a):>11.3f} "
              f"{result.hc_curve[i]:>9.4f} "
              f"{result.hc_curve_ci95_low[i]:>9.4f} "
              f"{result.hc_curve_ci95_high[i]:>10.4f}")
