#!/usr/bin/env python3
"""Compute HC₅₀ for 2 feeders using try6 sweep data."""

from __future__ import annotations

import json
from pathlib import Path

from hcar_metric import load_placements_from_sweep, hc_at_alpha, theta_low
from hc50_metric import bootstrap_hc50

TRY6_RESULTS = Path(__file__).resolve().parent.parent.parent / "mvp_try6" / "results"
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CHILD_DIR = Path.home() / ".gridflow" / "results"

FEEDERS = [
    {"name": "IEEE 13 (4.16 kV, OpenDSS)", "short": "ieee13",
     "sweep": TRY6_RESULTS / "sweep_ieee13.json"},
    {"name": "MV ring 7-bus (20 kV, pandapower)", "short": "mv_ring",
     "sweep": TRY6_RESULTS / "sweep_mv_ring.json"},
]


def main() -> None:
    all_results = {}
    for f in FEEDERS:
        print(f"\n=== {f['short']} ===")
        ps = load_placements_from_sweep(f["sweep"], CHILD_DIR)
        print(f"  loaded {len(ps)} placements")

        r = bootstrap_hc50(ps, n_alpha=101, n_bootstrap=1000, seed=42)

        print(f"  HC_max  = {r.hc_max:.4f} MW")
        if r.hc50_censored:
            print(f"  HC₅₀   = > 0.950 pu  (censored: HC never drops to 50%)")
        else:
            print(f"  HC₅₀   = {r.hc50_theta:.4f} pu  CI95 [{r.hc50_ci95_low:.4f}, {r.hc50_ci95_high:.4f}]")
        if r.hc_width is not None:
            print(f"  HC-width = {r.hc_width:.4f} pu  CI95 [{r.hc_width_ci95_low:.4f}, {r.hc_width_ci95_high:.4f}]")
        else:
            print(f"  HC-width = N/A (HC curve does not cross 90% and 10%)")

        all_results[f["short"]] = {
            "name": f["name"],
            "n_placements": len(ps),
            "hc_max_mw": r.hc_max,
            "hc50_theta_pu": r.hc50_theta,
            "hc50_censored": r.hc50_censored,
            "hc50_ci95": [r.hc50_ci95_low, r.hc50_ci95_high] if not r.hc50_censored else None,
            "hc_width_pu": r.hc_width,
            "hc_width_ci95": [r.hc_width_ci95_low, r.hc_width_ci95_high] if r.hc_width else None,
            "theta_grid": list(r.theta_grid),
            "hc_curve_mw": list(r.hc_curve_mw),
        }

    # Also include HCA-R from try6 for comparison
    with (TRY6_RESULTS / "two_feeder_hcar.json").open() as fh:
        hcar_data = json.load(fh)
    for short in ["ieee13", "mv_ring"]:
        all_results[short]["hcar_mw"] = hcar_data["feeders"][short]["hcar"]
        all_results[short]["hc_range_a_mw"] = hcar_data["feeders"][short]["hc_range_a"]
        all_results[short]["hc_range_b_mw"] = hcar_data["feeders"][short]["hc_range_b"]

    out = RESULTS_DIR / "hc50_analysis.json"
    with out.open("w") as fh:
        json.dump(all_results, fh, indent=2)
    print(f"\nwrote {out}")

    # Summary
    r13 = all_results["ieee13"]
    rmv = all_results["mv_ring"]
    print("\n" + "=" * 70)
    print("2-Feeder HC₅₀ Comparison")
    print("=" * 70)
    print(f"{'Metric':<25} {'IEEE 13':>20} {'MV ring':>20}")
    print("-" * 70)
    print(f"{'HC_max (MW)':<25} {r13['hc_max_mw']:>20.4f} {rmv['hc_max_mw']:>20.4f}")
    hc50_13 = f"{r13['hc50_theta_pu']:.4f}" if r13['hc50_theta_pu'] else "> 0.950"
    hc50_mv = f"{rmv['hc50_theta_pu']:.4f}" if rmv['hc50_theta_pu'] else "> 0.950"
    print(f"{'HC₅₀ (pu)':<25} {hc50_13:>20} {hc50_mv:>20}")
    w13 = f"{r13['hc_width_pu']:.4f}" if r13['hc_width_pu'] else "N/A"
    wmv = f"{rmv['hc_width_pu']:.4f}" if rmv['hc_width_pu'] else "N/A"
    print(f"{'HC-width (pu)':<25} {w13:>20} {wmv:>20}")
    print(f"{'HC (Range A) MW':<25} {r13['hc_range_a_mw']:>20.4f} {rmv['hc_range_a_mw']:>20.4f}")
    print(f"{'HC (Range B) MW':<25} {r13['hc_range_b_mw']:>20.4f} {rmv['hc_range_b_mw']:>20.4f}")
    print(f"{'HCA-R (MW)':<25} {r13['hcar_mw']:>20.4f} {rmv['hcar_mw']:>20.4f}")


if __name__ == "__main__":
    main()
