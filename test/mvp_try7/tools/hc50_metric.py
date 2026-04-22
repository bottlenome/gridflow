#!/usr/bin/env python3
"""HC₅₀ — Pharmacology-inspired hosting capacity transition metric.

Analogy: IC₅₀ (half-maximal inhibitory concentration) in pharmacology
characterizes a drug's potency by the dose at which 50% inhibition occurs.
HC₅₀ characterizes a feeder's regulatory fragility by the voltage threshold
at which hosting capacity drops to 50% of its maximum.

Definitions
-----------
Let HC(θ) be the stochastic hosting capacity (MW) at lower voltage
threshold θ_low = θ (upper threshold fixed or co-varied via α).

    HC_max = HC(θ_min)     where θ_min = 0.90 (Range B lower)

    HC₅₀ = θ such that HC(θ) = 0.5 × HC_max
            (linear interpolation on the HC(θ) grid)

    HC-width = θ(HC=0.1×HC_max) - θ(HC=0.9×HC_max)
               i.e., the threshold range over which HC transitions
               from 90% to 10% of max. Narrow = cliff-like (fragile),
               wide = graceful degradation.

If HC never drops to 50% within [θ_min, θ_max], HC₅₀ is reported as
"> θ_max" (censored), indicating the feeder is robust beyond the
regulatory range.
"""

from __future__ import annotations

import random
from dataclasses import dataclass

from hcar_metric import Placement, hc_at_alpha, theta_low, theta_high


@dataclass(frozen=True)
class HC50Result:
    """HC₅₀ analysis result for a single feeder."""
    hc_max: float                        # HC at most permissive threshold (MW)
    hc50_theta: float | None             # θ_low where HC = 50% of max (pu), None if censored
    hc50_censored: bool                  # True if HC never drops to 50%
    hc_width: float | None               # θ(10%) - θ(90%), None if not computable
    theta_grid: tuple[float, ...]
    hc_curve_mw: tuple[float, ...]

    # Bootstrap CI
    hc50_ci95_low: float | None
    hc50_ci95_high: float | None
    hc_width_ci95_low: float | None
    hc_width_ci95_high: float | None


def _find_crossing(thetas: list[float], hc_vals: list[float], target: float) -> float | None:
    """Find θ where HC crosses target via linear interpolation."""
    for i in range(len(thetas) - 1):
        if hc_vals[i] >= target >= hc_vals[i + 1]:
            # Linear interpolation
            if hc_vals[i] == hc_vals[i + 1]:
                return thetas[i]
            frac = (hc_vals[i] - target) / (hc_vals[i] - hc_vals[i + 1])
            return thetas[i] + frac * (thetas[i + 1] - thetas[i])
    return None


def compute_hc50(
    placements: list[Placement],
    n_alpha: int = 101,
) -> tuple[float | None, float | None, list[float], list[float]]:
    """Compute HC₅₀ and HC-width from placements.

    Returns (hc50_theta, hc_width, theta_grid, hc_curve).
    """
    alpha_grid = [i / (n_alpha - 1) for i in range(n_alpha)]
    theta_grid = [theta_low(a) for a in alpha_grid]
    hc_curve = [hc_at_alpha(placements, a) for a in alpha_grid]

    hc_max = hc_curve[0]
    if hc_max <= 0:
        return None, None, theta_grid, hc_curve

    target_50 = 0.5 * hc_max
    target_90 = 0.9 * hc_max
    target_10 = 0.1 * hc_max

    hc50 = _find_crossing(theta_grid, hc_curve, target_50)
    theta_90 = _find_crossing(theta_grid, hc_curve, target_90)
    theta_10 = _find_crossing(theta_grid, hc_curve, target_10)

    hc_width = None
    if theta_90 is not None and theta_10 is not None:
        hc_width = theta_10 - theta_90

    return hc50, hc_width, theta_grid, hc_curve


def bootstrap_hc50(
    placements: list[Placement],
    n_alpha: int = 101,
    n_bootstrap: int = 1000,
    seed: int = 42,
) -> HC50Result:
    """Compute HC₅₀ with bootstrap 95% CI."""
    rng = random.Random(seed)
    n = len(placements)

    # Point estimates
    hc50, hc_width, theta_grid, hc_curve = compute_hc50(placements, n_alpha)
    hc_max = hc_curve[0]

    # Bootstrap
    hc50_boot: list[float] = []
    width_boot: list[float] = []
    for _ in range(n_bootstrap):
        idx = [rng.randrange(n) for _ in range(n)]
        sample = [placements[i] for i in idx]
        b50, bw, _, _ = compute_hc50(sample, n_alpha)
        if b50 is not None:
            hc50_boot.append(b50)
        if bw is not None:
            width_boot.append(bw)

    def _ci(vals: list[float]) -> tuple[float | None, float | None]:
        if len(vals) < 20:
            return None, None
        s = sorted(vals)
        return s[int(0.025 * len(s))], s[int(0.975 * len(s))]

    hc50_ci = _ci(hc50_boot)
    width_ci = _ci(width_boot)

    return HC50Result(
        hc_max=hc_max,
        hc50_theta=hc50,
        hc50_censored=hc50 is None,
        hc_width=hc_width,
        theta_grid=tuple(theta_grid),
        hc_curve_mw=tuple(hc_curve),
        hc50_ci95_low=hc50_ci[0],
        hc50_ci95_high=hc50_ci[1],
        hc_width_ci95_low=width_ci[0],
        hc_width_ci95_high=width_ci[1],
    )
