"""MS-A2 smoke test — grid-aware simulator end-to-end on each feeder."""

from __future__ import annotations

import time

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool
from tools.feeders import FEEDER_NAMES, map_pool_to_feeder
from tools.grid_metrics import GRID_METRICS
from tools.grid_simulator import grid_simulate, to_grid_experiment_result
from tools.sdp_optimizer import solve_sdp_strict
from tools.trace_synthesizer import synth_c1_single_trigger
from tools.vpp_metrics import VPP_METRICS


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)
    active_ids = frozenset(d.der_id for d in pool[:60] if d.der_type == "residential_ev")

    burst = {"commute": 1500.0, "weather": 500.0, "market": 500.0}
    sol = solve_sdp_strict(pool, active_ids, burst, basis=TRIGGER_BASIS_K3)
    standby_ids = frozenset(sol.standby_ids)
    trace = synth_c1_single_trigger(pool, seed=0, sla_kw=1500.0)

    for name in FEEDER_NAMES:
        bus_map = map_pool_to_feeder(pool, name)

        t0 = time.perf_counter()
        run = grid_simulate(
            pool=pool,
            active_ids=active_ids,
            standby_ids=standby_ids,
            trace=trace,
            feeder_name=name,
            bus_map=bus_map,
            sample_every=24,  # coarser for smoke test
        )
        elapsed = time.perf_counter() - t0

        if run.n_steps != trace.n_steps:
            failures.append(f"{name}: n_steps mismatch")
        if run.n_pf_runs == 0:
            failures.append(f"{name}: zero PF runs")
        if run.feeder_name != name:
            failures.append(f"{name}: feeder_name mismatch")
        if any(v < 0 or v > 2 for v in run.voltage_min_pu_sampled):
            failures.append(f"{name}: voltage out of [0,2]")
        if any(ll < 0 for ll in run.line_max_load_pct_sampled):
            failures.append(f"{name}: negative line load")

        # ExperimentResult wrapping + metrics
        result = to_grid_experiment_result(
            run, pool=pool, active_ids=active_ids, standby_ids=standby_ids,
            trace=trace,
            experiment_id=f"msA2_{name}",
            scenario_pack_id="try11_msA2",
            method_label="M1",
        )
        harness = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS)
        summary = harness.evaluate(result)
        v_viol = summary.value("voltage_violation_ratio")
        line_overload = summary.value("line_overload_ratio")
        sla_viol = summary.value("sla_violation_ratio")

        if not (0.0 <= v_viol <= 1.0):
            failures.append(f"{name}: voltage_violation_ratio out of [0,1]")
        if not (0.0 <= line_overload <= 1.0):
            failures.append(f"{name}: line_overload_ratio out of [0,1]")

        print(f"  {name}: n_pf={run.n_pf_runs}, sla_viol={sla_viol:.3f}, "
              f"v_viol={v_viol:.3f}, line_overload={line_overload:.3f}, "
              f"v_min={summary.value('min_voltage_pu'):.3f}, "
              f"v_max={summary.value('max_voltage_pu'):.3f}, "
              f"max_line={summary.value('max_line_load_pct'):.1f}%, "
              f"t={elapsed:.1f}s")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-A2 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
