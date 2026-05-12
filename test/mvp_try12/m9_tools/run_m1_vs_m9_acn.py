"""MS-4: M1 vs M9 on real ACN per-EV trace, multi-week × multi-pairing.

Reuses try11's ACN fixture (data/acn_caltech_sessions_2019_01.csv) and
trace builder (build_trace_from_acn_sessions). 3 feeders × 2 methods ×
4 weeks × 3 pairings = 72 cells. α=0.70 (= harder operating point that
exposes try11's MILP selection bias).
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
for p in (_TRY11, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from gridflow.adapter.benchmark.harness import BenchmarkHarness  # noqa: E402

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool  # noqa: E402
from tools.feeder_config import FEEDER_TRAFO_MVA, FeederVppConfig, feeder_active_pool  # noqa: E402
from tools.feeders import map_pool_to_feeder  # noqa: E402
from tools.grid_metrics import GRID_METRICS  # noqa: E402
from tools.grid_simulator import grid_simulate, to_grid_experiment_result  # noqa: E402
from tools.real_data_trace import build_trace_from_acn_sessions  # noqa: E402
from tools.sdp_optimizer import solve_sdp_strict  # noqa: E402
from tools.vpp_metrics import VPP_METRICS  # noqa: E402
from tools.vpp_simulator import all_standby_dispatch_policy  # noqa: E402

from m9_tools.sdp_bayes_robust import solve_sdp_bayes_robust  # noqa: E402

DEFAULT_FEEDERS = tuple(FEEDER_TRAFO_MVA.keys())
DEFAULT_METHODS = ("M1", "M9")
DEFAULT_WEEK_OFFSETS = (0, 7, 14, 21)
DEFAULT_PAIRING_SEEDS = (0, 1, 2)
DEFAULT_THETA_FRACTION = 0.05
HARDER_ALPHA = 0.70


def _config_at_alpha(feeder, alpha):
    trafo_mva = FEEDER_TRAFO_MVA[feeder]
    sla_kw = round(trafo_mva * 1000.0 * alpha)
    burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))
    return FeederVppConfig(feeder, float(sla_kw), burst, n_active_ev)


def run_one_cell(args):
    (feeder, method, sessions_csv, alpha, week, window, pairing) = args
    started = time.perf_counter()
    try:
        config = _config_at_alpha(feeder, alpha)
        burst = config.burst_dict()
        pool = make_default_pool(seed=0)
        bus_map = map_pool_to_feeder(pool, feeder)
        active_ids = feeder_active_pool(pool, config)

        trace = build_trace_from_acn_sessions(
            Path(sessions_csv), pool, sla_kw=config.sla_kw, seed=0,
            horizon_days=window, start_offset_days=week, pairing_seed=pairing,
            trace_id=f"REAL-acn-w{week}-p{pairing}",
        )

        if method == "M1":
            sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
            standby_ids, design_cost, feasible = sol.standby_ids, sol.objective_cost, sol.feasible
            method_label = "M1"
            extras = {}
        elif method == "M9":
            m9 = solve_sdp_bayes_robust(
                pool, active_ids, burst,
                basis=TRIGGER_BASIS_K3, epsilon=0.05,
                expected_loss_threshold_fraction=DEFAULT_THETA_FRACTION,
                mode="M9-bayes-robust",
            )
            standby_ids, design_cost, feasible = m9.standby_ids, m9.objective_cost, m9.feasible
            method_label = "M9-bayes"
            extras = {
                "expected_loss_per_axis": list(m9.expected_loss_per_axis),
                "threshold_per_axis": list(m9.threshold_per_axis),
            }
        else:
            raise ValueError(method)

        if not feasible:
            return {
                "feeder": feeder, "method": method, "method_label": method_label,
                "week": week, "pairing": pairing, "alpha": alpha,
                "design_cost": None, "n_standby": 0, "infeasible": True,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "metrics": {}, "error": None, "extras": extras,
            }

        run = grid_simulate(
            pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids),
            trace=trace, feeder_name=feeder, bus_map=bus_map,
            dispatch_policy=all_standby_dispatch_policy, sample_every=24,
        )
        result = to_grid_experiment_result(
            run, pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids), trace=trace,
            experiment_id=f"try12_acn_{method}_{feeder}_w{week}_p{pairing}",
            scenario_pack_id="try12_acn", method_label=method_label,
        )
        metrics = dict(BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result).values)

        return {
            "feeder": feeder, "method": method, "method_label": method_label,
            "week": week, "pairing": pairing, "alpha": alpha,
            "design_cost": design_cost, "n_standby": len(standby_ids),
            "infeasible": False, "elapsed_s": round(time.perf_counter() - started, 3),
            "metrics": metrics, "error": None, "extras": extras,
        }
    except Exception as e:
        return {
            "feeder": feeder, "method": method, "week": week, "pairing": pairing,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "error": f"{type(e).__name__}: {e}", "metrics": {},
        }


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
        if r.get("error") or r.get("infeasible"):
            continue
        by_fm[(r["feeder"], r["method_label"])].append(r)
    rows = []
    for (f, m), bucket in sorted(by_fm.items()):
        sla = [r["metrics"].get("sla_violation_ratio", float("nan")) for r in bucket]
        sla = [v for v in sla if isinstance(v, (int, float)) and not math.isnan(v)]
        vd = [r["metrics"].get("voltage_violation_dispatch_induced", float("nan")) for r in bucket]
        vd = [v for v in vd if isinstance(v, (int, float)) and not math.isnan(v)]
        cost = [r["design_cost"] for r in bucket if isinstance(r["design_cost"], (int, float))]
        sla_m, sla_lo, sla_hi = _bootstrap_ci(sla)
        vd_m, vd_lo, vd_hi = _bootstrap_ci(vd)
        rows.append({
            "feeder": f, "method_label": m, "n": len(bucket),
            "sla_v_mean": sla_m, "sla_v_ci_lo": sla_lo, "sla_v_ci_hi": sla_hi,
            "v_disp_mean": vd_m, "v_disp_ci_lo": vd_lo, "v_disp_ci_hi": vd_hi,
            "cost_mean": statistics.fmean(cost) if cost else float("nan"),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-csv", required=True, type=Path)
    parser.add_argument("--feeders", nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--week-offsets", type=int, nargs="+", default=list(DEFAULT_WEEK_OFFSETS))
    parser.add_argument("--window-days", type=int, default=7)
    parser.add_argument("--pairing-seeds", type=int, nargs="+", default=list(DEFAULT_PAIRING_SEEDS))
    parser.add_argument("--alpha", type=float, default=HARDER_ALPHA)
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    args = parser.parse_args()

    cells = [
        (f, m, str(args.sessions_csv), args.alpha, w, args.window_days, p)
        for f in args.feeders for m in args.methods
        for w in args.week_offsets for p in args.pairing_seeds
    ]
    n = len(cells)
    print(f"[try12 ACN] cells={n} (α={args.alpha}, window={args.window_days}d) workers={args.n_workers}")

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_cell, cells)):
                records.append(rec)
                if (i + 1) % 10 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    print(f"  [{i+1}/{n}] elapsed {elapsed:.0f}s")
    print(f"[try12 ACN] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / "try12_m1_vs_m9_acn.json"
    out_csv = args.output / "try12_m1_vs_m9_acn_summary.csv"

    out = {
        "records": records,
        "config": vars(args) | {"sessions_csv": str(args.sessions_csv), "output": str(args.output)},
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
    header = f"{'feeder':<14}{'method':<14}{'n':>4}{'sla_v %':>16}{'V_disp %':>16}{'cost ¥':>10}"
    print(header)
    print("-" * len(header))
    for r in rows:
        def fmt(m, lo, hi):
            if isinstance(m, float) and m == m:
                return f"{m*100:.2f}[{lo*100:.2f},{hi*100:.2f}]"
            return "—"
        print(
            f"{r['feeder']:<14}{r['method_label']:<14}{r['n']:>4}"
            f"{fmt(r['sla_v_mean'], r['sla_v_ci_lo'], r['sla_v_ci_hi']):>16}"
            f"{fmt(r['v_disp_mean'], r['v_disp_ci_lo'], r['v_disp_ci_hi']):>16}"
            f"{r['cost_mean']:>10.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
