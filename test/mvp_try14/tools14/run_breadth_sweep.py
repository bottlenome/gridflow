"""MS-4: Full-breadth sweep — 4 feeders × 2 phases × 8 methods × multi-week × CI.

  Feeders:  cigre_lv (LV 0.95 MVA), kerber_dorf (LV 0.40 MVA),
            kerber_landnetz (LV 0.16 MVA), cigre_mv (MV 50 MVA)
  Phases:   workplace (try13 ACN, default), residential (try14 phase-invert)
  Methods:  M1, M7, M9, M9-grid, M9-grid-soft, B1, B4, B5

Reuses try11's grid_simulator + try13's run_multi_method_sweep cell logic
with the additions (M9-grid-soft, cigre_mv, residential phase).
"""

from __future__ import annotations

import argparse
import csv
import json
import math
import multiprocessing as mp
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
_TRY12 = _HERE.parent.parent / "mvp_try12"
_TRY13 = _HERE.parent.parent / "mvp_try13"
for p in (_TRY11, _TRY12, _TRY13, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

# Register cigre_mv before any other try11 import that snapshots FEEDER_NAMES
from tools14 import feeders_mv  # noqa: F401, E402

from gridflow.adapter.benchmark.harness import BenchmarkHarness  # noqa: E402

from tools.baselines import (  # noqa: E402
    solve_b1_static_overprov,
    solve_b4_markowitz,
    solve_b5_financial_causal,
)
from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool  # noqa: E402
from tools.feeder_config import FEEDER_TRAFO_MVA, FeederVppConfig, feeder_active_pool  # noqa: E402
from tools.feeders import map_pool_to_feeder  # noqa: E402
from tools.grid_metrics import GRID_METRICS  # noqa: E402
from tools.grid_simulator import grid_simulate, to_grid_experiment_result  # noqa: E402
from tools.real_data_trace import build_trace_from_acn_sessions  # noqa: E402
from tools.sdp_grid_aware import solve_sdp_grid_aware  # noqa: E402
from tools.sdp_optimizer import solve_sdp_strict  # noqa: E402
from tools.vpp_metrics import VPP_METRICS  # noqa: E402
from tools.vpp_simulator import all_standby_dispatch_policy  # noqa: E402

from m9_tools.sdp_bayes_robust import solve_sdp_bayes_robust  # noqa: E402

from m9_grid_tools.sdp_full import solve_sdp_full  # noqa: E402

from tools14.real_data_residential import build_trace_from_acn_residential  # noqa: E402
from tools14.sdp_full_soft import solve_sdp_full_soft  # noqa: E402

DEFAULT_METHODS = ("M1", "M7", "M9", "M9-grid", "M9-grid-soft", "B1", "B4", "B5")
DEFAULT_FEEDERS = ("cigre_lv", "kerber_dorf", "kerber_landnetz", "cigre_mv")
DEFAULT_PHASES = ("workplace", "residential")
DEFAULT_WEEKS = (0, 7, 14, 21)
ALPHA_BY_FEEDER = {
    "cigre_lv": 0.50,         # try13 cigre_lv α=0.70 strict が infeasible だったので緩める
    "kerber_dorf": 0.70,
    "kerber_landnetz": 0.70,
    "cigre_mv": 0.30,         # MV scale (50 MVA × 0.30 = 15 MW SLA target)
}


def _config(feeder, alpha):
    trafo = FEEDER_TRAFO_MVA[feeder]
    sla_kw = round(trafo * 1000.0 * alpha)
    burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    return FeederVppConfig(feeder, float(sla_kw), burst, max(5, int(sla_kw * 0.70 / 7.0)))


def _solve_one(method, pool, active_ids, config, bus_map, feeder, trace):
    burst = config.burst_dict()
    if method == "M1":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M1"
    if method == "M7":
        sol = solve_sdp_grid_aware(
            pool, active_ids, burst, bus_map=bus_map, feeder_name=feeder,
            v_max_pu=1.05, line_max_pct=100.0, basis=TRIGGER_BASIS_K3, mode="M7-strict",
        )
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M7-strict"
    if method == "M9":
        sol = solve_sdp_bayes_robust(
            pool, active_ids, burst, basis=TRIGGER_BASIS_K3,
            epsilon=0.05, expected_loss_threshold_fraction=0.01, mode="M9",
        )
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M9"
    if method == "M9-grid":
        sol = solve_sdp_full(
            pool, active_ids, burst, bus_map, feeder, basis=TRIGGER_BASIS_K3,
            epsilon=0.05, expected_loss_threshold_fraction=0.01,
            v_max_pu=1.05, line_max_pct=100.0, mode="M9-grid",
        )
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M9-grid"
    if method == "M9-grid-soft":
        sol = solve_sdp_full_soft(
            pool, active_ids, burst, bus_map, feeder, basis=TRIGGER_BASIS_K3,
            epsilon=0.05, expected_loss_threshold_fraction=0.01,
            slack_lambda=1e6, v_max_pu=1.05, line_max_pct=100.0, mode="M9-grid-soft",
        )
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M9-grid-soft"
    if method == "B1":
        sol = solve_b1_static_overprov(pool, active_ids, overprov_factor=0.30)
        return sol.standby_ids, sol.objective_cost, sol.feasible, "B1"
    if method == "B4":
        sol = solve_b4_markowitz(pool, active_ids, trace, sla_target_kw=config.sla_kw)
        return sol.standby_ids, sol.objective_cost, sol.feasible, "B4"
    if method == "B5":
        sol = solve_b5_financial_causal(pool, active_ids, trace, sla_target_kw=config.sla_kw)
        return sol.standby_ids, sol.objective_cost, sol.feasible, "B5"
    raise ValueError(method)


def run_one_cell(args):
    (feeder, phase, method, sessions_csv, week, pairing) = args
    started = time.perf_counter()
    try:
        alpha = ALPHA_BY_FEEDER[feeder]
        config = _config(feeder, alpha)
        pool = make_default_pool(seed=0)
        bus_map = map_pool_to_feeder(pool, feeder)
        active_ids = feeder_active_pool(pool, config)

        if phase == "workplace":
            trace = build_trace_from_acn_sessions(
                Path(sessions_csv), pool, sla_kw=config.sla_kw, seed=0,
                horizon_days=7, start_offset_days=week, pairing_seed=pairing,
                trace_id=f"wp-w{week}-p{pairing}",
            )
        else:  # residential
            trace = build_trace_from_acn_residential(
                Path(sessions_csv), pool, sla_kw=config.sla_kw, seed=0,
                horizon_days=7, start_offset_days=week, pairing_seed=pairing,
                trace_id=f"res-w{week}-p{pairing}",
            )

        standby_ids, design_cost, feasible, label = _solve_one(
            method, pool, active_ids, config, bus_map, feeder, trace,
        )
        if not feasible:
            return {
                "feeder": feeder, "phase": phase, "method": method, "method_label": label,
                "week": week, "pairing": pairing, "alpha": alpha,
                "design_cost": None, "n_standby": 0, "infeasible": True,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "metrics": {}, "error": None,
            }

        run = grid_simulate(
            pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids), trace=trace, feeder_name=feeder,
            bus_map=bus_map, dispatch_policy=all_standby_dispatch_policy, sample_every=24,
        )
        result = to_grid_experiment_result(
            run, pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids), trace=trace,
            experiment_id=f"try14_{label}_{feeder}_{phase}_w{week}_p{pairing}",
            scenario_pack_id="try14", method_label=label,
        )
        metrics = dict(BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result).values)
        return {
            "feeder": feeder, "phase": phase, "method": method, "method_label": label,
            "week": week, "pairing": pairing, "alpha": alpha,
            "design_cost": design_cost, "n_standby": len(standby_ids), "infeasible": False,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "metrics": metrics, "error": None,
        }
    except Exception as e:
        return {"feeder": feeder, "phase": phase, "method": method,
                "week": week, "pairing": pairing,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "error": f"{type(e).__name__}: {e}", "metrics": {}}


def _bootstrap_ci(values, n_boot=2000, conf=0.95, seed=0):
    if not values:
        return float("nan"), float("nan"), float("nan")
    rng = random.Random(seed)
    n = len(values)
    means = sorted(
        statistics.fmean(values[rng.randrange(n)] for _ in range(n))
        for _ in range(n_boot)
    )
    return statistics.fmean(values), means[int((1-conf)/2*n_boot)], means[int((1+conf)/2*n_boot)-1]


def aggregate(records):
    by = defaultdict(list)
    for r in records:
        if r.get("error"):
            continue
        by[(r["feeder"], r["phase"], r["method_label"])].append(r)
    rows = []
    for (f, ph, m), bucket in sorted(by.items()):
        feasible = [r for r in bucket if not r.get("infeasible")]
        sla = [r["metrics"].get("sla_violation_ratio", float("nan")) for r in feasible]
        sla = [v for v in sla if isinstance(v, (int, float)) and not math.isnan(v)]
        vd = [r["metrics"].get("voltage_violation_dispatch_induced", float("nan")) for r in feasible]
        vd = [v for v in vd if isinstance(v, (int, float)) and not math.isnan(v)]
        cost = [r["design_cost"] for r in feasible if isinstance(r["design_cost"], (int, float))]
        sla_m, sla_lo, sla_hi = _bootstrap_ci(sla)
        vd_m, vd_lo, vd_hi = _bootstrap_ci(vd)
        rows.append({
            "feeder": f, "phase": ph, "method_label": m,
            "n_total": len(bucket), "n_feasible": len(feasible),
            "feasibility_rate": len(feasible) / len(bucket) if bucket else 0.0,
            "sla_v_mean": sla_m, "sla_v_ci_lo": sla_lo, "sla_v_ci_hi": sla_hi,
            "v_disp_mean": vd_m, "v_disp_ci_lo": vd_lo, "v_disp_ci_hi": vd_hi,
            "cost_mean": statistics.fmean(cost) if cost else float("nan"),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-csv", required=True, type=Path)
    parser.add_argument("--feeders", nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--phases", nargs="+", default=list(DEFAULT_PHASES))
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--weeks", type=int, nargs="+", default=list(DEFAULT_WEEKS))
    parser.add_argument("--pairings", type=int, nargs="+", default=[0])
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    args = parser.parse_args()

    cells = [
        (f, ph, m, str(args.sessions_csv), w, p)
        for f in args.feeders for ph in args.phases for m in args.methods
        for w in args.weeks for p in args.pairings
    ]
    n = len(cells)
    print(f"[try14 breadth] cells={n} workers={args.n_workers}")

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_cell, cells)):
                records.append(rec)
                if (i + 1) % 30 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    print(f"  [{i+1}/{n}] elapsed {elapsed:.0f}s")
    print(f"[try14 breadth] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / "try14_breadth.json"
    out_csv = args.output / "try14_breadth_summary.csv"

    out = {
        "records": records,
        "config": vars(args) | {"output": str(args.output), "alpha_by_feeder": ALPHA_BY_FEEDER},
        "elapsed_s": round(time.perf_counter() - started, 1),
        "n_cells": n,
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_infeasible": sum(1 for r in records if r.get("infeasible")),
    }
    out_json.write_text(json.dumps(out, indent=2, sort_keys=True, default=str), encoding="utf-8")

    rows = aggregate(records)
    if rows:
        with out_csv.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"Wrote {out_json}\nWrote {out_csv}")
    print()
    h = (f"{'feeder':<14}{'phase':<12}{'method':<14}{'feas/n':>8}"
         f"{'SLA % [CI]':>20}{'V_disp % [CI]':>20}{'cost ¥':>10}")
    print(h); print("-" * len(h))
    for r in rows:
        def fmt(m, lo, hi):
            if isinstance(m, float) and m == m:
                return f"{m*100:.1f}[{lo*100:.1f},{hi*100:.1f}]"
            return "—"
        feas = f"{r['n_feasible']}/{r['n_total']}"
        print(
            f"{r['feeder']:<14}{r['phase']:<12}{r['method_label']:<14}{feas:>8}"
            f"{fmt(r['sla_v_mean'], r['sla_v_ci_lo'], r['sla_v_ci_hi']):>20}"
            f"{fmt(r['v_disp_mean'], r['v_disp_ci_lo'], r['v_disp_ci_hi']):>20}"
            f"{r['cost_mean']:>10.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
