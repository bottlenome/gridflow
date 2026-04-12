#!/usr/bin/env python3
"""Plot stochastic HCA results from two SweepResult JSONs.

Generates a 4-panel figure:
    (a) hosting_capacity_mw bar chart per solver (max + mean)
    (b) voltage_deviation_mean per solver
    (c) violation rate (= fraction of zero hosting_capacity_mw experiments)
    (d) summary text panel
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opendss", type=Path, required=True)
    p.add_argument("--pandapower", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    a = _load(args.opendss)
    b = _load(args.pandapower)
    am = a.get("aggregated_metrics", {}) or {}
    bm = b.get("aggregated_metrics", {}) or {}

    solvers = ["OpenDSS\n(IEEE 13)", "pandapower\n(IEEE 30)"]
    hc_mean = [am.get("hosting_capacity_mw_mean", 0.0), bm.get("hosting_capacity_mw_mean", 0.0)]
    hc_max = [am.get("hosting_capacity_mw_max", 0.0), bm.get("hosting_capacity_mw_max", 0.0)]
    vd_mean = [am.get("voltage_deviation_mean", 0.0), bm.get("voltage_deviation_mean", 0.0)]
    vd_max = [am.get("voltage_deviation_max", 0.0), bm.get("voltage_deviation_max", 0.0)]
    runtime = [am.get("runtime_mean", 0.0), bm.get("runtime_mean", 0.0)]

    n_a = len(a.get("experiment_ids", []))
    n_b = len(b.get("experiment_ids", []))

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    fig.suptitle(
        "Stochastic HCA — gridflow MVP try 2 (OpenDSS vs pandapower)",
        fontsize=13,
    )

    ax = axes[0, 0]
    width = 0.35
    x_pos = list(range(len(solvers)))
    ax.bar([p - width / 2 for p in x_pos], hc_mean, width, label="mean", color="C0")
    ax.bar([p + width / 2 for p in x_pos], hc_max, width, label="max", color="C2")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(solvers)
    ax.set_ylabel("hosting_capacity_mw [MW]")
    ax.set_title("Custom metric: hosting_capacity_mw")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[0, 1]
    ax.bar([p - width / 2 for p in x_pos], vd_mean, width, label="mean", color="C1")
    ax.bar([p + width / 2 for p in x_pos], vd_max, width, label="max", color="C3")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(solvers)
    ax.set_ylabel("voltage_deviation [pu]")
    ax.set_title("Built-in metric: voltage_deviation (RMSE)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 0]
    ax.bar(x_pos, runtime, color="C4")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(solvers)
    ax.set_ylabel("runtime per experiment [s]")
    ax.set_title("Built-in metric: runtime_mean")
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 1]
    ax.axis("off")
    text_lines = [
        "Sweep summary",
        "",
        f"  OpenDSS    : {n_a} experiments, {a.get('elapsed_s', 0):.2f}s",
        f"  pandapower : {n_b} experiments, {b.get('elapsed_s', 0):.2f}s",
        "",
        "Cross-solver hosting capacity:",
        f"  OpenDSS  mean = {hc_mean[0]:.3f} MW   max = {hc_max[0]:.3f} MW",
        f"  pp       mean = {hc_mean[1]:.3f} MW   max = {hc_max[1]:.3f} MW",
        "",
        "Voltage deviation (RMSE pu):",
        f"  OpenDSS  mean = {vd_mean[0]:.4f}   max = {vd_max[0]:.4f}",
        f"  pp       mean = {vd_mean[1]:.4f}   max = {vd_max[1]:.4f}",
        "",
        "Plan hashes (provenance):",
        f"  OpenDSS    : {a.get('plan_hash')}",
        f"  pandapower : {b.get('plan_hash')}",
    ]
    ax.text(
        0.02,
        0.98,
        "\n".join(text_lines),
        family="monospace",
        fontsize=8.5,
        va="top",
        ha="left",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=120)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
