#!/usr/bin/env python3
"""Generate publication-quality figure for HCA-R methodology paper."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results_dir = Path(__file__).resolve().parent.parent / "results"
    with (results_dir / "hcar_analysis.json").open() as f:
        data = json.load(f)

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(
        "Threshold-Robust Hosting Capacity (HCA-R):\n"
        "A Regulatory-Standard-Independent HCA Metric (IEEE 13, n=1000)",
        fontsize=12,
    )

    # (a) HC(alpha) curve with CI band + HCA-R shaded region
    ax = axes[0, 0]
    curve = data["hc_curve"]
    alphas = curve["alpha"]
    hc = curve["hc_mw"]
    ci_lo = curve["ci95_low"]
    ci_hi = curve["ci95_high"]
    ax.plot(alphas, hc, "o-", color="#1f77b4", linewidth=2, markersize=5, label="HC(α)")
    ax.fill_between(alphas, ci_lo, ci_hi, color="#1f77b4", alpha=0.2, label="95% CI")
    # Shaded area under curve (HCA-R interpretation)
    ax.fill_between(alphas, 0, hc, color="#ff7f0e", alpha=0.15, label="HCA-R = area / span")
    # Annotate HCA-R
    hcar = data["metrics"]["hcar_mw"]["point"]
    hcar_lo = data["metrics"]["hcar_mw"]["ci95_low"]
    hcar_hi = data["metrics"]["hcar_mw"]["ci95_high"]
    ax.axhline(hcar, color="#ff7f0e", linestyle="--", linewidth=1.5,
               label=f"HCA-R = {hcar:.3f} MW")
    ax.set_xlabel("α  (0 = Range B, 1 = Range A)")
    ax.set_ylabel("Hosting Capacity HC(α) [MW]")
    ax.set_title("(a) HC(α) curve across regulatory range")
    ax.legend(fontsize=8, loc="upper right")
    ax.grid(True, alpha=0.3)
    # Secondary x-axis showing theta_low
    def a2tl(a: float) -> float:
        return 0.90 + 0.05 * a
    sec = ax.secondary_xaxis("top", functions=(a2tl, lambda t: (t - 0.90) / 0.05))
    sec.set_xlabel("θ_low [pu]", fontsize=9)

    # (b) Comparison bar: HCA-R vs fixed-threshold HC
    ax = axes[0, 1]
    comp = data["comparison_to_fixed_threshold"]
    labels = ["HC\n(Range A)", "HC\n(Range B)", "HCA-R\n(proposed)"]
    keys = ["hc_range_a", "hc_range_b", "hcar"]
    colors = ["#d62728", "#2ca02c", "#ff7f0e"]
    points = [comp[k]["point"] for k in keys]
    los = [comp[k]["ci95_low"] for k in keys]
    his = [comp[k]["ci95_high"] for k in keys]
    errs_lo = [p - l for p, l in zip(points, los)]
    errs_hi = [h - p for p, h in zip(points, his)]
    x = list(range(len(labels)))
    ax.bar(x, points, color=colors, alpha=0.85, edgecolor="black", linewidth=0.5)
    ax.errorbar(x, points, yerr=[errs_lo, errs_hi], fmt="none",
                ecolor="black", capsize=5, linewidth=1.5)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("HC / HCA-R [MW]")
    ax.set_title("(b) Fixed-threshold vs threshold-robust metrics")
    ax.grid(True, axis="y", alpha=0.3)
    for i, (p, l, h) in enumerate(zip(points, los, his)):
        txt = f"{p:.3f}\n[{l:.3f}, {h:.3f}]"
        ax.text(i, p + errs_hi[i] + 0.03, txt, ha="center", va="bottom", fontsize=7)

    # (c) Convergence of HCA-R with sample size
    ax = axes[1, 0]
    conv = data["convergence"]
    ns = [c["n"] for c in conv]
    means = [c["hcar"] for c in conv]
    los = [c["hcar_ci95_low"] for c in conv]
    his = [c["hcar_ci95_high"] for c in conv]
    ax.plot(ns, means, "o-", color="#ff7f0e", linewidth=2, markersize=6, label="HCA-R")
    ax.fill_between(ns, los, his, color="#ff7f0e", alpha=0.2, label="95% CI")
    ax.set_xlabel("Monte Carlo sample size n")
    ax.set_ylabel("HCA-R [MW]")
    ax.set_title("(c) HCA-R convergence")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    ax.set_xscale("log")
    ax.set_xticks([100, 200, 500, 1000])
    ax.get_xaxis().set_major_formatter(plt.ScalarFormatter())

    # (d) Summary / interpretation
    ax = axes[1, 1]
    ax.axis("off")
    hcas = data["metrics"]["hcas_mw"]["point"]
    hcarr = data["metrics"]["hcarr"]["point"]
    text_lines = [
        "Proposed metrics (IEEE 13, n=1000):",
        "",
        f"  HCA-R  = {hcar:.3f} MW   [threshold-robust HC]",
        f"         95% CI [{hcar_lo:.3f}, {hcar_hi:.3f}]",
        "",
        f"  HCA-S  = {hcas:.3f} MW   [regulatory sensitivity]",
        f"         HC drops by {hcas:.3f} MW from",
        f"         Range B to Range A",
        "",
        f"  HCA-RR = {hcarr:.3f}     [robustness ratio]",
        f"         HC(Range A) / HC(Range B) = 0",
        f"         → IEEE 13 is NOT regulatorily robust",
        "",
        "Interpretation:",
        "  Fixed-threshold HC is ambiguous (0 to 0.98 MW",
        "  on same feeder). HCA-R collapses the regulatory",
        "  range to a single value usable for",
        "  standard-invariant feeder comparison.",
        "",
        "HCA-R properties:",
        "  • Bounded: 0 <= HCA-R <= max(HC)",
        "  • Reproducible: derived from any Monte Carlo HCA",
        "  • Comparable: same unit (MW) across studies",
    ]
    ax.text(0.02, 0.98, "\n".join(text_lines), family="monospace",
            fontsize=8, va="top", ha="left", transform=ax.transAxes)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = results_dir / "hcar_figure.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
