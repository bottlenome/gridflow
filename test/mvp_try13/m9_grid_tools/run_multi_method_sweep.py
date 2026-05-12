"""MS-3 + MS-4: 7-method comparison on synthetic + ACN multi-month/site.

Methods:
  M1   (try11)  — trigger-orth MILP
  M7   (try11)  — M1 + DistFlow grid-aware
  M9   (try12)  — M1 + Bayes-posterior expected-loss
  M9-grid (try13) — M1 + DistFlow + Bayes
  B1, B4, B5 (try11) — baselines

Datasets (--mode):
  synthetic: F-M2 traces × seeds × feeders (no ACN data)
  acn:       multi-month/site ACN at α=0.70

Usage:
  PYTHONPATH=src python -m m9_grid_tools.run_multi_method_sweep --mode acn \\
    --data-csv .../acn_caltech_2019_01.csv label=caltech-01 \\
                .../acn_caltech_2019_02.csv label=caltech-02 \\
                ...
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
for p in (_TRY11, _TRY12, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

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
from tools.trace_synthesizer import synth_c1_single_trigger  # noqa: E402
from tools.vpp_metrics import VPP_METRICS  # noqa: E402
from tools.vpp_simulator import all_standby_dispatch_policy  # noqa: E402

from m9_tools.sdp_bayes_robust import solve_sdp_bayes_robust  # noqa: E402

from m9_grid_tools.sdp_full import solve_sdp_full  # noqa: E402

METHODS = ("M1", "M7", "M9", "M9-grid", "B1", "B4", "B5")
ALPHA = 0.70


def _config(feeder, alpha=ALPHA):
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
        m9 = solve_sdp_bayes_robust(
            pool, active_ids, burst, basis=TRIGGER_BASIS_K3,
            epsilon=0.05, expected_loss_threshold_fraction=0.01, mode="M9",
        )
        return m9.standby_ids, m9.objective_cost, m9.feasible, "M9"
    if method == "M9-grid":
        m9g = solve_sdp_full(
            pool, active_ids, burst, bus_map, feeder, basis=TRIGGER_BASIS_K3,
            epsilon=0.05, expected_loss_threshold_fraction=0.01,
            v_max_pu=1.05, line_max_pct=100.0, mode="M9-grid",
        )
        return m9g.standby_ids, m9g.objective_cost, m9g.feasible, "M9-grid"
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
    (mode, feeder, method, dataset_label, sessions_csv, week, pairing, seed, alpha) = args
    started = time.perf_counter()
    try:
        config = _config(feeder, alpha)
        pool = make_default_pool(seed=0)
        bus_map = map_pool_to_feeder(pool, feeder)
        active_ids = feeder_active_pool(pool, config)

        if mode == "synthetic":
            trace = synth_c1_single_trigger(pool, seed=seed, sla_kw=config.sla_kw)
        else:  # acn
            trace = build_trace_from_acn_sessions(
                Path(sessions_csv), pool, sla_kw=config.sla_kw, seed=0,
                horizon_days=7, start_offset_days=week, pairing_seed=pairing,
                trace_id=f"{dataset_label}-w{week}-p{pairing}",
            )

        standby_ids, design_cost, feasible, label = _solve_one(
            method, pool, active_ids, config, bus_map, feeder, trace,
        )

        if not feasible:
            return {
                "mode": mode, "feeder": feeder, "method": method, "method_label": label,
                "dataset": dataset_label, "week": week, "pairing": pairing, "seed": seed,
                "alpha": alpha,
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
            experiment_id=f"try13_{label}_{feeder}_{dataset_label}_w{week}_p{pairing}",
            scenario_pack_id="try13", method_label=label,
        )
        metrics = dict(BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result).values)
        return {
            "mode": mode, "feeder": feeder, "method": method, "method_label": label,
            "dataset": dataset_label, "week": week, "pairing": pairing, "seed": seed,
            "alpha": alpha,
            "design_cost": design_cost, "n_standby": len(standby_ids), "infeasible": False,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "metrics": metrics, "error": None,
        }
    except Exception as e:
        return {"mode": mode, "feeder": feeder, "method": method, "dataset": dataset_label,
                "week": week, "pairing": pairing, "seed": seed,
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
    by_fm = defaultdict(list)
    for r in records:
        if r.get("error"):
            continue
        by_fm[(r["feeder"], r["method_label"])].append(r)
    rows = []
    for (f, m), bucket in sorted(by_fm.items()):
        feasible = [r for r in bucket if not r.get("infeasible")]
        sla = [r["metrics"].get("sla_violation_ratio", float("nan")) for r in feasible]
        sla = [v for v in sla if isinstance(v, (int, float)) and not math.isnan(v)]
        vd = [r["metrics"].get("voltage_violation_dispatch_induced", float("nan")) for r in feasible]
        vd = [v for v in vd if isinstance(v, (int, float)) and not math.isnan(v)]
        cost = [r["design_cost"] for r in feasible if isinstance(r["design_cost"], (int, float))]
        sla_m, sla_lo, sla_hi = _bootstrap_ci(sla)
        vd_m, vd_lo, vd_hi = _bootstrap_ci(vd)
        rows.append({
            "feeder": f, "method_label": m, "n_total": len(bucket), "n_feasible": len(feasible),
            "feasibility_rate": len(feasible) / len(bucket) if bucket else 0.0,
            "sla_v_mean": sla_m, "sla_v_ci_lo": sla_lo, "sla_v_ci_hi": sla_hi,
            "v_disp_mean": vd_m, "v_disp_ci_lo": vd_lo, "v_disp_ci_hi": vd_hi,
            "cost_mean": statistics.fmean(cost) if cost else float("nan"),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--mode", choices=("synthetic", "acn"), required=True)
    parser.add_argument("--feeders", nargs="+", default=list(FEEDER_TRAFO_MVA.keys()))
    parser.add_argument("--methods", nargs="+", default=list(METHODS))
    parser.add_argument("--alpha", type=float, default=ALPHA)
    parser.add_argument("--datasets", nargs="+", default=[],
                        help='for acn mode, list of "label=path" pairs')
    parser.add_argument("--weeks", type=int, nargs="+", default=[0, 7, 14, 21])
    parser.add_argument("--pairings", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    parser.add_argument("--out-tag", type=str, default="multi_method")
    args = parser.parse_args()

    cells = []
    if args.mode == "synthetic":
        for f in args.feeders:
            for m in args.methods:
                for s in args.seeds:
                    cells.append(("synthetic", f, m, "synthetic", "", 0, 0, s, args.alpha))
    else:  # acn
        if not args.datasets:
            raise SystemExit("--datasets required for --mode acn")
        for ds in args.datasets:
            label, path = ds.split("=", 1)
            for f in args.feeders:
                for m in args.methods:
                    for w in args.weeks:
                        for p in args.pairings:
                            cells.append(("acn", f, m, label, path, w, 7, p, args.alpha))

    n = len(cells)
    print(f"[try13 {args.mode}] cells={n} (α={args.alpha}) workers={args.n_workers}")

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
    print(f"[try13 {args.mode}] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / f"try13_{args.out_tag}_{args.mode}.json"
    out_csv = args.output / f"try13_{args.out_tag}_{args.mode}_summary.csv"

    out = {
        "records": records,
        "config": vars(args) | {"output": str(args.output)},
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
    h = f"{'feeder':<14}{'method':<12}{'feas/n':>8}{'SLA % [CI]':>20}{'V_disp % [CI]':>20}{'cost ¥':>10}"
    print(h); print("-" * len(h))
    for r in rows:
        def fmt(m, lo, hi):
            if isinstance(m, float) and m == m:
                return f"{m*100:.1f}[{lo*100:.1f},{hi*100:.1f}]"
            return "—"
        print(
            f"{r['feeder']:<14}{r['method_label']:<12}"
            f"{r['n_feasible']}/{r['n_total']:<5}"
            f"{fmt(r['sla_v_mean'], r['sla_v_ci_lo'], r['sla_v_ci_hi']):>20}"
            f"{fmt(r['v_disp_mean'], r['v_disp_ci_lo'], r['v_disp_ci_hi']):>20}"
            f"{r['cost_mean']:>10.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
