#!/usr/bin/env python3
"""Generate publication-quality figure for threshold sensitivity study."""

from __future__ import annotations

import json
from pathlib import Path

RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    with (RESULTS_DIR / "comparison.json").open() as f:
        comp = json.load(f)
    with (RESULTS_DIR / "convergence.json").open() as f:
        conv = json.load(f)

    labels = ["Range A\n(0.95–1.05)", "Custom\n(0.92–1.05)", "Range B\n(0.90–1.06)"]
    keys = ["range_a", "custom", "range_b"]
    colors = ["#d62728", "#ff7f0e", "#2ca02c"]

    means = [comp[k]["hosting_capacity_mw_mean"] for k in keys]
    ci_lows = [comp[k]["hosting_capacity_mw_ci95_low"] for k in keys]
    ci_highs = [comp[k]["hosting_capacity_mw_ci95_high"] for k in keys]
    errors_low = [m - cl for m, cl in zip(means, ci_lows)]
    errors_high = [ch - m for m, ch in zip(means, ci_highs)]
    reject_rates = [comp[k]["rejection_rate"] * 100 for k in keys]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8))
    fig.suptitle(
        "Impact of Voltage Standard Selection on Stochastic Hosting Capacity\n"
        "IEEE 13-Node Feeder, n=1000 Random PV Placements, OpenDSS",
        fontsize=12,
    )

    # (a) Bar chart: mean HC with 95% CI
    ax = axes[0, 0]
    x = range(len(labels))
    bars = ax.bar(x, means, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.errorbar(x, means, yerr=[errors_low, errors_high], fmt="none", ecolor="black", capsize=5, linewidth=1.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Mean Hosting Capacity [MW]")
    ax.set_title("(a) Mean HC with 95% CI")
    ax.grid(True, axis="y", alpha=0.3)
    for i, (m, ci_l, ci_h) in enumerate(zip(means, ci_lows, ci_highs)):
        if m > 0:
            ax.text(i, m + errors_high[i] + 0.03, f"{m:.3f}\n[{ci_l:.3f}, {ci_h:.3f}]",
                    ha="center", va="bottom", fontsize=7)
        else:
            ax.text(i, 0.02, "0.000\n(100% reject)", ha="center", va="bottom", fontsize=7)

    # (b) Rejection rate
    ax = axes[0, 1]
    ax.bar(x, reject_rates, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, fontsize=9)
    ax.set_ylabel("Rejection Rate [%]")
    ax.set_title("(b) Placement Rejection Rate")
    ax.set_ylim(0, 110)
    ax.grid(True, axis="y", alpha=0.3)
    for i, r in enumerate(reject_rates):
        ax.text(i, r + 2, f"{r:.1f}%", ha="center", va="bottom", fontsize=9, fontweight="bold")

    # (c) Convergence of mean HC
    ax = axes[1, 0]
    for k, color, label in zip(keys, colors, ["Range A", "Custom", "Range B"]):
        ns = [pt["n"] for pt in conv[k]]
        ms = [pt["mean"] for pt in conv[k]]
        ci_lo = [pt["ci95_low"] for pt in conv[k]]
        ci_hi = [pt["ci95_high"] for pt in conv[k]]
        ax.plot(ns, ms, "o-", color=color, label=label, markersize=4)
        ax.fill_between(ns, ci_lo, ci_hi, color=color, alpha=0.15)
    ax.set_xlabel("Number of Monte Carlo samples")
    ax.set_ylabel("Mean Hosting Capacity [MW]")
    ax.set_title("(c) Convergence of Mean HC (95% CI band)")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xscale("log")
    ax.set_xticks([50, 100, 200, 500, 1000])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

    # (d) Summary text
    ax = axes[1, 1]
    ax.axis("off")
    text_lines = [
        "Threshold Sensitivity Summary",
        "",
        "IEEE 13-Node Test Feeder (4.16 kV)",
        "Solver: OpenDSS  |  n = 1000 per scenario",
        f"Total: 3000 experiments, all seed-controlled",
        "",
        "Key Finding:",
        "  Voltage standard selection alone changes",
        f"  mean HC from 0.000 MW to {means[2]:.3f} MW",
        f"  on the same feeder with the same PV placements.",
        "",
        f"  Range A: {reject_rates[0]:.0f}% rejection → HC = 0",
        f"  Custom:  {reject_rates[1]:.0f}% rejection → HC = {means[1]:.3f} MW",
        f"  Range B: {reject_rates[2]:.0f}% rejection → HC = {means[2]:.3f} MW",
        "",
        "Implication:",
        "  HCA studies must specify voltage standard.",
        "  Results are not comparable across standards.",
    ]
    ax.text(0.02, 0.98, "\n".join(text_lines), family="monospace", fontsize=8.5,
            va="top", ha="left", transform=ax.transAxes)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = RESULTS_DIR / "threshold_sensitivity.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
