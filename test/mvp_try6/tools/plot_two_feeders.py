#!/usr/bin/env python3
"""2-feeder HCA-R comparison figure."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    results_dir = Path(__file__).resolve().parent.parent / "results"
    with (results_dir / "two_feeder_hcar.json").open() as f:
        data = json.load(f)

    r13 = data["feeders"]["ieee13"]
    rmv = data["feeders"]["mv_ring"]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(
        "HCA-R: 2-Feeder Comparison\n"
        "IEEE 13-node (4.16 kV) vs MV open-ring 7-bus (20 kV)",
        fontsize=12,
    )

    # (a) HC(α) curves for both feeders
    ax = axes[0, 0]
    alphas = r13["alpha_grid"]
    ax.plot(alphas, r13["hc_curve"], "o-", color="#1f77b4", ms=4, lw=2,
            label=f"IEEE 13 (HCA-R={r13['hcar']:.3f})")
    ax.fill_between(alphas, r13["hc_curve_ci95_low"], r13["hc_curve_ci95_high"],
                     color="#1f77b4", alpha=0.15)
    ax.plot(alphas, rmv["hc_curve"], "s-", color="#d62728", ms=4, lw=2,
            label=f"MV ring (HCA-R={rmv['hcar']:.3f})")
    ax.fill_between(alphas, rmv["hc_curve_ci95_low"], rmv["hc_curve_ci95_high"],
                     color="#d62728", alpha=0.15)
    ax.set_xlabel("α  (0 = Range B, 1 = Range A)")
    ax.set_ylabel("HC(α) [MW]")
    ax.set_title("(a) HC(α) curves with 95% CI")
    ax.legend(fontsize=8)
    ax.grid(True, alpha=0.3)
    def a2tl(a: float) -> float:
        return 0.90 + 0.05 * a
    sec = ax.secondary_xaxis("top", functions=(a2tl, lambda t: (t - 0.90) / 0.05))
    sec.set_xlabel("θ_low [pu]", fontsize=9)

    # (b) Bar comparison: HC(Range A), HC(Range B), HCA-R
    ax = axes[0, 1]
    labels = ["HC\n(Range A)", "HC\n(Range B)", "HCA-R"]
    ieee_vals = [r13["hc_range_a"], r13["hc_range_b"], r13["hcar"]]
    mv_vals = [rmv["hc_range_a"], rmv["hc_range_b"], rmv["hcar"]]
    x = list(range(len(labels)))
    w = 0.35
    ax.bar([i - w/2 for i in x], ieee_vals, w, label="IEEE 13", color="#1f77b4", alpha=0.8)
    ax.bar([i + w/2 for i in x], mv_vals, w, label="MV ring", color="#d62728", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(labels)
    ax.set_ylabel("[MW]")
    ax.set_title("(b) Fixed-threshold vs HCA-R")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    # (c) HCA-RR / HCA-S comparison
    ax = axes[1, 0]
    metrics = ["HCA-R\n(MW)", "HCA-S\n(MW)", "HCA-RR"]
    ieee_m = [r13["hcar"], r13["hcas"], r13["hcarr"]]
    mv_m = [rmv["hcar"], rmv["hcas"], rmv["hcarr"]]
    x = list(range(len(metrics)))
    bars1 = ax.bar([i - w/2 for i in x], ieee_m, w, label="IEEE 13", color="#1f77b4", alpha=0.8)
    bars2 = ax.bar([i + w/2 for i in x], mv_m, w, label="MV ring", color="#d62728", alpha=0.8)
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylabel("Value")
    ax.set_title("(c) Proposed metric triplet comparison")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)
    for bar, val in zip(list(bars1) + list(bars2), ieee_m + mv_m):
        ax.text(bar.get_x() + bar.get_width()/2, bar.get_height() + 0.02,
                f"{val:.3f}", ha="center", va="bottom", fontsize=7)

    # (d) Interpretation summary
    ax = axes[1, 1]
    ax.axis("off")
    text = [
        "2-Feeder HCA-R Comparison (n=1000 each)",
        "",
        "                   IEEE 13     MV ring",
        "  ─────────────────────────────────────",
        f"  HC (Range A)     {r13['hc_range_a']:.3f} MW    {rmv['hc_range_a']:.3f} MW",
        f"  HC (Range B)     {r13['hc_range_b']:.3f} MW    {rmv['hc_range_b']:.3f} MW",
        f"  HCA-R            {r13['hcar']:.3f} MW    {rmv['hcar']:.3f} MW",
        f"  HCA-S            {r13['hcas']:.3f} MW    {rmv['hcas']:.3f} MW",
        f"  HCA-RR           {r13['hcarr']:.3f}        {rmv['hcarr']:.3f}",
        "",
        "Key finding:",
        "  Fixed HC(Range A) says IEEE 13 has zero HC",
        "  and MV ring has 1.04 MW.",
        "  Fixed HC(Range B) says both have ~1 MW.",
        "  → fixed-threshold HC gives contradictory",
        "     rankings depending on threshold choice.",
        "",
        "  HCA-R resolves this: IEEE 13 = 0.28 MW",
        "  (fragile), MV ring = 1.04 MW (robust).",
        "  The ranking is threshold-choice-invariant.",
    ]
    ax.text(0.02, 0.98, "\n".join(text), family="monospace",
            fontsize=7.5, va="top", ha="left", transform=ax.transAxes)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = results_dir / "two_feeder_hcar.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
