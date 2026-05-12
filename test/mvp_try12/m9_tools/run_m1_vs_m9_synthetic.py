"""MS-3: M1 (try11) vs M9 (try12) synthetic 144-cell sweep with bootstrap CI.

Sweep dimensions:
  feeders × methods × traces × seeds = 3 × 2 × 8 × 3 = 144 cells.

Each cell:
  * builds the same pool (seed=0 for pool determinism, seed varies the trace)
  * solves both M1 and M9 on the same input
  * runs the same vpp_simulator, computes SLA / OOD metrics
  * records: design_cost, n_standby, sla_violation_ratio, expected_loss_*

Bootstrap CI (n_boot=2000) per (feeder, method, trace) over the 3 seeds,
plus per-method overall CI over all (feeder, trace, seed) cells.

Compares M9's μ_k (post-hoc on selected DERs) vs the θ_k threshold to
verify Theorem 2 holds empirically.
"""

from __future__ import annotations

import argparse
import csv
import json
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

from tools.der_pool import (  # noqa: E402
    TRIGGER_BASIS_K3,
    make_default_pool,
)
from tools.feeder_config import FEEDER_TRAFO_MVA, feeder_active_pool, get_feeder_config  # noqa: E402
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
from tools.vpp_simulator import all_standby_dispatch_policy, simulate_vpp, to_experiment_result  # noqa: E402

from m9_tools.sdp_bayes_robust import solve_sdp_bayes_robust  # noqa: E402

DEFAULT_FEEDERS: tuple[str, ...] = tuple(FEEDER_TRAFO_MVA.keys())
DEFAULT_METHODS: tuple[str, ...] = ("M1", "M9")
DEFAULT_TRACES: tuple[str, ...] = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)
DEFAULT_THETA_FRACTION: float = 0.05  # M9: θ_k = 5% × B_k


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


def _solve_method(method, pool, active_ids, burst, theta_fraction):
    if method == "M1":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
        extras = {
            "expected_loss_per_axis": (),
            "threshold_per_axis": (),
            "epsilon": None,
        }
        return sol.standby_ids, sol.objective_cost, sol.feasible, "M1", extras
    if method == "M9":
        m9 = solve_sdp_bayes_robust(
            pool, active_ids, burst,
            basis=TRIGGER_BASIS_K3,
            epsilon=0.05,
            expected_loss_threshold_fraction=theta_fraction,
            mode="M9-bayes-robust",
        )
        extras = {
            "expected_loss_per_axis": list(m9.expected_loss_per_axis),
            "threshold_per_axis": list(m9.threshold_per_axis),
            "epsilon": m9.epsilon,
        }
        return m9.standby_ids, m9.objective_cost, m9.feasible, "M9-bayes", extras
    raise ValueError(method)


def run_one_cell(args):
    feeder, method, trace_id, seed, theta_fraction = args
    started = time.perf_counter()
    try:
        config = get_feeder_config(feeder)
        sla_kw = config.sla_kw
        burst = config.burst_dict()

        base_pool = make_default_pool(seed=0)
        if trace_id == "C8":
            pool = make_scarce_orthogonal_pool(base_pool, n_utility_keep=2)
        elif trace_id == "C6":
            pool = perturb_pool_label_noise(base_pool, noise_rate=0.10, seed=seed + 11)
        else:
            pool = base_pool

        active_ids = feeder_active_pool(pool, config)
        trace = _make_trace(trace_id, pool, seed, sla_kw)

        design_t0 = time.perf_counter()
        standby_ids, design_cost, feasible, method_label, extras = _solve_method(
            method, pool, active_ids, burst, theta_fraction,
        )
        design_solve_time = time.perf_counter() - design_t0

        if not feasible:
            return {
                "feeder": feeder, "method": method, "method_label": method_label,
                "trace_id": trace_id, "seed": seed, "theta_fraction": theta_fraction,
                "design_cost": None, "n_standby": 0,
                "design_solve_time_s": round(design_solve_time, 3),
                "elapsed_s": round(time.perf_counter() - started, 3),
                "infeasible": True, "metrics": {}, "error": None,
                "extras": extras,
            }

        run = simulate_vpp(
            pool=pool,
            active_ids=active_ids,
            standby_ids=frozenset(standby_ids),
            trace=trace,
            dispatch_policy=all_standby_dispatch_policy,
        )
        result = to_experiment_result(
            run, pool=pool, active_ids=active_ids,
            standby_ids=frozenset(standby_ids), trace=trace,
            experiment_id=f"try12_{method}_{trace_id}_{feeder}_s{seed}",
            scenario_pack_id="try12_synthetic",
            method_label=method_label,
        )
        summary = BenchmarkHarness(metrics=VPP_METRICS).evaluate(result)
        metrics = dict(summary.values)

        return {
            "feeder": feeder, "method": method, "method_label": method_label,
            "trace_id": trace_id, "seed": seed, "theta_fraction": theta_fraction,
            "design_cost": design_cost, "n_standby": len(standby_ids),
            "design_solve_time_s": round(design_solve_time, 3),
            "elapsed_s": round(time.perf_counter() - started, 3),
            "infeasible": False, "metrics": metrics, "error": None,
            "extras": extras,
        }
    except Exception as e:
        return {
            "feeder": feeder, "method": method, "trace_id": trace_id, "seed": seed,
            "theta_fraction": theta_fraction,
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
    """Per (feeder, method, trace) and per-method summaries with CI."""
    METRICS = ("sla_violation_ratio", "sla_violation_ratio_train", "sla_violation_ratio_test", "ood_gap")
    rows = []

    # Per-method overall (across all feeder × trace × seed)
    by_m = defaultdict(list)
    by_m_cost = defaultdict(list)
    for r in records:
        if r.get("error") or r.get("infeasible"):
            continue
        m = r["method_label"]
        for k in METRICS:
            v = r["metrics"].get(k)
            if isinstance(v, (int, float)):
                by_m[(m, k)].append(float(v))
        if isinstance(r.get("design_cost"), (int, float)):
            by_m_cost[m].append(float(r["design_cost"]))

    for m in sorted({k[0] for k in by_m}):
        row = {"feeder": "ALL", "method_label": m, "trace_id": "ALL"}
        for k in METRICS:
            mean, lo, hi = _bootstrap_ci(by_m[(m, k)])
            row[f"{k}_mean"] = mean
            row[f"{k}_ci_lo"] = lo
            row[f"{k}_ci_hi"] = hi
        cost_v = by_m_cost.get(m, [])
        row["design_cost_mean"] = statistics.fmean(cost_v) if cost_v else float("nan")
        row["n"] = len(cost_v)
        rows.append(row)

    return rows


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--feeders", nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--methods", nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--traces", nargs="+", default=list(DEFAULT_TRACES))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--theta-fraction", type=float, default=DEFAULT_THETA_FRACTION)
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=Path, default=_HERE.parent / "results")
    args = parser.parse_args()

    cells = [
        (f, m, t, s, args.theta_fraction)
        for f in args.feeders for m in args.methods for t in args.traces for s in args.seeds
    ]
    n = len(cells)
    print(f"[try12 synthetic] cells={n} (θ={args.theta_fraction}·B_k) workers={args.n_workers}")

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_cell, cells)):
                records.append(rec)
                if (i + 1) % 20 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    print(f"  [{i+1}/{n}] elapsed {elapsed:.0f}s")
    print(f"[try12 synthetic] total {time.perf_counter() - started:.0f}s for {n} cells")

    args.output.mkdir(parents=True, exist_ok=True)
    out_json = args.output / "try12_m1_vs_m9_synthetic.json"
    out_csv = args.output / "try12_m1_vs_m9_summary.csv"

    out = {
        "records": records,
        "config": {
            "feeders": args.feeders, "methods": args.methods,
            "traces": args.traces, "seeds": args.seeds,
            "theta_fraction": args.theta_fraction,
        },
        "elapsed_s": round(time.perf_counter() - started, 1),
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
    print(f"Wrote {out_json}\nWrote {out_csv}")

    print()
    print(f"{'method':<14}{'n':>5}{'sla_v %':>14}{'sla_test %':>14}{'ood_gap %':>14}{'cost ¥':>12}")
    print("-" * 73)
    for r in rows:
        def fmt(k):
            m = r.get(f"{k}_mean")
            lo = r.get(f"{k}_ci_lo")
            hi = r.get(f"{k}_ci_hi")
            if isinstance(m, float) and m == m:
                return f"{m*100:.2f}[{lo*100:.2f},{hi*100:.2f}]"
            return "—"
        print(
            f"{r['method_label']:<14}{r['n']:>5}"
            f"{fmt('sla_violation_ratio'):>14}"
            f"{fmt('sla_violation_ratio_test'):>14}"
            f"{fmt('ood_gap'):>14}"
            f"{r['design_cost_mean']:>12.0f}"
        )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
