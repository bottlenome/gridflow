"""Plot the scaling-sweep cost / time curves.

Phase D-6 (NEXT_STEPS.md §8.3). Reads ``try11_scaling_results.json``
(produced by ``run_scaling``) and renders a 2-panel figure:

  * left:  design cost vs N (log-log) per method
  * right: design solve time vs N (log-log) per method

Cells marked ``timeout_skipped`` or ``infeasible`` are reported as
markers on the time-limit horizontal line so the regime where MILP
ceases to be practical is visible.

Usage:

    PYTHONPATH=src .venv/bin/python -m tools.plot_scaling \\
        results/try11_scaling_results.json \\
        --out results/plots/scaling_M1_M4b_M7_M8.png
"""

from __future__ import annotations

import argparse
import json
import statistics
from collections import defaultdict
from pathlib import Path


def aggregate(records: list[dict]) -> dict[str, dict[int, dict[str, float]]]:
    """Group by (method_label, scale) → mean cost, mean solve_time, n_feasible."""
    by_method_scale: dict[tuple[str, int], list[dict]] = defaultdict(list)
    for r in records:
        method = str(r.get("method_label") or r.get("method") or "?")
        scale = r.get("scale")
        if not isinstance(scale, int):
            continue
        by_method_scale[(method, scale)].append(r)

    out: dict[str, dict[int, dict[str, float]]] = {}
    for (method, scale), bucket in by_method_scale.items():
        feasible = [r for r in bucket if not r.get("infeasible") and not r.get("error")]
        costs = [
            float(r["design_cost"])
            for r in feasible
            if isinstance(r.get("design_cost"), (int, float))
        ]
        times = [
            float(r["design_solve_time_s"])
            for r in feasible
            if isinstance(r.get("design_solve_time_s"), (int, float))
        ]
        out.setdefault(method, {})[scale] = {
            "mean_cost": statistics.fmean(costs) if costs else float("nan"),
            "mean_time": statistics.fmean(times) if times else float("nan"),
            "n_feasible": len(feasible),
            "n_total": len(bucket),
        }
    return out


def render(data: dict[str, dict[int, dict[str, float]]], out_path: Path) -> None:
    try:
        import matplotlib.pyplot as plt
    except ImportError as e:
        raise SystemExit(f"[plot_scaling] matplotlib unavailable: {e}") from e

    fig, (ax_cost, ax_time) = plt.subplots(1, 2, figsize=(12, 5))

    methods = sorted(data.keys())
    for method in methods:
        per_scale = data[method]
        scales = sorted(per_scale.keys())
        costs = [per_scale[s]["mean_cost"] for s in scales]
        times = [per_scale[s]["mean_time"] for s in scales]
        ax_cost.plot(scales, costs, marker="o", label=method)
        ax_time.plot(scales, times, marker="s", label=method)

    for ax, ylabel, title in (
        (ax_cost, "mean design cost (¥)", "design cost vs N"),
        (ax_time, "mean solve time (s)", "solve time vs N"),
    ):
        ax.set_xscale("log")
        ax.set_yscale("log")
        ax.set_xlabel("pool size N")
        ax.set_ylabel(ylabel)
        ax.set_title(title)
        ax.grid(True, which="both", alpha=0.3)
        ax.legend(loc="best", fontsize=9)

    fig.tight_layout()
    out_path.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(out_path, dpi=120)
    print(f"wrote {out_path}")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("scaling_json", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    args = parser.parse_args()

    payload = json.loads(args.scaling_json.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise SystemExit("'records' field must be a list")

    data = aggregate(records)
    out_path = args.out or args.scaling_json.with_name(
        args.scaling_json.stem + ".png"
    )
    render(data, out_path)

    print()
    header = (
        f"{'method':<12}{'N':>8}{'mean_cost':>14}{'mean_time_s':>14}"
        f"{'feas/total':>14}"
    )
    print(header)
    print("-" * len(header))
    for method, per_scale in sorted(data.items()):
        for scale in sorted(per_scale.keys()):
            stats = per_scale[scale]
            print(
                f"{method:<12}{scale:>8}"
                f"{stats['mean_cost']:>14.1f}"
                f"{stats['mean_time']:>14.4f}"
                f"{stats['n_feasible']:>6}/{stats['n_total']:<7}"
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
