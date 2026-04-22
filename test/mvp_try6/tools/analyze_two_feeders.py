#!/usr/bin/env python3
"""Compute HCA-R/S/RR for two feeders and generate comparison JSON."""

from __future__ import annotations

import json
from pathlib import Path

from hcar_metric import (
    bootstrap_ci,
    hc_at_alpha,
    load_placements_from_sweep,
    theta_low,
    theta_high,
)

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CHILD_DIR = Path.home() / ".gridflow" / "results"

ALPHA_GRID = [i / 20.0 for i in range(21)]  # 0.00, 0.05, ..., 1.00 (21 points)
BOOTSTRAP = 1000
CONVERGENCE_NS = [100, 200, 500, 1000]

FEEDERS = [
    {
        "name": "IEEE 13 (4.16 kV, OpenDSS)",
        "short": "ieee13",
        "sweep_json": "sweep_ieee13.json",
    },
    {
        "name": "MV ring 7-bus (20 kV, pandapower)",
        "short": "mv_ring",
        "sweep_json": "sweep_mv_ring.json",
    },
]


def analyze_feeder(sweep_file: str, short: str) -> dict:
    print(f"\n=== {short} ===")
    ps = load_placements_from_sweep(RESULTS_DIR / sweep_file, CHILD_DIR)
    print(f"  loaded {len(ps)} placements")

    result = bootstrap_ci(ps, ALPHA_GRID, n_bootstrap=BOOTSTRAP, seed=42)

    # Convergence with same BOOTSTRAP count for all checkpoints
    convergence = []
    for n in CONVERGENCE_NS:
        sub = ps[:n]
        r = bootstrap_ci(sub, ALPHA_GRID, n_bootstrap=BOOTSTRAP, seed=42)
        convergence.append({
            "n": n,
            "hcar": r.hcar, "hcar_ci95": [r.hcar_ci95_low, r.hcar_ci95_high],
            "hcas": r.hcas, "hcas_ci95": [r.hcas_ci95_low, r.hcas_ci95_high],
            "hcarr": r.hcarr, "hcarr_ci95": [r.hcarr_ci95_low, r.hcarr_ci95_high],
        })
        ci_w = r.hcar_ci95_high - r.hcar_ci95_low
        print(f"  n={n:>4}: HCA-R={r.hcar:.4f} CI[{r.hcar_ci95_low:.4f},{r.hcar_ci95_high:.4f}] w={ci_w:.4f}")

    return {
        "alpha_grid": list(result.alpha_grid),
        "hc_curve": list(result.hc_curve),
        "hc_curve_ci95_low": list(result.hc_curve_ci95_low),
        "hc_curve_ci95_high": list(result.hc_curve_ci95_high),
        "hcar": result.hcar,
        "hcar_ci95": [result.hcar_ci95_low, result.hcar_ci95_high],
        "hcas": result.hcas,
        "hcas_ci95": [result.hcas_ci95_low, result.hcas_ci95_high],
        "hcarr": result.hcarr,
        "hcarr_ci95": [result.hcarr_ci95_low, result.hcarr_ci95_high],
        "hc_range_a": hc_at_alpha(ps, 1.0),
        "hc_range_b": hc_at_alpha(ps, 0.0),
        "convergence": convergence,
    }


def main() -> None:
    results = {}
    for f in FEEDERS:
        results[f["short"]] = analyze_feeder(f["sweep_json"], f["short"])
        results[f["short"]]["name"] = f["name"]

    # 2-feeder comparison summary
    comparison = {
        "metric_definitions": {
            "alpha_grid_points": len(ALPHA_GRID),
            "alpha_range": [ALPHA_GRID[0], ALPHA_GRID[-1]],
            "theta_low_formula": "0.90 + 0.05 * alpha",
            "theta_high_formula": "1.06 - 0.01 * alpha",
            "bootstrap_resamples": BOOTSTRAP,
            "bootstrap_seed": 42,
        },
        "feeders": results,
    }

    out = RESULTS_DIR / "two_feeder_hcar.json"
    with out.open("w") as f:
        json.dump(comparison, f, indent=2)
    print(f"\nwrote {out}")

    # Summary table
    print("\n" + "=" * 75)
    print("2-Feeder HCA-R Comparison (n=1000 each)")
    print("=" * 75)
    print(f"{'Metric':<22} {'IEEE 13':>20} {'MV ring':>20}")
    print("-" * 75)
    for key in ["ieee13", "mv_ring"]:
        pass
    r13 = results["ieee13"]
    rmv = results["mv_ring"]
    for label, k in [("HC (Range A)", "hc_range_a"), ("HC (Range B)", "hc_range_b")]:
        print(f"{label:<22} {r13[k]:>20.4f} {rmv[k]:>20.4f}")
    for label, k, ci_k in [
        ("HCA-R (MW)", "hcar", "hcar_ci95"),
        ("HCA-S (MW)", "hcas", "hcas_ci95"),
        ("HCA-RR", "hcarr", "hcarr_ci95"),
    ]:
        v13 = f"{r13[k]:.4f} [{r13[ci_k][0]:.3f},{r13[ci_k][1]:.3f}]"
        vmv = f"{rmv[k]:.4f} [{rmv[ci_k][0]:.3f},{rmv[ci_k][1]:.3f}]"
        print(f"{label:<22} {v13:>20} {vmv:>20}")


if __name__ == "__main__":
    main()
