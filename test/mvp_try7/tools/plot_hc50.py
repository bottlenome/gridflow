#!/usr/bin/env python3
"""Publication figure: HC₅₀ dose-response characterization."""

from __future__ import annotations

import json
from pathlib import Path


def main() -> None:
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    import matplotlib.patches as mpatches

    results_dir = Path(__file__).resolve().parent.parent / "results"
    with (results_dir / "hc50_analysis.json").open() as f:
        data = json.load(f)

    r13 = data["ieee13"]
    rmv = data["mv_ring"]

    fig, axes = plt.subplots(2, 2, figsize=(11, 8.5))
    fig.suptitle(
        "HC₅₀: Dose-Response Characterization of Hosting Capacity\n"
        "(Inspired by IC₅₀ in pharmacology)",
        fontsize=12,
    )

    # (a) HC(θ) "dose-response" curves for both feeders
    ax = axes[0, 0]
    t13 = r13["theta_grid"]
    hc13 = r13["hc_curve_mw"]
    tmv = rmv["theta_grid"]
    hcmv = rmv["hc_curve_mw"]

    ax.plot(t13, hc13, "-", color="#1f77b4", lw=2, label="IEEE 13")
    ax.plot(tmv, hcmv, "-", color="#d62728", lw=2, label="MV ring")

    # HC₅₀ annotation for IEEE 13
    hc50_13 = r13["hc50_theta_pu"]
    hc_max_13 = r13["hc_max_mw"]
    ax.axhline(0.5 * hc_max_13, color="#1f77b4", ls=":", alpha=0.5, lw=1)
    ax.axvline(hc50_13, color="#1f77b4", ls="--", alpha=0.7, lw=1.5)
    ax.plot(hc50_13, 0.5 * hc_max_13, "o", color="#1f77b4", ms=8, zorder=5)
    ax.annotate(f"HC₅₀ = {hc50_13:.3f} pu",
                xy=(hc50_13, 0.5 * hc_max_13),
                xytext=(hc50_13 + 0.008, 0.5 * hc_max_13 + 0.15),
                fontsize=9, color="#1f77b4",
                arrowprops=dict(arrowstyle="->", color="#1f77b4"))

    # MV ring annotation
    ax.annotate("HC₅₀ > 0.950 pu\n(censored: robust)",
                xy=(0.950, rmv["hc_max_mw"]),
                xytext=(0.935, 0.6),
                fontsize=8, color="#d62728",
                arrowprops=dict(arrowstyle="->", color="#d62728"))

    # Range markers
    ax.axvspan(0.90, 0.90, color="green", alpha=0.3)
    ax.axvspan(0.95, 0.95, color="orange", alpha=0.3)
    ax.text(0.901, -0.05, "Range B\n(0.90)", fontsize=7, color="green", va="top")
    ax.text(0.946, -0.05, "Range A\n(0.95)", fontsize=7, color="orange", va="top")

    ax.set_xlabel("θ_low [pu]  (\"dose\" — regulatory stringency)")
    ax.set_ylabel("HC(θ) [MW]  (\"response\")")
    ax.set_title("(a) HC dose-response curves")
    ax.legend(fontsize=9)
    ax.grid(True, alpha=0.3)
    ax.set_xlim(0.895, 0.955)

    # (b) HC-width illustration (IEEE 13 zoom)
    ax = axes[0, 1]
    ax.plot(t13, [h / hc_max_13 for h in hc13], "-", color="#1f77b4", lw=2)
    ax.axhline(0.9, ls=":", color="gray", alpha=0.5)
    ax.axhline(0.5, ls=":", color="gray", alpha=0.5)
    ax.axhline(0.1, ls=":", color="gray", alpha=0.5)
    ax.text(0.896, 0.92, "90%", fontsize=8, color="gray")
    ax.text(0.896, 0.52, "50%", fontsize=8, color="gray")
    ax.text(0.896, 0.12, "10%", fontsize=8, color="gray")

    # Find θ(90%) and θ(10%) for illustration
    hc_w = r13["hc_width_pu"]
    if hc_w and hc50_13:
        # θ(90%) ≈ hc50 - width/2 (approx)
        from hc50_metric import _find_crossing
        t90 = _find_crossing(t13, hc13, 0.9 * hc_max_13)
        t10 = _find_crossing(t13, hc13, 0.1 * hc_max_13)
        if t90 and t10:
            ax.axvspan(t90, t10, color="#ff7f0e", alpha=0.2)
            ax.annotate(f"HC-width\n= {hc_w:.4f} pu",
                        xy=((t90 + t10) / 2, 0.5),
                        fontsize=9, ha="center", color="#ff7f0e",
                        fontweight="bold")

    ax.axvline(hc50_13, color="#1f77b4", ls="--", alpha=0.7, lw=1.5)
    ax.set_xlabel("θ_low [pu]")
    ax.set_ylabel("HC / HC_max (normalized)")
    ax.set_title("(b) IEEE 13: transition steepness")
    ax.set_xlim(0.900, 0.935)
    ax.grid(True, alpha=0.3)

    # (c) Metric comparison bar chart
    ax = axes[1, 0]
    metrics = ["HC\n(Range A)", "HC\n(Range B)", "HCA-R", "HC₅₀\n(pu×10)"]
    ieee_vals = [r13["hc_range_a_mw"], r13["hc_range_b_mw"], r13["hcar_mw"],
                 hc50_13 * 10 if hc50_13 else 0]
    mv_vals = [rmv["hc_range_a_mw"], rmv["hc_range_b_mw"], rmv["hcar_mw"],
               9.5]  # >0.95 → 9.5 for display
    w = 0.35
    x = list(range(len(metrics)))
    ax.bar([i - w / 2 for i in x], ieee_vals, w, label="IEEE 13", color="#1f77b4", alpha=0.8)
    bars_mv = ax.bar([i + w / 2 for i in x], mv_vals, w, label="MV ring", color="#d62728", alpha=0.8)
    # Mark HC₅₀ bar for MV ring as censored
    bars_mv[3].set_hatch("//")
    ax.set_xticks(x)
    ax.set_xticklabels(metrics)
    ax.set_ylabel("Value")
    ax.set_title("(c) Metric comparison (HC₅₀ scaled ×10 for visibility)")
    ax.legend(fontsize=8)
    ax.grid(True, axis="y", alpha=0.3)

    # (d) Summary
    ax = axes[1, 1]
    ax.axis("off")
    text = [
        "HC₅₀ Comparison (n=1000 per feeder)",
        "",
        "                  IEEE 13    MV ring",
        " ─────────────────────────────────────",
        f" HC_max           {r13['hc_max_mw']:.3f} MW   {rmv['hc_max_mw']:.3f} MW",
        f" HC₅₀             {hc50_13:.3f} pu   > 0.950 pu",
    ]
    if r13["hc50_ci95"]:
        text.append(f"   CI95           [{r13['hc50_ci95'][0]:.3f}, {r13['hc50_ci95'][1]:.3f}]   (censored)")
    if hc_w:
        text.append(f" HC-width         {hc_w:.4f} pu   N/A")
    text += [
        "",
        "Interpretation:",
        f" IEEE 13: tightening θ_low by just",
        f"   {hc50_13 - 0.90:.3f} pu from Range B causes 50%",
        f"   HC loss. Transition is cliff-like",
        f"   (width = {hc_w:.4f} pu).",
        "",
        " MV ring: HC₅₀ beyond Range A → the",
        "   feeder is inherently robust to any",
        "   threshold choice within ANSI range.",
        "",
        "IC₅₀ analogy (pharmacology):",
        " HC₅₀ = threshold \"dose\" for 50% HC loss",
        " HC-width = \"steepness\" of the response",
    ]
    ax.text(0.02, 0.98, "\n".join(text), family="monospace",
            fontsize=7.5, va="top", ha="left", transform=ax.transAxes)

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    out = results_dir / "hc50_figure.png"
    fig.savefig(out, dpi=150)
    print(f"wrote {out}")


if __name__ == "__main__":
    main()
