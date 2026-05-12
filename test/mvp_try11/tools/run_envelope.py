"""Feasibility envelope sweep — (feeder, α, β) deployability map.

Phase D-4 (NEXT_STEPS.md §6). Where ``run_phase1_multifeeder.py`` sweeps
(feeder, scale, trace, method, seed) to compare *methods*, this runner
sweeps the *operating point* axes:

  * ``alpha`` (α): SLA scale = α · transformer MVA
  * ``beta`` (β):  burst level = β · default burst per trigger

so that each (feeder, α, β) cell measures *how often* a chosen method
remains feasible across a fan of traces and seeds. The output is a
deployability map suitable for a heatmap figure (``aggregate_envelope``).

Default sweep follows §6.2:
  feeder ∈ {cigre_lv, kerber_dorf, kerber_landnetz}
  α      ∈ {0.10, 0.20, 0.30, 0.40, 0.50, 0.60}
  β      ∈ {0.5, 1.0, 1.5, 2.0}
  scale  = 200
  traces = C1..C8
  method = M8 (default; can be overridden)
  seeds  = {0, 1, 2}

= 3 × 6 × 4 × 8 × 3 × 1 = 1728 cells (≈ 1 hour at 4 workers, M8).
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import time
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from .der_pool import (
    make_scaled_pool,
)
from .feeder_config import FEEDER_TRAFO_MVA, FeederVppConfig, feeder_active_pool
from .feeders import map_pool_to_feeder
from .grid_metrics import GRID_METRICS
from .grid_simulator import grid_simulate, to_grid_experiment_result
from .run_phase1_multifeeder import _make_trace, _solve
from .trace_synthesizer import (
    make_scarce_orthogonal_pool,
    perturb_pool_label_noise,
)
from .vpp_metrics import VPP_METRICS

DEFAULT_FEEDERS: tuple[str, ...] = tuple(FEEDER_TRAFO_MVA.keys())
DEFAULT_ALPHAS: tuple[float, ...] = (0.10, 0.20, 0.30, 0.40, 0.50, 0.60)
DEFAULT_BETAS: tuple[float, ...] = (0.5, 1.0, 1.5, 2.0)
DEFAULT_TRACES: tuple[str, ...] = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)


def envelope_config(feeder: str, alpha: float, beta: float) -> FeederVppConfig:
    """Construct a per-(feeder, α, β) operating-point config.

    α rescales the SLA target relative to ``trafo_MVA``; β rescales
    every burst entry relative to the default mix. ``n_active_ev`` is
    re-sized so the active pool still covers ~ 70 % of the new SLA.
    """
    trafo_mva = FEEDER_TRAFO_MVA[feeder]
    sla_kw = round(trafo_mva * 1000.0 * alpha)

    # Default burst mix (must mirror feeder_config.get_feeder_config)
    base_burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    scaled_burst = tuple(
        (axis, value * beta) for axis, value in base_burst
    )
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))
    return FeederVppConfig(
        feeder_name=feeder,
        sla_kw=float(sla_kw),
        burst_kw=scaled_burst,
        n_active_ev=n_active_ev,
    )


def run_one_envelope_cell(args: tuple) -> dict:
    """Single envelope cell.

    args = (feeder, alpha, beta, scale, trace_id, method, seed).
    Mirrors ``run_phase1_multifeeder.run_one_cell`` but threads the
    α-/β-rescaled ``FeederVppConfig`` through.
    """
    feeder, alpha, beta, scale, trace_id, method, seed = args
    started = time.perf_counter()
    try:
        config = envelope_config(feeder, alpha, beta)
        sla_kw = config.sla_kw
        burst = config.burst_dict()

        base_pool = make_scaled_pool(scale, seed=0)
        if trace_id == "C8":
            pool = make_scarce_orthogonal_pool(base_pool, n_utility_keep=2)
        elif trace_id == "C6":
            pool = perturb_pool_label_noise(base_pool, noise_rate=0.10, seed=seed + 11)
        else:
            pool = base_pool

        active_ids = feeder_active_pool(pool, config)
        bus_map = map_pool_to_feeder(pool, feeder)
        trace = _make_trace(trace_id, pool, seed, sla_kw)

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

        soft_metric_keys = (
            "voltage_slack_total_pu",
            "voltage_slack_max_pu",
            "line_slack_total_pct",
            "line_slack_max_pct",
            "soft_penalty_lambda",
            "active_cost",
            "standby_cost",
            "m8_worst_v_min_pu",
        )
        soft_metrics = {k: extras[k] for k in soft_metric_keys if k in extras}

        record_base = {
            "feeder": feeder,
            "alpha": alpha,
            "beta": beta,
            "scale": scale,
            "trace_id": trace_id,
            "method": method,
            "method_label": method_label,
            "seed": seed,
            "sla_kw": sla_kw,
        }

        if not feasible:
            elapsed = time.perf_counter() - started
            return {
                **record_base,
                "design_cost": None,
                "n_standby": 0,
                "design_solve_time_s": round(design_solve_time, 3),
                "elapsed_s": round(elapsed, 3),
                "infeasible": True,
                "infeasibility_reason": infeasibility_reason
                or "design optimisation reported infeasible",
                "metrics": dict(soft_metrics),
                "error": None,
            }

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
            experiment_id=(
                f"{method}_{trace_id}_{feeder}_a{alpha:.2f}_b{beta:.2f}_s{seed}"
            ),
            scenario_pack_id="try11_envelope",
            method_label=method_label,
        )
        harness = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS)
        summary = harness.evaluate(result)
        metrics_out: dict = dict(summary.values)
        metrics_out.update(soft_metrics)

        elapsed = time.perf_counter() - started
        return {
            **record_base,
            "design_cost": design_cost,
            "n_standby": len(standby_ids),
            "design_solve_time_s": round(design_solve_time, 3),
            "elapsed_s": round(elapsed, 3),
            "infeasible": False,
            "infeasibility_reason": None,
            "metrics": metrics_out,
            "error": None,
        }
    except Exception as e:
        elapsed = time.perf_counter() - started
        return {
            "feeder": feeder,
            "alpha": alpha,
            "beta": beta,
            "scale": scale,
            "trace_id": trace_id,
            "method": method,
            "seed": seed,
            "elapsed_s": round(elapsed, 3),
            "error": f"{type(e).__name__}: {e}",
            "metrics": {},
        }


def build_cell_list(
    feeders: tuple[str, ...],
    alphas: tuple[float, ...],
    betas: tuple[float, ...],
    scale: int,
    traces: tuple[str, ...],
    method: str,
    seeds: tuple[int, ...],
) -> list[tuple]:
    cells: list[tuple] = []
    for feeder in feeders:
        for alpha in alphas:
            for beta in betas:
                for trace_id in traces:
                    for seed in seeds:
                        cells.append((feeder, alpha, beta, scale, trace_id, method, seed))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description="try11 feasibility envelope sweep")
    parser.add_argument("--feeders", type=str, nargs="+", default=list(DEFAULT_FEEDERS))
    parser.add_argument("--alphas", type=float, nargs="+", default=list(DEFAULT_ALPHAS))
    parser.add_argument("--betas", type=float, nargs="+", default=list(DEFAULT_BETAS))
    parser.add_argument("--scale", type=int, default=200)
    parser.add_argument("--traces", type=str, nargs="+", default=list(DEFAULT_TRACES))
    parser.add_argument("--method", type=str, default="M8")
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    cells = build_cell_list(
        tuple(args.feeders), tuple(args.alphas), tuple(args.betas),
        int(args.scale), tuple(args.traces), str(args.method),
        tuple(args.seeds),
    )
    n = len(cells)
    print(
        f"[try11 envelope] cells = {n}, method = {args.method}, "
        f"workers = {args.n_workers}"
    )

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_envelope_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_envelope_cell, cells)):
                records.append(rec)
                if (i + 1) % 20 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    rate = (i + 1) / elapsed
                    eta = (n - (i + 1)) / rate if rate > 0 else 0
                    print(
                        f"  [{i + 1}/{n}] elapsed {elapsed:.0f}s, "
                        f"rate {rate:.2f}/s, ETA {eta:.0f}s"
                    )

    total_elapsed = time.perf_counter() - started
    print(f"[try11 envelope] total {total_elapsed:.0f}s for {n} cells")

    output_dir = (
        Path(args.output) if args.output else
        Path(__file__).resolve().parent.parent / "results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / f"try11_envelope_{args.method}.json"
    out_csv = output_dir / f"envelope_{args.method}_records.csv"

    out = {
        "records": records,
        "config": {
            "feeders": list(args.feeders),
            "alphas": list(args.alphas),
            "betas": list(args.betas),
            "scale": args.scale,
            "traces": list(args.traces),
            "method": args.method,
            "seeds": list(args.seeds),
        },
        "elapsed_s": round(total_elapsed, 1),
        "n_cells": n,
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_infeasible": sum(1 for r in records if r.get("infeasible")),
    }
    out_json.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    metric_names = sorted({m for r in records for m in r.get("metrics", {})})
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "feeder", "alpha", "beta", "scale", "trace_id", "method",
            "method_label", "seed", "sla_kw",
            "design_cost", "n_standby", "design_solve_time_s", "elapsed_s",
            "infeasible", "infeasibility_reason", "error", *metric_names,
        ])
        for r in records:
            w.writerow(
                [
                    r.get("feeder"), r.get("alpha"), r.get("beta"),
                    r.get("scale"), r.get("trace_id"), r.get("method"),
                    r.get("method_label"), r.get("seed"), r.get("sla_kw"),
                    r.get("design_cost"), r.get("n_standby"),
                    r.get("design_solve_time_s"), r.get("elapsed_s"),
                    r.get("infeasible", False),
                    r.get("infeasibility_reason", "") or "",
                    r.get("error", ""),
                    *(r.get("metrics", {}).get(name, "") for name in metric_names),
                ]
            )
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
