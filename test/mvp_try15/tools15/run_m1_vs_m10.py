"""MS-4: M1 (try11) vs M10 (try15) comparison on the same trace.

Purpose: empirically demonstrate that τ-diversification (M10) achieves
**lower SLA tail** than uniform-τ MILP (M1) on the SAME trace, using
the SAME pool, where the only difference is:

  * M1 picks standby via cost-min MILP set-cover
  * M10 picks standby via greedy τ-diversification heuristic

Both solutions are then evaluated on a τ-aware simulator that models
DER drop delays τ_j explicitly. This is the apples-to-apples
comparison that exits the try11-14 paradigm.

Sweep: 3 feeders × 2 methods × 8 traces × 3 seeds = 144 cells.
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

from tools.der_pool import TRIGGER_BASIS_K3  # noqa: E402
from tools.feeder_config import feeder_active_pool, get_feeder_config  # noqa: E402
from tools.sdp_optimizer import solve_sdp_strict  # noqa: E402
from tools.trace_synthesizer import (  # noqa: E402
    make_scarce_orthogonal_pool,
    perturb_pool_label_noise,
    synth_c1_single_trigger,
    synth_c2_extreme_burst,
    synth_c3_simultaneous,
    synth_c4_out_of_basis,
    synth_c5_frequency_shift,
    synth_c7_correlation_reversal,
    synth_c8_scarce_orthogonal,
)
from tools.vpp_metrics import VPP_METRICS  # noqa: E402

from tools15.m10_selection import select_m10  # noqa: E402
from tools15.tau_pool import make_tau_pool, tau_diversity  # noqa: E402
from tools15.tau_simulator import tau_simulate, to_experiment_result_tau  # noqa: E402

DEFAULT_FEEDERS = ("cigre_lv", "kerber_dorf", "kerber_landnetz")
DEFAULT_METHODS = ("M1", "M10")
DEFAULT_TRACES = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
DEFAULT_SEEDS = (0, 1, 2)


def _make_trace(trace_id, pool, seed, sla_kw):
    if trace_id == "C1":
        return synth_c1_single_trigger(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C2":
        return synth_c2_extreme_burst(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C3":
        return synth_c3_simultaneous(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C4":
        return synth_c4_out_of_basis(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C5":
        return synth_c5_frequency_shift(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C6":
        return synth_c1_single_trigger(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C7":
        return synth_c7_correlation_reversal(pool, seed=seed, sla_kw=sla_kw)
    if trace_id == "C8":
        return synth_c8_scarce_orthogonal(pool, seed=seed, sla_kw=sla_kw)
    raise ValueError(trace_id)


def run_one_cell(args):
    feeder, method, trace_id, seed = args
    started = time.perf_counter()
    try:
        config = get_feeder_config(feeder)
        burst = config.burst_dict()
        # τ-aware pool, seed=0 for pool determinism
        tau_pool = make_tau_pool(seed=0)
        pool = tau_pool.pool

        # Trace-specific pool modification (mirrors try11)
        if trace_id == "C8":
            modified_pool = make_scarce_orthogonal_pool(pool, n_utility_keep=2)
        elif trace_id == "C6":
            modified_pool = perturb_pool_label_noise(pool, noise_rate=0.10, seed=seed + 11)
        else:
            modified_pool = pool
        # Carry τ over to the modified pool by der_id (= same DERs, just
        # exposure perturbed). Build a transient TauPool with the modified pool.
        from tools15.tau_pool import TauPool
        tau_dict = tau_pool.tau_dict()
        tau_pool_eff = TauPool(
            pool=modified_pool,
            tau_drop_s=tuple((d.der_id, tau_dict.get(d.der_id, 60.0)) for d in modified_pool),
        )

        active_ids = feeder_active_pool(modified_pool, config)
        trace = _make_trace(trace_id, modified_pool, seed, config.sla_kw)

        if method == "M1":
            sol = solve_sdp_strict(modified_pool, active_ids, burst,
                                   basis=TRIGGER_BASIS_K3, mode="M1")
            standby_ids = sol.standby_ids
            design_cost = sol.objective_cost
            feasible = sol.feasible
            label = "M1"
            div = tau_diversity(tau_pool_eff, standby_ids)
        elif method == "M10":
            sol = select_m10(tau_pool_eff, active_ids, burst,
                             basis=TRIGGER_BASIS_K3, mode="M10")
            standby_ids = sol.standby_ids
            design_cost = sol.objective_cost
            feasible = sol.feasible
            label = "M10-tau"
            div = sol.tau_diversity_log
        else:
            raise ValueError(method)

        if not feasible:
            return {"feeder": feeder, "method": method, "method_label": label,
                    "trace_id": trace_id, "seed": seed,
                    "design_cost": None, "infeasible": True,
                    "tau_diversity_log": float("nan"),
                    "elapsed_s": round(time.perf_counter() - started, 3),
                    "metrics": {}, "error": None}

        run = tau_simulate(tau_pool_eff, active_ids, frozenset(standby_ids),
                           trace, seed=seed)
        result = to_experiment_result_tau(
            run, tau_pool_eff, active_ids, frozenset(standby_ids), trace,
            experiment_id=f"try15_{label}_{trace_id}_{feeder}_s{seed}",
            scenario_pack_id="try15", method_label=label,
        )
        metrics = dict(BenchmarkHarness(metrics=VPP_METRICS).evaluate(result).values)
        # Add custom τ metrics
        metrics["sla_violation_rate_tau"] = run.sla_violation_rate
        metrics["aggregate_min_kw"] = run.aggregate_min_kw

        return {"feeder": feeder, "method": method, "method_label": label,
                "trace_id": trace_id, "seed": seed,
                "design_cost": design_cost, "n_standby": len(standby_ids),
                "tau_diversity_log": div,
                "infeasible": False,
                "elapsed_s": round(time.perf_counter() - started, 3),
                "metrics": metrics, "error": None}
    except Exception as e:
        return {"feeder": feeder, "method": method, "trace_id": trace_id, "seed": seed,
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
    by_m = defaultdict(list)
    for r in records:
        if r.get("error") or r.get("infeasible"):
            continue
        by_m[r["method_label"]].append(r)
    rows = []
    for m, bucket in sorted(by_m.items()):
        sla = [r["metrics"].get("sla_violation_ratio", float("nan")) for r in bucket]
        sla = [v for v in sla if isinstance(v, (int, float)) and not math.isnan(v)]
        sla_t = [r["metrics"].get("sla_violation_rate_tau", float("nan")) for r in bucket]
        sla_t = [v for v in sla_t if isinstance(v, (int, float)) and not math.isnan(v)]
        amin = [r["metrics"].get("aggregate_min_kw", float("nan")) for r in bucket]
        amin = [v for v in amin if isinstance(v, (int, float)) and not math.isnan(v)]
        cost = [r["design_cost"] for r in bucket if isinstance(r["design_cost"], (int, float))]
        div = [r["tau_diversity_log"] for r in bucket
               if isinstance(r["tau_diversity_log"], float) and not math.isnan(r["tau_diversity_log"])]
        sla_m, sla_lo, sla_hi = _bootstrap_ci(sla)
        slat_m, slat_lo, slat_hi = _bootstrap_ci(sla_t)
        amin_m, amin_lo, amin_hi = _bootstrap_ci(amin)
        rows.append({
            "method_label": m, "n": len(bucket),
            "sla_v_mean": sla_m, "sla_v_ci_lo": sla_lo, "sla_v_ci_hi": sla_hi,
            "sla_v_tau_mean": slat_m, "sla_v_tau_ci_lo": slat_lo, "sla_v_tau_ci_hi": slat_hi,
            "aggregate_min_mean": amin_m, "aggregate_min_ci_lo": amin_lo, "aggregate_min_ci_hi": amin_hi,
            "cost_mean": statistics.fmean(cost) if cost else float("nan"),
            "tau_diversity_log_mean": statistics.fmean(div) if div else float("nan"),
        })
    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feeders", nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--traces", nargs="+", default=list(DEFAULT_TRACES))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    args = parser.parse_args()

    cells = [(f, m, t, s) for f in args.feeders for m in args.methods
             for t in args.traces for s in args.seeds]
    n = len(cells)
    print(f"[try15 m1_vs_m10] cells={n} workers={args.n_workers}")

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
    print(f"[try15 m1_vs_m10] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / "try15_m1_vs_m10.json"
    out_csv = args.output / "try15_m1_vs_m10_summary.csv"

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
    h = (f"{'method':<14}{'n':>4}{'SLA % [CI]':>20}{'SLA_τ % [CI]':>20}"
         f"{'aggMin kW':>14}{'cost ¥':>10}{'log(τ) σ':>10}")
    print(h); print("-" * len(h))
    for r in rows:
        def fmt(m, lo, hi):
            if isinstance(m, float) and m == m:
                return f"{m*100:.2f}[{lo*100:.2f},{hi*100:.2f}]"
            return "—"
        print(
            f"{r['method_label']:<14}{r['n']:>4}"
            f"{fmt(r['sla_v_mean'], r['sla_v_ci_lo'], r['sla_v_ci_hi']):>20}"
            f"{fmt(r['sla_v_tau_mean'], r['sla_v_tau_ci_lo'], r['sla_v_tau_ci_hi']):>20}"
            f"{r['aggregate_min_mean']:>14.0f}"
            f"{r['cost_mean']:>10.0f}"
            f"{r['tau_diversity_log_mean']:>10.2f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
