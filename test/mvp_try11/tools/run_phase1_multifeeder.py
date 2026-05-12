"""F-M2 sweep runner — multi-feeder × multi-scale × extended traces.

Spec: implementation_plan.md F-M2.

Sweep dimensions:
  * 3 feeders   (cigre_lv / kerber_dorf / kerber_landnetz)
  * 4 scales    (50 / 200 / 1000 / 5000)
  * 8 traces    (C1-C6 from MS-1, plus C7 / C8 from MS-A4)
  * 15 methods  (M1, M2a-c, M3b, M3c, M4b, M5, M6, B1-B6)
  * 3 seeds
= 4320 cells. Local 4-core multiprocessing target: ~2-3 hours.

Two limitations adopted to keep run time tractable:
  1. **PF sampling stride = 24** (= every 2 hours): grid power-flow only
     samples the trace; aggregate-output and SLA metrics still use full
     resolution.
  2. **Method skip rules at large scale**: MILP-based methods (M1, M2a-c,
     M3b, M3c, M5, M6, B2, B3) skip when ``scale >= 5000``; greedy (M4b)
     and structural baselines (B1, B4, B5, B6) run at all scales.

Each cell records:
  * design_cost, n_standby, design_solve_time
  * SLA metrics (full / train / test / OOD gap)
  * Grid metrics (voltage_violation_ratio, line_overload_ratio,
                  max_line_load_pct, min/max voltage)
  * total experiment time
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import time
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from .baselines import (
    naive_nn_dispatch_policy,
    solve_b1_static_overprov,
    solve_b2_stochastic_program,
    solve_b3_wasserstein_dro,
    solve_b4_markowitz,
    solve_b5_financial_causal,
    solve_b6_naive_nn,
)
from .der_pool import (
    SCALE_PROFILES,
    TRIGGER_BASIS_K2,
    TRIGGER_BASIS_K3,
    TRIGGER_BASIS_K4,
    make_scaled_pool,
)
from .feeder_config import FEEDER_TRAFO_MVA, feeder_active_pool, get_feeder_config
from .feeders import map_pool_to_feeder
from .grid_metrics import GRID_METRICS
from .grid_simulator import grid_simulate, to_grid_experiment_result
from .sdp_full_milp import solve_sdp_full
from .sdp_grid_aware import solve_sdp_grid_aware, solve_sdp_grid_aware_soft
from .sdp_optimizer import (
    solve_sdp_greedy,
    solve_sdp_soft,
    solve_sdp_strict,
    solve_sdp_tolerant,
)
from .trace_synthesizer import (
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
from .vpp_metrics import VPP_METRICS
from .vpp_simulator import all_standby_dispatch_policy

METHODS = ("M1", "M2a", "M2b", "M2c", "M3b", "M3c", "M4b", "M5", "M6", "M7", "M7-soft", "M8",
           "B1", "B2", "B3", "B4", "B5", "B6")

TRACES = ("C1", "C2", "C3", "C4", "C5", "C6", "C7", "C8")

FEEDERS = tuple(FEEDER_TRAFO_MVA.keys())

# Methods that skip at scale=5000 (too slow)
SKIP_AT_5000 = frozenset({
    "M1", "M2a", "M2b", "M2c", "M3b", "M3c", "M5", "M6",
    "M7", "M7-soft", "M8", "B2", "B3",
})


def _make_trace(trace_id: str, pool, seed: int, sla_kw: float):
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
    raise ValueError(f"unknown trace: {trace_id}")


def _solve(method: str, pool, active_ids, trace, *, burst, sla_kw, seed,
           bus_map=None, feeder_name=None):
    """Run the design optimisation for one method.

    Returns ``(standby_ids, design_cost, method_label, dispatch_policy, extras)``.

    ``extras`` carries optional diagnostics (currently ``feasible`` and the
    M7-soft slack stats when applicable). Callers must always unpack the
    5-tuple; for hard methods the dict is ``{"feasible": True}``.
    """
    feasible = True
    extras: dict = {"feasible": True}
    if method == "M1":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
        return sol.standby_ids, sol.objective_cost, "M1", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M2a":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K2, mode="M2a")
        return sol.standby_ids, sol.objective_cost, "M2a-K2", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M2b":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M2b")
        return sol.standby_ids, sol.objective_cost, "M2b-K3", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M2c":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K4, mode="M2c")
        return sol.standby_ids, sol.objective_cost, "M2c-K4", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M3b":
        sol = solve_sdp_soft(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M3b")
        return sol.standby_ids, sol.objective_cost, "M3b-soft", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M3c":
        sol = solve_sdp_tolerant(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M3c")
        return sol.standby_ids, sol.objective_cost, "M3c-tolerant", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M4b":
        sol = solve_sdp_greedy(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M4b")
        return sol.standby_ids, sol.objective_cost, "M4b-greedy", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M5":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M5")
        policy = naive_nn_dispatch_policy(trace=trace, seed=seed)
        return sol.standby_ids, sol.objective_cost, "M5-NN", policy, {"feasible": sol.feasible}
    if method == "M6":
        perturbed = perturb_pool_label_noise(pool, noise_rate=0.10, seed=seed + 99)
        sol = solve_sdp_strict(perturbed, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M6")
        return sol.standby_ids, sol.objective_cost, "M6-noise10", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "M7":
        if bus_map is None or feeder_name is None:
            raise ValueError("M7 requires bus_map and feeder_name")
        # Phase D-2: ANSI C84.1 / IEEE 1547 strict envelope. Cells where
        # this is infeasible are reported honestly in the record (the
        # earlier relaxed V_max=1.10 / L_max=120% hack was retracted).
        sol = solve_sdp_grid_aware(
            pool, active_ids, burst, bus_map=bus_map, feeder_name=feeder_name,
            basis=TRIGGER_BASIS_K3,
            v_max_pu=1.05, line_max_pct=100.0,
            mode="M7-strict-grid",
        )
        return (
            sol.standby_ids,
            sol.objective_cost,
            "M7-strict",
            all_standby_dispatch_policy,
            {
                "feasible": sol.feasible,
                "infeasibility_reason": (
                    None if sol.feasible
                    else "M7 MILP infeasible under V_max=1.05 / L_max=100%"
                ),
            },
        )
    if method == "M7-soft":
        if bus_map is None or feeder_name is None:
            raise ValueError("M7-soft requires bus_map and feeder_name")
        soft = solve_sdp_grid_aware_soft(
            pool, active_ids, burst, bus_map=bus_map, feeder_name=feeder_name,
            basis=TRIGGER_BASIS_K3,
            v_max_pu=1.05, line_max_pct=100.0,
            mode="M7-soft",
        )
        sol = soft.solution
        slack_extras: dict = {"feasible": sol.feasible}
        slack_extras.update(soft.metric_dict())
        if not sol.feasible:
            slack_extras["infeasibility_reason"] = (
                "M7-soft MILP infeasible under K3 orthogonality + capacity coverage"
            )
        return sol.standby_ids, sol.objective_cost, "M7-soft", all_standby_dispatch_policy, slack_extras
    if method == "M8":
        if bus_map is None or feeder_name is None:
            raise ValueError("M8 requires bus_map and feeder_name")
        full = solve_sdp_full(
            pool, bus_map=bus_map, feeder_name=feeder_name,
            burst_kw=burst, sla_target_kw=sla_kw,
            basis=TRIGGER_BASIS_K3,
            v_max_pu=1.05, v_min_pu=0.95, line_max_pct=100.0,
            mode="M8-full",
        )
        m8_extras: dict = {
            "feasible": full.feasible,
            # The MILP picks both active and standby; downstream
            # ``run_one_cell`` must use this active assignment for the
            # simulation, not the legacy ``feeder_active_pool`` default.
            "active_ids_override": frozenset(full.active_ids),
            "active_cost": full.active_cost,
            "standby_cost": full.standby_cost,
            "m8_worst_v_min_pu": full.worst_v_min_pu,
        }
        if not full.feasible:
            m8_extras["infeasibility_reason"] = (
                "M8 joint MILP infeasible under V_max=1.05 / V_min=0.95 / L_max=100%"
            )
        return (
            full.standby_ids,
            full.objective_cost,
            "M8-full",
            all_standby_dispatch_policy,
            m8_extras,
        )
    if method == "B1":
        sol = solve_b1_static_overprov(pool, active_ids, overprov_factor=0.30)
        return sol.standby_ids, sol.objective_cost, "B1", all_standby_dispatch_policy, extras
    if method == "B2":
        sol = solve_b2_stochastic_program(pool, active_ids, burst, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B2", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "B3":
        sol = solve_b3_wasserstein_dro(pool, active_ids, burst, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B3", all_standby_dispatch_policy, {"feasible": sol.feasible}
    if method == "B4":
        sol = solve_b4_markowitz(pool, active_ids, trace, sla_target_kw=sla_kw)
        return sol.standby_ids, sol.objective_cost, "B4", all_standby_dispatch_policy, extras
    if method == "B5":
        sol = solve_b5_financial_causal(pool, active_ids, trace, sla_target_kw=sla_kw)
        return sol.standby_ids, sol.objective_cost, "B5", all_standby_dispatch_policy, extras
    if method == "B6":
        sol = solve_b6_naive_nn(pool, active_ids, trace, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B6", all_standby_dispatch_policy, extras
    _ = feasible  # quieten linter; loop above is exhaustive
    raise ValueError(f"unknown method: {method}")


def run_one_cell(args: tuple) -> dict:
    """Single child experiment. Picklable for multiprocessing."""
    feeder, scale, trace_id, method, seed = args
    started = time.perf_counter()
    try:
        config = get_feeder_config(feeder)
        sla_kw = config.sla_kw
        burst = config.burst_dict()

        # Pool construction + per-trace pool modification (C8)
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

        # M8 picks the active pool itself; honour its assignment when present.
        active_ids_for_sim = extras.get("active_ids_override", active_ids)

        # Slack stats from M7-soft (or any future soft variant) flow into
        # ``metrics`` so they appear alongside voltage/SLA columns in the CSV.
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
        soft_metrics = {
            k: extras[k] for k in soft_metric_keys if k in extras
        }

        if not feasible:
            elapsed = time.perf_counter() - started
            return {
                "feeder": feeder,
                "scale": scale,
                "trace_id": trace_id,
                "method": method,
                "method_label": method_label,
                "seed": seed,
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
            experiment_id=f"{method}_{trace_id}_{feeder}_n{scale}_s{seed}",
            scenario_pack_id="try11_FM2",
            method_label=method_label,
        )
        harness = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS)
        summary = harness.evaluate(result)
        metrics_out: dict = dict(summary.values)
        metrics_out.update(soft_metrics)

        elapsed = time.perf_counter() - started
        return {
            "feeder": feeder,
            "scale": scale,
            "trace_id": trace_id,
            "method": method,
            "method_label": method_label,
            "seed": seed,
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
            "feeder": feeder, "scale": scale, "trace_id": trace_id,
            "method": method, "seed": seed,
            "elapsed_s": round(elapsed, 3),
            "error": f"{type(e).__name__}: {e}",
            "metrics": {},
        }


def build_cell_list(
    feeders: tuple[str, ...],
    scales: tuple[int, ...],
    traces: tuple[str, ...],
    methods: tuple[str, ...],
    seeds: tuple[int, ...],
) -> list[tuple]:
    cells: list[tuple] = []
    for feeder in feeders:
        for scale in scales:
            for trace_id in traces:
                for method in methods:
                    if scale >= 5000 and method in SKIP_AT_5000:
                        continue
                    for seed in seeds:
                        cells.append((feeder, scale, trace_id, method, seed))
    return cells


def main() -> int:
    parser = argparse.ArgumentParser(description="try11 F-M2 multi-feeder sweep")
    parser.add_argument("--feeders", type=str, nargs="+", default=list(FEEDERS))
    parser.add_argument("--scales", type=int, nargs="+", default=[50, 200, 1000])
    parser.add_argument("--traces", type=str, nargs="+", default=list(TRACES))
    parser.add_argument("--methods", type=str, nargs="+", default=list(METHODS))
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    cells = build_cell_list(
        tuple(args.feeders), tuple(args.scales),
        tuple(args.traces), tuple(args.methods),
        tuple(args.seeds),
    )
    n = len(cells)
    print(f"[try11 F-M2] cells = {n}, workers = {args.n_workers}")

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_cell(c) for i, c in enumerate(cells)
                   if (print(f"  [{i+1}/{n}] {c}") or True)]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_cell, cells)):
                records.append(rec)
                if (i + 1) % 20 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    rate = (i + 1) / elapsed
                    eta = (n - (i + 1)) / rate if rate > 0 else 0
                    print(f"  [{i+1}/{n}] elapsed {elapsed:.0f}s, rate {rate:.2f}/s, ETA {eta:.0f}s")

    total_elapsed = time.perf_counter() - started
    print(f"[try11 F-M2] total {total_elapsed:.0f}s for {n} cells")

    output_dir = (
        Path(args.output) if args.output else
        Path(__file__).resolve().parent.parent / "results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / "try11_FM2_results.json"
    out_csv = output_dir / "FM2_per_condition_metrics.csv"

    out = {
        "records": records,
        "config": {
            "feeders": list(args.feeders),
            "scales": list(args.scales),
            "traces": list(args.traces),
            "methods": list(args.methods),
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
            "feeder", "scale", "trace_id", "method", "method_label", "seed",
            "design_cost", "n_standby", "design_solve_time_s", "elapsed_s",
            "infeasible", "infeasibility_reason", "error", *metric_names,
        ])
        for r in records:
            w.writerow(
                [r.get("feeder"), r.get("scale"), r.get("trace_id"),
                 r.get("method"), r.get("method_label"), r.get("seed"),
                 r.get("design_cost"), r.get("n_standby"),
                 r.get("design_solve_time_s"), r.get("elapsed_s"),
                 r.get("infeasible", False),
                 r.get("infeasibility_reason", "") or "",
                 r.get("error", ""),
                 *(r.get("metrics", {}).get(n, "") for n in metric_names)]
            )
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
