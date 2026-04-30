"""Generate matplotlib figures for the F-M2 paper revision (MS-A8).

Spec: implementation_plan.md F-M2 / MS-A8.

Reads ``results/try11_FM2_results.json`` and produces 5 figures into
``results/plots/``:
  1. ``pareto_cost_violation.png`` — cost vs SLA violation, all methods
     × all traces, per feeder
  2. ``per_trace_violation_box.png`` — method × trace SLA violation
     box plots
  3. ``ood_gap_bar.png`` — OOD gap (test - train) per method, averaged
     over traces
  4. ``voltage_violation_per_feeder.png`` — voltage violation ratio
     per method per feeder
  5. ``c7_c8_dominance_bar.png`` — SDP vs baselines on the
     differentiation traces C7 / C8

All figures use deterministic seaborn-style aesthetics. The script does
NOT install seaborn (matplotlib only).
"""

from __future__ import annotations

import json
import statistics
from pathlib import Path

import matplotlib.pyplot as plt
import numpy as np


# Method colour palette (deterministic)
METHOD_COLORS: dict[str, str] = {
    "M1":  "#2E86AB", "M2a": "#3D7EA6", "M2b": "#2E86AB", "M2c": "#1F567D",
    "M3b": "#A23B72", "M3c": "#7A1F4F", "M4b": "#F18F01", "M5":  "#9C28B8",
    "M6":  "#0B5394",
    "B1":  "#C73E1D", "B2":  "#888888", "B3":  "#666666", "B4":  "#888888",
    "B5":  "#FF6B35", "B6":  "#444444",
}
METHOD_ORDER: tuple[str, ...] = (
    "M1", "M2a", "M2b", "M2c", "M3b", "M3c", "M4b", "M5", "M6",
    "B1", "B2", "B3", "B4", "B5", "B6",
)


def _load(path: Path) -> list[dict]:
    data = json.loads(path.read_text(encoding="utf-8"))
    return [r for r in data["records"] if not r.get("error")]


def fig1_pareto(records: list[dict], out_dir: Path) -> Path:
    """Cost vs SLA violation — Pareto frontier per feeder."""
    feeders = sorted({r["feeder"] for r in records})
    fig, axes = plt.subplots(1, len(feeders), figsize=(5 * len(feeders), 5),
                              squeeze=False)
    for ax, feeder in zip(axes[0], feeders):
        for method in METHOD_ORDER:
            xs, ys = [], []
            for r in records:
                if r["feeder"] != feeder or r["method"] != method:
                    continue
                m = r.get("metrics", {})
                xs.append(r["design_cost"])
                ys.append(m.get("sla_violation_ratio", 0) * 100)
            if not xs:
                continue
            ax.scatter(xs, ys,
                        color=METHOD_COLORS.get(method, "#888"),
                        s=40 if method.startswith("M") else 25,
                        marker="o" if method.startswith("M") else "x",
                        label=method, alpha=0.7)
        ax.set_xlabel("Design cost (¥/month)")
        ax.set_ylabel("SLA violation ratio (%)")
        ax.set_title(f"Pareto: cost vs violation [{feeder}]")
        ax.set_yscale("symlog", linthresh=0.1)
        ax.grid(alpha=0.3)
        if ax is axes[0][0]:
            ax.legend(loc="upper right", fontsize=7, ncol=2)
    fig.tight_layout()
    out = out_dir / "pareto_cost_violation.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def fig2_per_trace_box(records: list[dict], out_dir: Path) -> Path:
    """Method × trace SLA violation box plot (single feeder = aggregated)."""
    traces = sorted({r["trace_id"] for r in records})
    methods = METHOD_ORDER
    data: dict[tuple[str, str], list[float]] = {}
    for r in records:
        m = r.get("metrics", {})
        key = (r["method"], r["trace_id"])
        data.setdefault(key, []).append(m.get("sla_violation_ratio", 0) * 100)

    fig, ax = plt.subplots(figsize=(15, 6))
    width = 0.06
    x_base = np.arange(len(traces))
    for j, method in enumerate(methods):
        ys = [statistics.fmean(data.get((method, t), [0])) for t in traces]
        offset = (j - len(methods) / 2) * width
        ax.bar(x_base + offset, ys, width=width,
               color=METHOD_COLORS.get(method, "#888"),
               label=method, alpha=0.85)
    ax.set_xticks(x_base)
    ax.set_xticklabels(traces)
    ax.set_xlabel("Trace")
    ax.set_ylabel("SLA violation ratio (%)")
    ax.set_title("SLA violation by method × trace (mean over feeders × seeds)")
    ax.set_yscale("symlog", linthresh=0.1)
    ax.legend(ncol=8, fontsize=7, loc="upper center", bbox_to_anchor=(0.5, -0.10))
    ax.grid(alpha=0.3)
    fig.tight_layout()
    out = out_dir / "per_trace_violation_bar.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def fig3_ood_gap(records: list[dict], out_dir: Path) -> Path:
    """OOD gap per method, averaged over feeders × traces."""
    by_method: dict[str, list[float]] = {}
    for r in records:
        m = r.get("metrics", {})
        by_method.setdefault(r["method"], []).append(m.get("ood_gap", 0) * 100)

    methods = [m for m in METHOD_ORDER if m in by_method]
    means = [statistics.fmean(by_method[m]) for m in methods]
    fig, ax = plt.subplots(figsize=(10, 5))
    bars = ax.bar(methods, means,
                  color=[METHOD_COLORS.get(m, "#888") for m in methods])
    ax.axhline(0, color="black", linewidth=0.5)
    ax.set_ylabel("OOD gap (test - train) [%]")
    ax.set_title("Out-of-distribution gap per method (mean over feeders × traces)")
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = out_dir / "ood_gap_bar.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def fig4_voltage_per_feeder(records: list[dict], out_dir: Path) -> Path:
    """Voltage violation ratio per method per feeder."""
    feeders = sorted({r["feeder"] for r in records})
    methods = METHOD_ORDER
    data: dict[tuple[str, str], list[float]] = {}
    for r in records:
        m = r.get("metrics", {})
        key = (r["method"], r["feeder"])
        data.setdefault(key, []).append(m.get("voltage_violation_ratio", 0) * 100)

    fig, ax = plt.subplots(figsize=(15, 6))
    width = 0.25
    x_base = np.arange(len(methods))
    for j, feeder in enumerate(feeders):
        ys = [statistics.fmean(data.get((m, feeder), [0])) for m in methods]
        offset = (j - len(feeders) / 2) * width
        ax.bar(x_base + offset, ys, width=width,
               label=feeder, alpha=0.85)
    ax.set_xticks(x_base)
    ax.set_xticklabels(methods)
    ax.set_xlabel("Method")
    ax.set_ylabel("Voltage violation ratio (%)")
    ax.set_title("Voltage violation per method × feeder")
    ax.legend()
    ax.grid(alpha=0.3, axis="y")
    fig.tight_layout()
    out = out_dir / "voltage_violation_per_feeder.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def fig5_c7_c8_dominance(records: list[dict], out_dir: Path) -> Path:
    """SDP vs baselines on differentiation traces C7 / C8."""
    targets = ("C7", "C8")
    methods = METHOD_ORDER
    data: dict[tuple[str, str], list[float]] = {}
    for r in records:
        m = r.get("metrics", {})
        if r["trace_id"] not in targets:
            continue
        key = (r["method"], r["trace_id"])
        data.setdefault(key, []).append(m.get("sla_violation_ratio", 0) * 100)

    fig, axes = plt.subplots(1, 2, figsize=(14, 5))
    for ax, t in zip(axes, targets):
        ys = [statistics.fmean(data.get((m, t), [0])) for m in methods]
        bars = ax.bar(methods, ys,
                      color=[METHOD_COLORS.get(m, "#888") for m in methods])
        ax.set_ylabel("SLA violation (%)")
        ax.set_title(f"Trace {t}: SDP vs baselines (mean violation, all feeders)")
        ax.grid(alpha=0.3, axis="y")
        ax.set_yscale("symlog", linthresh=0.1)
    fig.tight_layout()
    out = out_dir / "c7_c8_dominance_bar.png"
    fig.savefig(out, dpi=120)
    plt.close(fig)
    return out


def main(results_path: Path | None = None, out_dir: Path | None = None) -> int:
    results_path = results_path or (
        Path(__file__).resolve().parent.parent / "results" / "try11_FM2_results.json"
    )
    out_dir = out_dir or results_path.parent / "plots"
    out_dir.mkdir(parents=True, exist_ok=True)
    records = _load(results_path)
    print(f"loaded {len(records)} records from {results_path}")

    paths = [
        fig1_pareto(records, out_dir),
        fig2_per_trace_box(records, out_dir),
        fig3_ood_gap(records, out_dir),
        fig4_voltage_per_feeder(records, out_dir),
        fig5_c7_c8_dominance(records, out_dir),
    ]
    for p in paths:
        print(f"  wrote {p}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
