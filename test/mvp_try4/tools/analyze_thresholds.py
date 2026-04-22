#!/usr/bin/env python3
"""Analyze threshold sensitivity from child experiment JSONs.

Reads child experiments once, applies all three thresholds, and produces:
  1. comparison.json — side-by-side metrics
  2. convergence.json — running mean at n=50,100,200,500,1000
  3. per-experiment rejection rates
"""

from __future__ import annotations

import json
import math
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"
CHILD_DIR = Path.home() / ".gridflow" / "results"

THRESHOLDS = {
    "range_a": (0.95, 1.05),
    "range_b": (0.90, 1.06),
    "custom": (0.92, 1.05),
}

CHECKPOINTS = [50, 100, 200, 500, 1000]


def _load_sweep(name: str) -> dict:
    with (RESULTS_DIR / f"sweep_{name}.json").open() as f:
        return json.load(f)


def _load_child(exp_id: str) -> dict:
    with (CHILD_DIR / f"{exp_id}.json").open() as f:
        return json.load(f)


def _compute_hc(child: dict, low: float, high: float) -> float:
    pv_kw = float(child["metadata"]["parameters"].get("pv_kw", 0))
    voltages = []
    for nr in child.get("node_results", []):
        voltages.extend(v for v in nr.get("voltages", []) if v > 0)
    for step in child.get("steps", []):
        nr = step.get("node_result")
        if nr:
            voltages.extend(v for v in nr.get("voltages", []) if v > 0)
    if not voltages:
        return 0.0
    if min(voltages) < low or max(voltages) > high:
        return 0.0
    return pv_kw / 1000.0


def main() -> None:
    # Use Range B sweep for experiment_ids (same seed → same experiments)
    sweep_b = _load_sweep("range_b")
    exp_ids = sweep_b["experiment_ids"]
    n_total = len(exp_ids)

    print(f"Loading {n_total} child experiments...")

    # Compute HC for each experiment under each threshold
    hc_values: dict[str, list[float]] = {k: [] for k in THRESHOLDS}
    for i, exp_id in enumerate(exp_ids):
        child = _load_child(exp_id)
        for name, (low, high) in THRESHOLDS.items():
            hc_values[name].append(_compute_hc(child, low, high))
        if (i + 1) % 200 == 0:
            print(f"  processed {i + 1}/{n_total}")

    # 1. Comparison JSON
    comparison: dict[str, dict] = {}
    for name, values in hc_values.items():
        n = len(values)
        mean_val = sum(values) / n
        sorted_v = sorted(values)
        median_val = sorted_v[n // 2]
        max_val = max(values)
        min_val = min(values)
        stdev_val = math.sqrt(sum((v - mean_val) ** 2 for v in values) / n) if n > 1 else 0.0
        n_reject = sum(1 for v in values if v == 0.0)
        rejection_rate = n_reject / n
        # 95% CI for mean (normal approx)
        se = stdev_val / math.sqrt(n) if n > 0 else 0.0
        ci_low = mean_val - 1.96 * se
        ci_high = mean_val + 1.96 * se

        comparison[name] = {
            "threshold_low": THRESHOLDS[name][0],
            "threshold_high": THRESHOLDS[name][1],
            "n_experiments": n,
            "hosting_capacity_mw_mean": mean_val,
            "hosting_capacity_mw_median": median_val,
            "hosting_capacity_mw_max": max_val,
            "hosting_capacity_mw_min": min_val,
            "hosting_capacity_mw_stdev": stdev_val,
            "hosting_capacity_mw_ci95_low": ci_low,
            "hosting_capacity_mw_ci95_high": ci_high,
            "rejection_rate": rejection_rate,
            "n_rejected": n_reject,
            "n_accepted": n - n_reject,
        }

    with (RESULTS_DIR / "comparison.json").open("w") as f:
        json.dump(comparison, f, indent=2)
    print(f"wrote {RESULTS_DIR / 'comparison.json'}")

    # 2. Convergence JSON
    convergence: dict[str, list[dict]] = {k: [] for k in THRESHOLDS}
    for name, values in hc_values.items():
        for cp in CHECKPOINTS:
            if cp > len(values):
                break
            subset = values[:cp]
            mean_val = sum(subset) / cp
            stdev_val = math.sqrt(sum((v - mean_val) ** 2 for v in subset) / cp) if cp > 1 else 0.0
            se = stdev_val / math.sqrt(cp)
            convergence[name].append({
                "n": cp,
                "mean": mean_val,
                "stdev": stdev_val,
                "ci95_low": mean_val - 1.96 * se,
                "ci95_high": mean_val + 1.96 * se,
                "rejection_rate": sum(1 for v in subset if v == 0.0) / cp,
            })

    with (RESULTS_DIR / "convergence.json").open("w") as f:
        json.dump(convergence, f, indent=2)
    print(f"wrote {RESULTS_DIR / 'convergence.json'}")

    # Summary
    print("\n=== Threshold Sensitivity Summary ===")
    print(f"{'Threshold':<20} {'Mean HC (MW)':>12} {'95% CI':>20} {'Reject':>8} {'Max HC':>10}")
    print("-" * 75)
    for name in ["range_a", "custom", "range_b"]:
        c = comparison[name]
        ci = f"[{c['hosting_capacity_mw_ci95_low']:.4f}, {c['hosting_capacity_mw_ci95_high']:.4f}]"
        print(f"{name} ({c['threshold_low']}-{c['threshold_high']})"
              f"  {c['hosting_capacity_mw_mean']:>8.4f}"
              f"  {ci:>20}"
              f"  {c['rejection_rate']:>7.1%}"
              f"  {c['hosting_capacity_mw_max']:>8.4f}")


if __name__ == "__main__":
    main()
