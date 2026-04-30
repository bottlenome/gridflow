"""Phase 1 experiment runner — 12 conditions × 6 traces = 72 child experiments.

Spec: ``test/mvp_try11/implementation_plan.md`` §8 (MS-7).

Each child experiment:
  1. Loads/synthesises a trace (C1-C6).
  2. Selects a method (M1-M6 SDP variants or B1-B6 baselines).
  3. Runs the method to get a standby DER set.
  4. Wraps result via ``vpp_simulator.simulate_vpp`` and
     ``to_experiment_result``.
  5. Evaluates ``VPP_METRICS`` via :class:`BenchmarkHarness`.
  6. Records (method, trace, metrics, timing) in a flat record list.

Output:
  * ``results/try11_results.json``  — full record dump
  * ``results/per_condition_metrics.csv`` — flat CSV view

The runner is single-process (sequential). Total runtime on the 200-DER
pool with 30-day, 5-min trace is ~minutes — gridflow's
``SweepOrchestrator`` could parallelise in Docker, but for a 72-cell
matrix the simplicity of sequential is preferred (CLAUDE.md §0.5.1: do
not over-engineer).
"""

from __future__ import annotations

import argparse
import csv
import json
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
    TRIGGER_BASIS_K2,
    TRIGGER_BASIS_K3,
    TRIGGER_BASIS_K4,
    make_default_pool,
)
from .sdp_optimizer import (
    solve_sdp_greedy,
    solve_sdp_soft,
    solve_sdp_strict,
    solve_sdp_tolerant,
)
from .trace_synthesizer import (
    perturb_pool_label_noise,
    synth_c1_single_trigger,
    synth_c2_extreme_burst,
    synth_c3_simultaneous,
    synth_c4_out_of_basis,
    synth_c5_frequency_shift,
    DEFAULT_SLA_TARGET_KW,
)
from .vpp_metrics import VPP_METRICS
from .vpp_simulator import (
    all_standby_dispatch_policy,
    simulate_vpp,
    to_experiment_result,
)


METHODS = ("M1", "M2a", "M2b", "M2c", "M3b", "M3c", "M4b", "M5", "M6",
           "B1", "B2", "B3", "B4", "B5", "B6")  # 15 conditions (M2b == M1 functionally; kept for traceability)
# Implementation plan called for 12: M1-M6 (6) + B1-B6 (6).
# Here we run a slightly larger set including M2a (K=2) and M2c (K=4)
# explicitly so the basis-dimensionality study (M2) is its own column.

TRACES = ("C1", "C2", "C3", "C4", "C5", "C6")


def _make_active_pool(pool: tuple, sla_kw: float) -> frozenset[str]:
    """Active pool: 60 residential_ev (commute-exposed).

    Total active capacity ≈ 60 × 7 = 420 kW, which is BELOW the SLA target
    (1500 kW). This intentionally creates a gap that the standby pool MUST
    fill. The size of that gap, and the design strategy for filling it,
    is exactly what differentiates SDP from baselines.

    All active members are residential_ev so they share the commute trigger
    exposure — making the trigger-orthogonality argument well-posed
    (active spans the commute axis; standby must avoid it).
    """
    ev_pool = [d for d in pool if d.der_type == "residential_ev"]
    return frozenset(d.der_id for d in ev_pool[:60])


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
        # C6 = C1 trace + label noise applied before method sees pool;
        # handled by the method-runner.
        return synth_c1_single_trigger(pool, seed=seed, sla_kw=sla_kw)
    raise ValueError(f"unknown trace: {trace_id}")


def _solve(method: str, pool, active_ids, trace, *, burst, sla_kw, seed):
    """Dispatch to the right solver, returning (standby_ids, design_cost, label, dispatch_policy)."""
    if method == "M1":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M1")
        return sol.standby_ids, sol.objective_cost, "M1", all_standby_dispatch_policy
    if method == "M2a":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K2, mode="M2a-K2")
        return sol.standby_ids, sol.objective_cost, "M2a-K2", all_standby_dispatch_policy
    if method == "M2b":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M2b-K3")
        return sol.standby_ids, sol.objective_cost, "M2b-K3", all_standby_dispatch_policy
    if method == "M2c":
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K4, mode="M2c-K4")
        return sol.standby_ids, sol.objective_cost, "M2c-K4", all_standby_dispatch_policy
    if method == "M3b":
        sol = solve_sdp_soft(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M3b-soft")
        return sol.standby_ids, sol.objective_cost, "M3b-soft", all_standby_dispatch_policy
    if method == "M3c":
        sol = solve_sdp_tolerant(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M3c-tolerant")
        return sol.standby_ids, sol.objective_cost, "M3c-tolerant", all_standby_dispatch_policy
    if method == "M4b":
        sol = solve_sdp_greedy(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M4b-greedy")
        return sol.standby_ids, sol.objective_cost, "M4b-greedy", all_standby_dispatch_policy
    if method == "M5":
        # SDP M1 design + NN dispatch
        sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M5-NN-dispatch")
        policy = naive_nn_dispatch_policy(trace=trace, seed=seed)
        return sol.standby_ids, sol.objective_cost, "M5-NN-dispatch", policy
    if method == "M6":
        # SDP M1 on perturbed (label-noise 10%) pool
        perturbed_pool = perturb_pool_label_noise(pool, noise_rate=0.10, seed=seed + 99)
        sol = solve_sdp_strict(perturbed_pool, active_ids, burst, basis=TRIGGER_BASIS_K3, mode="M6-noise10")
        return sol.standby_ids, sol.objective_cost, "M6-noise10", all_standby_dispatch_policy
    if method == "B1":
        sol = solve_b1_static_overprov(pool, active_ids, overprov_factor=0.30)
        return sol.standby_ids, sol.objective_cost, "B1-static_overprov", all_standby_dispatch_policy
    if method == "B2":
        sol = solve_b2_stochastic_program(pool, active_ids, burst, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B2-stochastic_program", all_standby_dispatch_policy
    if method == "B3":
        sol = solve_b3_wasserstein_dro(pool, active_ids, burst, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B3-wasserstein_dro", all_standby_dispatch_policy
    if method == "B4":
        sol = solve_b4_markowitz(pool, active_ids, trace, sla_target_kw=sla_kw)
        return sol.standby_ids, sol.objective_cost, "B4-markowitz", all_standby_dispatch_policy
    if method == "B5":
        sol = solve_b5_financial_causal(pool, active_ids, trace, sla_target_kw=sla_kw)
        return sol.standby_ids, sol.objective_cost, "B5-financial_causal", all_standby_dispatch_policy
    if method == "B6":
        sol = solve_b6_naive_nn(pool, active_ids, trace, sla_target_kw=sla_kw, seed=seed)
        return sol.standby_ids, sol.objective_cost, "B6-naive_nn", all_standby_dispatch_policy
    raise ValueError(f"unknown method: {method}")


def run_one(
    method: str,
    trace_id: str,
    *,
    base_pool,
    seed: int,
    sla_kw: float,
    burst: dict,
) -> dict:
    """Run a single (method, trace) cell end-to-end and return a record."""
    started = time.perf_counter()

    # C6: apply label noise to the pool before the method sees it
    if trace_id == "C6":
        pool = perturb_pool_label_noise(base_pool, noise_rate=0.10, seed=seed + 11)
    else:
        pool = base_pool

    active_ids = _make_active_pool(pool, sla_kw)
    trace = _make_trace(trace_id, pool, seed, sla_kw)

    standby_ids, design_cost, method_label, dispatch_policy = _solve(
        method, pool, active_ids, trace,
        burst=burst, sla_kw=sla_kw, seed=seed,
    )

    standby_set = frozenset(standby_ids)
    run = simulate_vpp(
        pool=pool, active_ids=active_ids, standby_ids=standby_set,
        trace=trace, dispatch_policy=dispatch_policy,
    )
    result = to_experiment_result(
        run, pool=pool, active_ids=active_ids, standby_ids=standby_set,
        trace=trace,
        experiment_id=f"{method}_{trace_id}_seed{seed}",
        scenario_pack_id="try11_phase1",
        method_label=method_label,
    )
    harness = BenchmarkHarness(metrics=VPP_METRICS)
    summary = harness.evaluate(result)

    elapsed = time.perf_counter() - started
    return {
        "method": method,
        "method_label": method_label,
        "trace_id": trace_id,
        "seed": seed,
        "design_cost": design_cost,
        "n_standby": len(standby_ids),
        "elapsed_s": round(elapsed, 3),
        "metrics": dict(summary.values),
    }


def run_full_sweep(
    *,
    seeds: tuple[int, ...] = (0, 1, 2),
    sla_kw: float = 1500.0,  # active pool of 60 EVs (420 kW) cannot meet
                             # alone — standby is essential; differentiation
                             # between methods becomes meaningful
    methods: tuple[str, ...] = METHODS,
    traces: tuple[str, ...] = TRACES,
    output_dir: Path | None = None,
) -> list[dict]:
    """Run methods × traces × seeds and return the full record list."""
    output_dir = output_dir or Path(__file__).resolve().parent.parent / "results"
    output_dir.mkdir(parents=True, exist_ok=True)

    base_pool = make_default_pool(seed=0)
    # Burst sizes (kW) — represent the maximum compensable amount per
    # trigger axis the SDP must reserve for. Commute is largest because
    # active pool is 60 EVs all commute-exposed; the SDP must reserve
    # standby capacity ~ SLA worth of orthogonal-to-commute capacity.
    burst = {
        "commute": 1500.0,   # full SLA recovery if all 60 EVs churn
        "weather": 500.0,
        "market": 500.0,
        "comm_fault": 300.0,
    }

    records: list[dict] = []
    started = time.perf_counter()
    n_total = len(methods) * len(traces) * len(seeds)
    n_done = 0
    for method in methods:
        for trace_id in traces:
            for seed in seeds:
                rec = run_one(
                    method, trace_id,
                    base_pool=base_pool, seed=seed,
                    sla_kw=sla_kw, burst=burst,
                )
                records.append(rec)
                n_done += 1
                print(
                    f"  [{n_done:>3}/{n_total}] {method:>4} × {trace_id} seed={seed}: "
                    f"violation={rec['metrics']['sla_violation_ratio']:.3f}, "
                    f"cost={rec['design_cost']:.0f}, t={rec['elapsed_s']:.1f}s"
                )
    total_elapsed = time.perf_counter() - started
    print(f"\nTotal elapsed: {total_elapsed:.1f}s for {n_total} cells")

    out = {
        "records": records,
        "config": {
            "seeds": list(seeds),
            "methods": list(methods),
            "traces": list(traces),
            "sla_kw": sla_kw,
            "burst_kw": burst,
        },
        "elapsed_s": round(total_elapsed, 1),
    }
    (output_dir / "try11_results.json").write_text(
        json.dumps(out, indent=2, sort_keys=True), encoding="utf-8"
    )
    # Flat CSV
    csv_path = output_dir / "per_condition_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        all_metric_names = sorted({m for r in records for m in r["metrics"]})
        writer.writerow(["method", "method_label", "trace_id", "seed",
                         "design_cost", "n_standby", "elapsed_s", *all_metric_names])
        for r in records:
            writer.writerow(
                [r["method"], r["method_label"], r["trace_id"], r["seed"],
                 r["design_cost"], r["n_standby"], r["elapsed_s"],
                 *(r["metrics"].get(n, "") for n in all_metric_names)]
            )
    print(f"Wrote {output_dir / 'try11_results.json'}")
    print(f"Wrote {csv_path}")
    return records


def main() -> int:
    parser = argparse.ArgumentParser(description="try11 Phase 1 sweep runner")
    parser.add_argument("--seeds", type=int, nargs="+", default=[0, 1, 2])
    parser.add_argument("--methods", type=str, nargs="+", default=list(METHODS))
    parser.add_argument("--traces", type=str, nargs="+", default=list(TRACES))
    parser.add_argument("--sla-kw", type=float, default=1500.0)
    args = parser.parse_args()
    run_full_sweep(
        seeds=tuple(args.seeds),
        methods=tuple(args.methods),
        traces=tuple(args.traces),
        sla_kw=args.sla_kw,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
