#!/usr/bin/env python3
"""Compute HCA-R and comparison metrics; persist to JSON for report.md."""

from __future__ import annotations

import json
import math
from dataclasses import asdict
from pathlib import Path

from hcar_metric import (
    Placement,
    bootstrap_ci,
    hc_at_alpha,
    load_placements_from_sweep,
    theta_low,
    theta_high,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CHILD_DIR = Path.home() / ".gridflow" / "results"

ALPHA_GRID = [i / 10.0 for i in range(11)]  # 0.0, 0.1, ..., 1.0
CHECKPOINTS = [100, 200, 500, 1000]
BOOTSTRAP = 1000


def _ci(values: list[float]) -> tuple[float, float]:
    s = sorted(values)
    n = len(s)
    return s[int(0.025 * n)], s[int(0.975 * n)]


def main() -> None:
    print("Loading base sweep placements...")
    placements = load_placements_from_sweep(
        RESULTS_DIR / "sweep_base.json", CHILD_DIR
    )
    print(f"  loaded {len(placements)} placements")

    # 1. Primary HCA-R computation with bootstrap
    print(f"\nComputing HCA-R at n={len(placements)} with {BOOTSTRAP} bootstrap resamples...")
    result = bootstrap_ci(placements, ALPHA_GRID, n_bootstrap=BOOTSTRAP, seed=42)

    # 2. Convergence: HCA-R at growing sample sizes
    print("\nConvergence analysis...")
    convergence = []
    for n in CHECKPOINTS:
        sub = placements[:n]
        r = bootstrap_ci(sub, ALPHA_GRID, n_bootstrap=500, seed=42)
        convergence.append({
            "n": n,
            "hcar": r.hcar,
            "hcar_ci95_low": r.hcar_ci95_low,
            "hcar_ci95_high": r.hcar_ci95_high,
            "hcas": r.hcas,
            "hcas_ci95_low": r.hcas_ci95_low,
            "hcas_ci95_high": r.hcas_ci95_high,
        })
        print(f"  n={n}: HCA-R = {r.hcar:.4f} CI[{r.hcar_ci95_low:.4f}, {r.hcar_ci95_high:.4f}]")

    # 3. Comparison: HCA-R vs fixed-threshold HC metrics
    hc_range_a = hc_at_alpha(placements, 1.0)  # (0.95, 1.05)
    hc_range_b = hc_at_alpha(placements, 0.0)  # (0.90, 1.06)
    # Bootstrap CI for fixed-threshold HC
    rng_seed = 42
    import random
    rng = random.Random(rng_seed)
    hc_a_boot: list[float] = []
    hc_b_boot: list[float] = []
    for _ in range(BOOTSTRAP):
        idx = [rng.randrange(len(placements)) for _ in range(len(placements))]
        sample = [placements[i] for i in idx]
        hc_a_boot.append(hc_at_alpha(sample, 1.0))
        hc_b_boot.append(hc_at_alpha(sample, 0.0))
    hc_a_ci = _ci(hc_a_boot)
    hc_b_ci = _ci(hc_b_boot)

    comparison = {
        "hc_range_a": {
            "point": hc_range_a,
            "ci95_low": hc_a_ci[0],
            "ci95_high": hc_a_ci[1],
            "threshold": "(0.95, 1.05)",
            "note": "Fixed Range A threshold",
        },
        "hc_range_b": {
            "point": hc_range_b,
            "ci95_low": hc_b_ci[0],
            "ci95_high": hc_b_ci[1],
            "threshold": "(0.90, 1.06)",
            "note": "Fixed Range B threshold",
        },
        "hcar": {
            "point": result.hcar,
            "ci95_low": result.hcar_ci95_low,
            "ci95_high": result.hcar_ci95_high,
            "threshold": "integrated over alpha in [0, 1]",
            "note": "Threshold-robust HCA (proposed)",
        },
        "hcas": {
            "point": result.hcas,
            "ci95_low": result.hcas_ci95_low,
            "ci95_high": result.hcas_ci95_high,
            "unit": "MW",
            "note": "Regulatory sensitivity: HC(Range B) - HC(Range A)",
        },
        "hcarr": {
            "point": result.hcarr,
            "ci95_low": result.hcarr_ci95_low,
            "ci95_high": result.hcarr_ci95_high,
            "unit": "dimensionless",
            "note": "Regulatory robustness ratio: HC(Range A) / HC(Range B)",
        },
    }

    # 4. Persist all results
    hcar_json = {
        "metric_definitions": {
            "alpha_grid": list(ALPHA_GRID),
            "theta_low_formula": "0.90 + 0.05 * alpha",
            "theta_high_formula": "1.06 - 0.01 * alpha",
            "alpha_0_thresholds": [theta_low(0.0), theta_high(0.0)],
            "alpha_1_thresholds": [theta_low(1.0), theta_high(1.0)],
            "hcar": "trapezoidal integral of HC(alpha) over [0, 1], normalized by span",
            "hcas": "HC(alpha=0) - HC(alpha=1)",
            "hcarr": "HC(alpha=1) / HC(alpha=0), clipped to [0, 1]",
            "bootstrap_resamples": BOOTSTRAP,
            "bootstrap_seed": 42,
        },
        "n_placements": len(placements),
        "hc_curve": {
            "alpha": list(result.alpha_grid),
            "theta_low": [theta_low(a) for a in result.alpha_grid],
            "theta_high": [theta_high(a) for a in result.alpha_grid],
            "hc_mw": list(result.hc_curve),
            "ci95_low": list(result.hc_curve_ci95_low),
            "ci95_high": list(result.hc_curve_ci95_high),
        },
        "metrics": {
            "hcar_mw": {
                "point": result.hcar,
                "ci95_low": result.hcar_ci95_low,
                "ci95_high": result.hcar_ci95_high,
            },
            "hcas_mw": {
                "point": result.hcas,
                "ci95_low": result.hcas_ci95_low,
                "ci95_high": result.hcas_ci95_high,
            },
            "hcarr": {
                "point": result.hcarr,
                "ci95_low": result.hcarr_ci95_low,
                "ci95_high": result.hcarr_ci95_high,
            },
        },
        "comparison_to_fixed_threshold": comparison,
        "convergence": convergence,
    }
    out = RESULTS_DIR / "hcar_analysis.json"
    with out.open("w") as f:
        json.dump(hcar_json, f, indent=2)
    print(f"\nwrote {out}")

    # 5. Summary
    print("\n=== Summary (IEEE 13 feeder, n=1000) ===")
    print(f"{'Metric':<25} {'Point':>10} {'CI95':>22}")
    print("-" * 60)
    print(f"{'HC (Range A)':<25} {hc_range_a:>10.4f} {'[':>2}{hc_a_ci[0]:.4f}, {hc_a_ci[1]:.4f}]")
    print(f"{'HC (Range B)':<25} {hc_range_b:>10.4f} {'[':>2}{hc_b_ci[0]:.4f}, {hc_b_ci[1]:.4f}]")
    print(f"{'HCA-R (proposed, MW)':<25} {result.hcar:>10.4f} {'[':>2}{result.hcar_ci95_low:.4f}, {result.hcar_ci95_high:.4f}]")
    print(f"{'HCA-S (sensitivity)':<25} {result.hcas:>10.4f} {'[':>2}{result.hcas_ci95_low:.4f}, {result.hcas_ci95_high:.4f}]")
    print(f"{'HCA-RR (robustness)':<25} {result.hcarr:>10.4f} {'[':>2}{result.hcarr_ci95_low:.4f}, {result.hcarr_ci95_high:.4f}]")


if __name__ == "__main__":
    main()
