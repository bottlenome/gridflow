"""Multi-method validation sweep on real Caltech ACN-Data EV trace.

Phase D-5 v2 entry point. Reviewer M-1 / M-2 fix: where the v1
"validation" was 1 cell × 1 method × CAISO-system-load proxy on a
trivial operating point (= 0% achievable by any controller), this
sweep:

  * uses **real per-EV availability** (Caltech ACN-Data) as the active
    pool's churn signal — no semantic gap to the trigger-orthogonal
    framework
  * compares **multiple controllers** (M1 / M7-strict / B1 / B4) on
    the same real-DER trace
  * runs at a **harder operating point** (α=0.7) so that controllers
    actually differentiate (α=0.5 saturates baseline trafo and any
    controller clears it)
  * reports **mean ± 95% bootstrap CI** across 3 seeds × multiple
    feeders so the headline isn't sample-of-1

Default: 3 feeders × 4 methods × 3 seeds = 36 cells, ~5–10 min total.
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import random
import statistics
import time
from collections import defaultdict
from dataclasses import replace
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from .der_pool import make_default_pool
from .feeder_config import FEEDER_TRAFO_MVA, FeederVppConfig
from .feeders import map_pool_to_feeder
from .grid_metrics import GRID_METRICS
from .grid_simulator import grid_simulate, to_grid_experiment_result
from .real_data_trace import build_trace_from_acn_sessions, trace_summary
from .run_phase1_multifeeder import _solve
from .vpp_metrics import VPP_METRICS

DEFAULT_FEEDERS: tuple[str, ...] = tuple(FEEDER_TRAFO_MVA.keys())
DEFAULT_METHODS: tuple[str, ...] = ("M1", "M7", "B1", "B4")
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)
HARDER_ALPHA: float = 0.70  # 70% of trafo MVA — pushes controllers to differentiate


def _config_at_alpha(feeder: str, alpha: float) -> FeederVppConfig:
    """Build a FeederVppConfig at a custom α (= SLA / trafo) ratio."""
    trafo_mva = FEEDER_TRAFO_MVA[feeder]
    sla_kw = round(trafo_mva * 1000.0 * alpha)
    burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))
    return FeederVppConfig(
        feeder_name=feeder, sla_kw=float(sla_kw),
        burst_kw=burst, n_active_ev=n_active_ev,
    )


def run_one_acn_cell(args: tuple) -> dict:
    """Single (feeder, method, seed) cell driven by the ACN real trace."""
    feeder, method, seed, sessions_csv, alpha = args
    started = time.perf_counter()
    try:
        config = _config_at_alpha(feeder, alpha)
        sla_kw = config.sla_kw
        burst = config.burst_dict()

        pool = make_default_pool(seed=0)
        bus_map = map_pool_to_feeder(pool, feeder)

        # Active pool is the residential_ev subset (real ACN trace will drive it)
        from .feeder_config import feeder_active_pool
        active_ids = feeder_active_pool(pool, config)

        # Build the real-DER trace; seed perturbs the (synthetic) sweep over
        # the non-EV slice and the active-matrix-derived event timing only.
        trace = build_trace_from_acn_sessions(
            Path(sessions_csv), pool, sla_kw=sla_kw, seed=seed,
            trace_id=f"REAL-acn-{seed}",
        )

        design_t0 = time.perf_counter()
        standby_ids, design_cost, method_label, dispatch_policy, extras = _solve(
            method, pool, active_ids, trace,
            burst=burst, sla_kw=sla_kw, seed=seed,
            bus_map=bus_map, feeder_name=feeder,
        )
        design_solve_time = time.perf_counter() - design_t0
        feasible = bool(extras.get("feasible", True))
        infeasibility_reason = extras.get("infeasibility_reason")
        active_ids_for_sim = extras.get("active_ids_override", active_ids)

        if not feasible:
            elapsed = time.perf_counter() - started
            return {
                "feeder": feeder, "method": method, "method_label": method_label,
                "seed": seed, "alpha": alpha, "sla_kw": sla_kw,
                "design_cost": None, "n_standby": 0,
                "design_solve_time_s": round(design_solve_time, 3),
                "elapsed_s": round(elapsed, 3),
                "infeasible": True,
                "infeasibility_reason": infeasibility_reason or "design infeasible",
                "metrics": {}, "error": None,
            }

        # M7 default in run_phase1_multifeeder._solve uses V_max=1.05 strict;
        # mode label distinguishes M7 from M7-soft for the CSV.
        run = grid_simulate(
            pool=pool, active_ids=active_ids_for_sim,
            standby_ids=frozenset(standby_ids),
            trace=trace, feeder_name=feeder, bus_map=bus_map,
            dispatch_policy=dispatch_policy,
            sample_every=24,
        )
        result = to_grid_experiment_result(
            run, pool=pool, active_ids=active_ids_for_sim,
            standby_ids=frozenset(standby_ids), trace=trace,
            experiment_id=f"acn_{method}_{feeder}_a{alpha:.2f}_s{seed}",
            scenario_pack_id="try11_acn_real",
            method_label=method_label,
        )
        summary = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result)
        metrics = dict(summary.values)

        elapsed = time.perf_counter() - started
        return {
            "feeder": feeder, "method": method, "method_label": method_label,
            "seed": seed, "alpha": alpha, "sla_kw": sla_kw,
            "design_cost": design_cost, "n_standby": len(standby_ids),
            "design_solve_time_s": round(design_solve_time, 3),
            "elapsed_s": round(elapsed, 3),
            "infeasible": False, "infeasibility_reason": None,
            "metrics": metrics, "error": None,
        }
    except Exception as e:
        elapsed = time.perf_counter() - started
        return {
            "feeder": feeder, "method": method, "seed": seed,
            "alpha": alpha, "elapsed_s": round(elapsed, 3),
            "error": f"{type(e).__name__}: {e}", "metrics": {},
        }


def _bootstrap_ci(values: list[float], n_boot: int = 2000, conf: float = 0.95,
                  seed: int = 0) -> tuple[float, float, float]:
    """Return (mean, ci_low, ci_high) using a percentile bootstrap."""
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    means = []
    for _ in range(n_boot):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    lo_idx = int((1 - conf) / 2 * n_boot)
    hi_idx = int((1 + conf) / 2 * n_boot) - 1
    return statistics.fmean(values), means[lo_idx], means[hi_idx]


def aggregate(records: list[dict]) -> list[dict]:
    """Per-(feeder, method) summary with bootstrap CIs."""
    METRICS_OF_INTEREST = (
        "sla_violation_ratio",
        "voltage_violation_ratio",
        "voltage_violation_baseline_only",
        "voltage_violation_dispatch_induced",
        "max_voltage_pu",
        "min_voltage_pu",
        "line_overload_ratio",
    )
    groups: dict[tuple[str, str], list[dict]] = defaultdict(list)
    for r in records:
        groups[(r.get("feeder", ""), r.get("method_label", r.get("method", "")))].append(r)
    rows: list[dict] = []
    for (feeder, label), bucket in sorted(groups.items()):
        feasible = [r for r in bucket if not r.get("infeasible") and not r.get("error")]
        row: dict = {
            "feeder": feeder, "method_label": label,
            "n_records": len(bucket), "n_feasible": len(feasible),
            "n_infeasible": sum(1 for r in bucket if r.get("infeasible")),
        }
        for metric in METRICS_OF_INTEREST:
            values = [
                float(r["metrics"][metric])
                for r in feasible
                if isinstance(r.get("metrics", {}).get(metric), (int, float))
                and not math.isnan(float(r["metrics"][metric]))
            ]
            mean, lo, hi = _bootstrap_ci(values)
            row[f"{metric}_mean"] = mean
            row[f"{metric}_ci_lo"] = lo
            row[f"{metric}_ci_hi"] = hi
        # Cost (just mean ± std for simplicity)
        costs = [
            float(r["design_cost"]) for r in feasible
            if isinstance(r.get("design_cost"), (int, float))
        ]
        row["design_cost_mean"] = statistics.fmean(costs) if costs else float("nan")
        row["design_cost_std"] = statistics.pstdev(costs) if len(costs) > 1 else 0.0
        rows.append(row)
    return rows


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-csv", required=True, type=Path,
                        help="ACN sessions CSV (from tools/fetch_acn)")
    parser.add_argument("--feeders", nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--alpha", type=float, default=HARDER_ALPHA,
                        help=f"SLA/trafo ratio (default {HARDER_ALPHA})")
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=None)
    args = parser.parse_args()

    sessions_csv = args.sessions_csv
    if not sessions_csv.exists():
        raise SystemExit(f"sessions CSV not found: {sessions_csv}")

    cells: list[tuple] = [
        (f, m, s, str(sessions_csv), args.alpha)
        for f in args.feeders for m in args.methods for s in args.seeds
    ]
    n = len(cells)
    print(
        f"[acn-real-validation] cells={n} (α={args.alpha}) workers={args.n_workers}"
    )

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_acn_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_acn_cell, cells)):
                records.append(rec)
                if (i + 1) % 5 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    print(f"  [{i + 1}/{n}] elapsed {elapsed:.0f}s")
    total = time.perf_counter() - started

    output_dir = args.output or (
        Path(__file__).resolve().parent.parent / "results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / "try11_acn_real_results.json"
    out_csv = output_dir / "acn_real_summary.csv"

    out = {
        "records": records,
        "config": {
            "feeders": args.feeders, "methods": args.methods,
            "seeds": args.seeds, "alpha": args.alpha,
            "sessions_csv": str(sessions_csv),
        },
        "elapsed_s": round(total, 1),
        "n_cells": n,
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_infeasible": sum(1 for r in records if r.get("infeasible")),
    }
    out_json.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    rows = aggregate(records)
    if rows:
        fields = list(rows[0].keys())
        with out_csv.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=fields)
            w.writeheader()
            w.writerows(rows)
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")

    # Console preview
    print()
    header = (
        f"{'feeder':<14}{'method':<14}{'feas/total':>12}"
        f"{'sla_v %':>12}{'V_disp_ind %':>16}{'cost ¥':>12}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        feas = f"{row['n_feasible']}/{row['n_records']}"
        sla_m = row.get("sla_violation_ratio_mean")
        sla_lo = row.get("sla_violation_ratio_ci_lo")
        sla_hi = row.get("sla_violation_ratio_ci_hi")
        vd_m = row.get("voltage_violation_dispatch_induced_mean")
        vd_lo = row.get("voltage_violation_dispatch_induced_ci_lo")
        vd_hi = row.get("voltage_violation_dispatch_induced_ci_hi")
        cost = row.get("design_cost_mean")
        sla_s = (
            f"{sla_m * 100:.2f}[{sla_lo * 100:.2f},{sla_hi * 100:.2f}]"
            if isinstance(sla_m, float) and not math.isnan(sla_m) else "—"
        )
        vd_s = (
            f"{vd_m * 100:.2f}[{vd_lo * 100:.2f},{vd_hi * 100:.2f}]"
            if isinstance(vd_m, float) and not math.isnan(vd_m) else "—"
        )
        cost_s = f"{cost:.0f}" if isinstance(cost, float) and not math.isnan(cost) else "—"
        print(
            f"{row['feeder']:<14}{row['method_label']:<14}{feas:>12}"
            f"{sla_s:>12}{vd_s:>16}{cost_s:>12}"
        )
    return 0


# Reference replace so dataclasses replace stays imported
_ = replace


if __name__ == "__main__":
    raise SystemExit(main())
