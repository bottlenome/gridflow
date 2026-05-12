"""MS-5: Sensitivity sweep for M9 — θ scan and ε scan on kerber_landnetz.

The MS-4 ACN sweep showed M9 beats M1 on kerber_landnetz at α=0.70 with
the default θ_k = 5%·B_k. This MS-5 maps the cost / SLA-violation Pareto
as θ varies, plus tests robustness to mis-specified ε.

Sweep:
  feeder = kerber_landnetz, α = 0.70
  method = M9
  θ_fraction ∈ {0.00, 0.01, 0.02, 0.05, 0.10, 0.20, 1.00}
  ε ∈ {0.01, 0.05, 0.10, 0.20}
  4 weeks × 3 pairings = 12 cells per (θ, ε)
  Total: 7 × 4 × 12 = 336 cells

Plus M1 baseline for the same 12 (week, pairing) cells.
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

ALPHA = 0.70
FEEDER = "kerber_landnetz"
WEEK_OFFSETS = (0, 7, 14, 21)
PAIRING_SEEDS = (0, 1, 2)
THETA_FRACTIONS = (0.00, 0.01, 0.02, 0.05, 0.10, 0.20, 1.00)
EPSILONS = (0.01, 0.05, 0.10, 0.20)


def _config():
    trafo_mva = FEEDER_TRAFO_MVA[FEEDER]
    sla_kw = round(trafo_mva * 1000.0 * ALPHA)
    burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))
    return FeederVppConfig(FEEDER, float(sla_kw), burst, n_active_ev)


def run_one_cell(args):
    method, theta_fraction, epsilon, sessions_csv, week, pairing = args
    started = time.perf_counter()
    try:
        config = _config()
        burst = config.burst_dict()
        pool = make_default_pool(seed=0)
        bus_map = map_pool_to_feeder(pool, FEEDER)
        active_ids = feeder_active_pool(pool, config)

        trace = build_trace_from_acn_sessions(
            Path(sessions_csv), pool, sla_kw=config.sla_kw, seed=0,
            horizon_days=7, start_offset_days=week, pairing_seed=pairing,
            trace_id=f"sens-w{week}-p{pairing}",
        )

        if method == "M1":
            sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
            standby_ids, design_cost, feasible = sol.standby_ids, sol.objective_cost, sol.feasible
            label = "M1"
        elif method == "M9":
            m9 = solve_sdp_bayes_robust(
                pool, active_ids, burst,
                basis=TRIGGER_BASIS_K3, epsilon=epsilon,
                expected_loss_threshold_fraction=theta_fraction,
                mode=f"M9-θ{theta_fraction:.2f}-ε{epsilon:.2f}",
            )
            standby_ids, design_cost, feasible = m9.standby_ids, m9.objective_cost, m9.feasible
            label = f"M9-θ{theta_fraction:.2f}-ε{epsilon:.2f}"
        else:
            raise ValueError(method)

        if not feasible:
            return {
                "method": method, "label": label,
                "theta_fraction": theta_fraction, "epsilon": epsilon,
                "week": week, "pairing": pairing,
                "design_cost": None, "infeasible": True,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "metrics": {}, "error": None,
            }

        run = grid_simulate(
            pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids),
            trace=trace, feeder_name=FEEDER, bus_map=bus_map,
            dispatch_policy=all_standby_dispatch_policy, sample_every=24,
        )
        result = to_grid_experiment_result(
            run, pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids), trace=trace,
            experiment_id=f"sens_{label}_w{week}_p{pairing}",
            scenario_pack_id="try12_sens", method_label=label,
        )
        metrics = dict(BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result).values)
        return {
            "method": method, "label": label,
            "theta_fraction": theta_fraction, "epsilon": epsilon,
            "week": week, "pairing": pairing,
            "design_cost": design_cost, "n_standby": len(standby_ids),
            "infeasible": False,
            "elapsed_s": round(time.perf_counter() - started, 3),
            "metrics": metrics, "error": None,
        }
    except Exception as e:
        return {"method": method, "theta_fraction": theta_fraction, "epsilon": epsilon,
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


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sessions-csv", required=True, type=Path)
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    args = parser.parse_args()

    cells = []
    # M1 baseline (only varies by week/pairing — θ/ε irrelevant)
    for w in WEEK_OFFSETS:
        for p in PAIRING_SEEDS:
            cells.append(("M1", 0.0, 0.05, str(args.sessions_csv), w, p))
    # M9 sensitivity
    for theta in THETA_FRACTIONS:
        for eps in EPSILONS:
            for w in WEEK_OFFSETS:
                for p in PAIRING_SEEDS:
                    cells.append(("M9", theta, eps, str(args.sessions_csv), w, p))

    n = len(cells)
    print(f"[try12 sensitivity] cells={n} (α={ALPHA}, feeder={FEEDER}) workers={args.n_workers}")

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
    print(f"[try12 sensitivity] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / "try12_sensitivity.json"
    out_csv = args.output / "try12_sensitivity_summary.csv"

    out = {
        "records": records,
        "config": {"feeder": FEEDER, "alpha": ALPHA,
                   "theta_fractions": list(THETA_FRACTIONS),
                   "epsilons": list(EPSILONS),
                   "week_offsets": list(WEEK_OFFSETS),
                   "pairing_seeds": list(PAIRING_SEEDS)},
        "elapsed_s": round(time.perf_counter() - started, 1),
        "n_cells": n,
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_infeasible": sum(1 for r in records if r.get("infeasible")),
    }
    out_json.write_text(json.dumps(out, indent=2, sort_keys=True, default=str), encoding="utf-8")

    # Aggregate per (method, theta, epsilon)
    by_key = defaultdict(list)
    for r in records:
        if r.get("error"):
            continue
        key = (r["method"], r["theta_fraction"], r["epsilon"])
        by_key[key].append(r)

    rows = []
    for (m, theta, eps), bucket in sorted(by_key.items()):
        feasible = [r for r in bucket if not r.get("infeasible")]
        sla = [r["metrics"].get("sla_violation_ratio", float("nan")) for r in feasible]
        sla = [v for v in sla if isinstance(v, (int, float)) and not math.isnan(v)]
        cost = [r["design_cost"] for r in feasible if isinstance(r["design_cost"], (int, float))]
        sla_m, sla_lo, sla_hi = _bootstrap_ci(sla)
        rows.append({
            "method": m, "theta_fraction": theta, "epsilon": eps,
            "n_total": len(bucket), "n_feasible": len(feasible),
            "n_infeasible": sum(1 for r in bucket if r.get("infeasible")),
            "feasibility_rate": len(feasible) / len(bucket) if bucket else 0.0,
            "sla_v_mean": sla_m, "sla_v_ci_lo": sla_lo, "sla_v_ci_hi": sla_hi,
            "cost_mean": statistics.fmean(cost) if cost else float("nan"),
        })
    if rows:
        with out_csv.open("w", encoding="utf-8", newline="") as fh:
            w = csv.DictWriter(fh, fieldnames=list(rows[0].keys()))
            w.writeheader()
            w.writerows(rows)
    print(f"Wrote {out_json}\nWrote {out_csv}")
    print()
    print(f"{'method':<10}{'θ':>6}{'ε':>6}{'feas/n':>10}{'sla_v %':>16}{'cost ¥':>10}")
    print("-" * 60)
    for r in rows:
        feas = f"{r['n_feasible']}/{r['n_total']}"
        if isinstance(r['sla_v_mean'], float) and r['sla_v_mean'] == r['sla_v_mean']:
            sla_s = f"{r['sla_v_mean']*100:.2f}[{r['sla_v_ci_lo']*100:.2f},{r['sla_v_ci_hi']*100:.2f}]"
        else:
            sla_s = "—"
        cost_s = f"{r['cost_mean']:.0f}" if isinstance(r['cost_mean'], float) and r['cost_mean'] == r['cost_mean'] else "—"
        print(f"{r['method']:<10}{r['theta_fraction']:>6.2f}{r['epsilon']:>6.2f}{feas:>10}{sla_s:>16}{cost_s:>10}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
