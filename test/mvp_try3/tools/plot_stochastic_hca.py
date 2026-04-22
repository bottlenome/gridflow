#!/usr/bin/env python3
"""Plot stochastic HCA results from two SweepResult JSONs.

Generates a 4-panel figure:
    (a) hosting_capacity_mw bar chart per network (max + mean)
    (b) voltage_deviation_mean per network
    (c) runtime per experiment
    (d) summary text panel

Change from try2: corrected network labels (MV ring 7-bus, not IEEE 30),
and title no longer mentions gridflow (§3.1 compliance).
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

    networks = ["OpenDSS\n(IEEE 13, 4.16 kV)", "pandapower\n(MV ring 7-bus, 20 kV)"]
    hc_mean = [am.get("hosting_capacity_mw_mean", 0.0), bm.get("hosting_capacity_mw_mean", 0.0)]
    hc_max = [am.get("hosting_capacity_mw_max", 0.0), bm.get("hosting_capacity_mw_max", 0.0)]
    vd_mean = [am.get("voltage_deviation_mean", 0.0), bm.get("voltage_deviation_mean", 0.0)]
    vd_max = [am.get("voltage_deviation_max", 0.0), bm.get("voltage_deviation_max", 0.0)]
    runtime = [am.get("runtime_mean", 0.0), bm.get("runtime_mean", 0.0)]

    n_a = len(a.get("experiment_ids", []))
    n_b = len(b.get("experiment_ids", []))

    fig, axes = plt.subplots(2, 2, figsize=(11, 7.5))
    fig.suptitle(
        "Stochastic HCA: Cross-topology Comparison\n"
        "(IEEE 13-node feeder vs MV open-ring 7-bus feeder)",
        fontsize=12,
    )

    ax = axes[0, 0]
    width = 0.35
    x_pos = list(range(len(networks)))
    ax.bar([p - width / 2 for p in x_pos], hc_mean, width, label="mean", color="C0")
    ax.bar([p + width / 2 for p in x_pos], hc_max, width, label="max", color="C2")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(networks, fontsize=8)
    ax.set_ylabel("hosting_capacity_mw [MW]")
    ax.set_title("(a) Stochastic hosting capacity")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[0, 1]
    ax.bar([p - width / 2 for p in x_pos], vd_mean, width, label="mean", color="C1")
    ax.bar([p + width / 2 for p in x_pos], vd_max, width, label="max", color="C3")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(networks, fontsize=8)
    ax.set_ylabel("voltage_deviation [pu]")
    ax.set_title("(b) Voltage deviation (RMSE vs 1.0 pu)")
    ax.legend()
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 0]
    ax.bar(x_pos, runtime, color="C4")
    ax.set_xticks(x_pos)
    ax.set_xticklabels(networks, fontsize=8)
    ax.set_ylabel("runtime per experiment [s]")
    ax.set_title("(c) Mean runtime per experiment")
    ax.grid(True, axis="y", alpha=0.3)

    ax = axes[1, 1]
    ax.axis("off")
    text_lines = [
        "Sweep summary",
        "",
        f"  OpenDSS (IEEE 13)  : {n_a} experiments, {a.get('elapsed_s', 0):.2f}s",
        f"  pandapower (MV ring): {n_b} experiments, {b.get('elapsed_s', 0):.2f}s",
        "",
        "Stochastic hosting capacity:",
        f"  IEEE 13    mean = {hc_mean[0]:.4f} MW   max = {hc_max[0]:.4f} MW",
        f"  MV ring    mean = {hc_mean[1]:.4f} MW   max = {hc_max[1]:.4f} MW",
        "",
        "Voltage deviation (RMSE pu vs 1.0):",
        f"  IEEE 13    mean = {vd_mean[0]:.4f}   max = {vd_max[0]:.4f}",
        f"  MV ring    mean = {vd_mean[1]:.4f}   max = {vd_max[1]:.4f}",
        "",
        "Plan hashes (provenance):",
        f"  OpenDSS    : {a.get('plan_hash')}",
        f"  pandapower : {b.get('plan_hash')}",
        "",
        "Note: hosting_capacity_mw_max identity is a",
        "shared-seed artifact (see report §2.4).",
    ]
    ax.text(
        0.02,
        0.98,
        "\n".join(text_lines),
        family="monospace",
        fontsize=8,
        va="top",
        ha="left",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.93))
    args.output.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(args.output, dpi=120)
    print(f"wrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
