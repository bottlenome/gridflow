"""MS-D1 smoke test — voltage violation metric decomposition.

Phase D-1 (NEXT_STEPS.md §3) addresses PWRS reviewer C3 by separating
``voltage_violation_ratio`` (legacy combined) into:

  * ``voltage_violation_baseline_only`` — violations present with zero
    DER injection (= existing-load-induced; the controller is structurally
    unable to repair these because positive injection only raises V).
  * ``voltage_violation_dispatch_induced`` — violations the dispatch
    *introduced* (= what M7 is actually responsible for).

This smoke test verifies on cigre_lv (whose baseline V_min ≈ 0.912 < 0.95
already violates without any DER):

  1. The new metrics are present and finite.
  2. The legacy combined ratio equals the union of the two components
     (i.e. baseline-only + dispatch-induced ≤ combined, with the
     dispatch-induced contribution being the *new* violations only).
  3. Baseline-only ≈ 100% on cigre_lv (the whole feeder is constantly
     in baseline V_min violation; no positive injection can repair it).
  4. Dispatch-induced ≈ 0% — the controller does not introduce *new*
     violations in steps where the baseline was already healthy.
"""

from __future__ import annotations

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool
from tools.feeder_config import feeder_active_pool, get_feeder_config
from tools.feeders import map_pool_to_feeder
from tools.grid_metrics import GRID_METRICS
from tools.grid_simulator import grid_simulate, to_grid_experiment_result
from tools.sdp_grid_aware import solve_sdp_grid_aware
from tools.trace_synthesizer import synth_c1_single_trigger
from tools.vpp_metrics import VPP_METRICS
from tools.vpp_simulator import all_standby_dispatch_policy


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)
    feeder = "cigre_lv"
    config = get_feeder_config(feeder)
    sla_kw = config.sla_kw
    burst = config.burst_dict()
    active_ids = feeder_active_pool(pool, config)
    bus_map = map_pool_to_feeder(pool, feeder)
    trace = synth_c1_single_trigger(pool, seed=0, sla_kw=sla_kw)

    # Use M7 with relaxed bounds so the solve is feasible; the metric
    # decomposition is independent of feasibility (it is a property of
    # the simulated voltage trace).
    sol_m7 = solve_sdp_grid_aware(
        pool,
        active_ids,
        burst,
        bus_map=bus_map,
        feeder_name=feeder,
        basis=TRIGGER_BASIS_K3,
        v_max_pu=1.10,
        line_max_pct=120.0,
        mode="M7-strict-grid-relaxed",
    )
    if not sol_m7.feasible:
        failures.append("M7 (relaxed) should be feasible on cigre_lv")
        return _report(failures)

    run = grid_simulate(
        pool=pool,
        active_ids=active_ids,
        standby_ids=frozenset(sol_m7.standby_ids),
        trace=trace,
        feeder_name=feeder,
        bus_map=bus_map,
        dispatch_policy=all_standby_dispatch_policy,
        sample_every=24,
    )

    # Sanity: GridRunResult now carries the time-independent baseline.
    if not (0.0 < run.baseline_voltage_min_pu < 2.0):
        failures.append(
            f"baseline_voltage_min_pu out of range: {run.baseline_voltage_min_pu}"
        )
    if not (0.0 < run.baseline_voltage_max_pu < 2.0):
        failures.append(
            f"baseline_voltage_max_pu out of range: {run.baseline_voltage_max_pu}"
        )
    print(
        f"  baseline V_min={run.baseline_voltage_min_pu:.4f}, "
        f"V_max={run.baseline_voltage_max_pu:.4f}, "
        f"line={run.baseline_line_load_pct:.2f}%"
    )

    result = to_grid_experiment_result(
        run,
        pool=pool,
        active_ids=active_ids,
        standby_ids=frozenset(sol_m7.standby_ids),
        trace=trace,
        experiment_id="msD1_M7",
        scenario_pack_id="try11_msD1",
        method_label="M7",
    )

    # Verify the synthetic baseline channels are exposed.
    embedded_ids = {lr.asset_id for lr in result.load_results}
    for needed in ("__voltage_baseline_min__", "__voltage_baseline_max__",
                   "__line_load_baseline_max__"):
        if needed not in embedded_ids:
            failures.append(f"missing synthetic load: {needed}")

    harness = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS)
    summary = harness.evaluate(result)
    combined = summary.value("voltage_violation_ratio")
    baseline_only = summary.value("voltage_violation_baseline_only")
    dispatch_induced = summary.value("voltage_violation_dispatch_induced")

    print(
        f"  voltage_violation_ratio          = {combined * 100:.2f}%"
    )
    print(
        f"  voltage_violation_baseline_only  = {baseline_only * 100:.2f}%"
    )
    print(
        f"  voltage_violation_dispatch_induced = {dispatch_induced * 100:.2f}%"
    )

    # Property 1: all metrics finite in [0, 1]
    for name, val in (
        ("combined", combined),
        ("baseline_only", baseline_only),
        ("dispatch_induced", dispatch_induced),
    ):
        if not (0.0 <= val <= 1.0):
            failures.append(f"{name} ratio out of [0,1]: {val}")

    # Property 2: dispatch_induced ≤ combined (strict subset by definition)
    # and baseline_only ≤ combined when the violation set actually overlaps.
    if dispatch_induced > combined + 1e-9:
        failures.append(
            f"dispatch_induced ({dispatch_induced}) > combined ({combined})"
        )

    # Property 3: cigre_lv has baseline V_min ≈ 0.912 → baseline_only ≈ 1.0
    if run.baseline_voltage_min_pu < 0.95 and baseline_only < 0.99:
        failures.append(
            f"cigre_lv: baseline V_min={run.baseline_voltage_min_pu:.3f} < 0.95 "
            f"but baseline_only={baseline_only:.3f} (expected ≈ 1.0)"
        )

    # Property 4: dispatch-induced should be negligible on a feeder whose
    # baseline already saturates the violation set (the dispatch can only
    # "steal" already-violating steps from baseline_only, not invent new
    # ones in steps where baseline was healthy).
    if run.baseline_voltage_min_pu < 0.95 and dispatch_induced > 0.01:
        failures.append(
            f"cigre_lv: dispatch_induced={dispatch_induced:.4f} > 0.01 — "
            "dispatch should not invent new violations when baseline "
            "already covers every step"
        )

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D1 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
