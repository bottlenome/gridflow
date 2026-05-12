"""Aggregate envelope sweep records into per-(feeder, α, β) summaries.

Phase D-4 (NEXT_STEPS.md §6) post-processor for ``run_envelope.py``.

For every (feeder, α, β) cell across ``n_traces × n_seeds`` records,
computes:

  * ``feasibility_rate``: feasible / total in [0, 1]
  * ``mean_voltage_dispatch_induced``: D-1 metric, feasible cells only
  * ``mean_sla_violation``: feasible cells only
  * ``mean_design_cost_per_kw_sla``: design ¥ ÷ sla_kw

Optionally renders a heatmap per feeder using matplotlib (``--plots``).

Usage:

    PYTHONPATH=src .venv/bin/python -m tools.aggregate_envelope \\
        results/try11_envelope_M8.json \\
        --out results/envelope_M8_summary.csv \\
        --plots results/plots/feasibility_envelope_M8
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import statistics
from collections import defaultdict
from pathlib import Path


def _safe_mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def aggregate(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Group by (feeder, α, β) and reduce to one summary row per cell."""
    groups: dict[tuple[str, float, float], list[dict[str, object]]] = defaultdict(list)
    for r in records:
        feeder = str(r.get("feeder", ""))
        alpha = float(r.get("alpha", 0.0))
        beta = float(r.get("beta", 0.0))
        groups[(feeder, alpha, beta)].append(r)

    rows: list[dict[str, object]] = []
    for (feeder, alpha, beta), bucket in sorted(groups.items()):
        n_total = len(bucket)
        n_errors = sum(1 for r in bucket if r.get("error"))
        n_infeasible = sum(1 for r in bucket if r.get("infeasible"))
        n_feasible = n_total - n_errors - n_infeasible

        sla_violations: list[float] = []
        v_dispatch_induced: list[float] = []
        v_baseline_only: list[float] = []
        cost_per_kw_sla: list[float] = []
        for r in bucket:
            if r.get("error") or r.get("infeasible"):
                continue
            metrics = r.get("metrics") or {}
            if not isinstance(metrics, dict):
                continue
            if (sla_v := metrics.get("sla_violation_ratio")) is not None:
                sla_violations.append(float(sla_v))
            if (vd := metrics.get("voltage_violation_dispatch_induced")) is not None:
                v_dispatch_induced.append(float(vd))
            if (vb := metrics.get("voltage_violation_baseline_only")) is not None:
                v_baseline_only.append(float(vb))
            cost = r.get("design_cost")
            sla_kw = r.get("sla_kw")
            if (
                isinstance(cost, (int, float))
                and isinstance(sla_kw, (int, float))
                and sla_kw > 0
            ):
                cost_per_kw_sla.append(float(cost) / float(sla_kw))

        rows.append(
            {
                "feeder": feeder,
                "alpha": alpha,
                "beta": beta,
                "n_total": n_total,
                "n_feasible": n_feasible,
                "n_infeasible": n_infeasible,
                "n_errors": n_errors,
                "feasibility_rate": (n_feasible / n_total) if n_total else 0.0,
                "mean_sla_violation": _safe_mean(sla_violations),
                "mean_voltage_dispatch_induced": _safe_mean(v_dispatch_induced),
                "mean_voltage_baseline_only": _safe_mean(v_baseline_only),
                "mean_cost_per_kw_sla": _safe_mean(cost_per_kw_sla),
            }
        )
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def render_heatmaps(
    rows: list[dict[str, object]],
    plot_prefix: Path,
) -> list[Path]:
    """Render one heatmap per feeder of feasibility_rate over (α, β).

    Returns the list of written PNG paths.
    """
    try:
        import matplotlib.pyplot as plt
        import numpy as np
    except ImportError as e:
        print(f"[aggregate_envelope] matplotlib unavailable, skipping plots: {e}")
        return []

    feeder_groups: dict[str, list[dict[str, object]]] = defaultdict(list)
    for r in rows:
        feeder_groups[str(r["feeder"])].append(r)

    plot_prefix.parent.mkdir(parents=True, exist_ok=True)
    written: list[Path] = []

    for feeder, group in feeder_groups.items():
        alphas = sorted({float(r["alpha"]) for r in group})
        betas = sorted({float(r["beta"]) for r in group})
        # Build the matrix; rows = α (descending so larger α at top), cols = β
        matrix = np.full((len(alphas), len(betas)), float("nan"))
        for r in group:
            i = alphas.index(float(r["alpha"]))
            j = betas.index(float(r["beta"]))
            value = r.get("feasibility_rate")
            if isinstance(value, (int, float)) and not math.isnan(float(value)):
                matrix[i, j] = float(value)

        fig, ax = plt.subplots(figsize=(2.0 + 1.0 * len(betas), 2.0 + 0.5 * len(alphas)))
        im = ax.imshow(
            matrix[::-1, :], aspect="auto", vmin=0.0, vmax=1.0, cmap="RdYlGn",
        )
        ax.set_xticks(range(len(betas)))
        ax.set_xticklabels([f"β={b:g}" for b in betas])
        ax.set_yticks(range(len(alphas)))
        ax.set_yticklabels([f"α={a:g}" for a in reversed(alphas)])
        ax.set_xlabel("burst level β")
        ax.set_ylabel("SLA scale α")
        ax.set_title(f"feasibility envelope — {feeder}")
        for i, alpha in enumerate(reversed(alphas)):
            for j, beta in enumerate(betas):
                v = matrix[len(alphas) - 1 - i, j]
                txt = "—" if math.isnan(v) else f"{v * 100:.0f}%"
                ax.text(j, i, txt, ha="center", va="center", color="black", fontsize=9)
        cbar = fig.colorbar(im, ax=ax)
        cbar.set_label("feasibility rate")
        fig.tight_layout()
        out_path = plot_prefix.with_name(f"{plot_prefix.name}_{feeder}.png")
        fig.savefig(out_path, dpi=120)
        plt.close(fig)
        written.append(out_path)

    return written


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("envelope_json", type=Path)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument(
        "--plots",
        type=Path,
        default=None,
        help="Path prefix for per-feeder heatmap PNGs (e.g. results/plots/env_M8)",
    )
    args = parser.parse_args()

    payload = json.loads(args.envelope_json.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("'records' field must be a list")

    rows = aggregate(records)
    out_path = args.out or args.envelope_json.with_name(
        args.envelope_json.stem + "_summary.csv"
    )
    write_csv(out_path, rows)
    print(f"wrote {len(rows)} rows to {out_path}")

    if args.plots is not None:
        written = render_heatmaps(rows, args.plots)
        for p in written:
            print(f"  heatmap → {p}")

    print()
    header = (
        f"{'feeder':<14}{'α':>6}{'β':>6}"
        f"{'feas/total':>14}{'sla_v':>10}{'V_disp':>10}{'¥/kW_SLA':>12}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        feas = f"{row['n_feasible']}/{row['n_total']}"
        print(
            f"{row['feeder']:<14}"
            f"{row['alpha']:>6.2f}{row['beta']:>6.2f}"
            f"{feas:>14}"
            f"{_fmt_pct(row['mean_sla_violation']):>10}"
            f"{_fmt_pct(row['mean_voltage_dispatch_induced']):>10}"
            f"{_fmt(row['mean_cost_per_kw_sla']):>12}"
        )
    return 0


def _fmt_pct(v: object) -> str:
    if isinstance(v, float) and not math.isnan(v):
        return f"{v * 100:.1f}%"
    return "—"


def _fmt(v: object) -> str:
    if isinstance(v, float) and not math.isnan(v):
        return f"{v:.1f}"
    return "—"


if __name__ == "__main__":
    raise SystemExit(main())
