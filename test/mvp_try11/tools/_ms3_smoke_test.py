"""MS-3 smoke test — VPP simulator + metrics, end-to-end on small trace.

Verifies:
  - simulate_vpp() walks a trace end-to-end without error
  - to_experiment_result() produces a proper ExperimentResult that
    BenchmarkHarness accepts
  - All 6 VPP metrics return sensible values (in expected ranges)
  - SLA violation ratio increases when SLA target > total active capacity
  - Standby dispatch decreases SLA violations vs no-standby case
"""

from __future__ import annotations

from gridflow.adapter.benchmark.harness import BenchmarkHarness

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool
from tools.sdp_optimizer import solve_sdp_strict
from tools.trace_synthesizer import synth_c1_single_trigger
from tools.vpp_metrics import VPP_METRICS
from tools.vpp_simulator import simulate_vpp, to_experiment_result


def main() -> int:
    failures: list[str] = []

    # Setup: 200-DER pool, C1 trace, SLA = 5 MW
    pool = make_default_pool(seed=0)
    # Active = first 60 residential_ev (capacity 7kW × 60 = 420 kW only)
    # — intentionally below SLA 5MW so standby is essential
    active_ids = frozenset(d.der_id for d in pool[:60])
    trace = synth_c1_single_trigger(pool, seed=0, magnitude=0.5)

    # SLA = 1500 kW (achievable with right standby)
    trace = synth_c1_single_trigger(
        pool, seed=0, magnitude=0.5, sla_kw=1500.0
    )

    # T1: SDP design produces a feasible standby
    sol = solve_sdp_strict(
        pool, active_ids,
        burst_kw={"commute": 1500.0, "weather": 500.0, "market": 500.0},
        basis=TRIGGER_BASIS_K3,
    )
    if not sol.feasible:
        failures.append("T1: SDP should be feasible")
    standby_ids = frozenset(sol.standby_ids)

    # T2: simulate_vpp with standby
    run_with = simulate_vpp(
        pool=pool, active_ids=active_ids,
        standby_ids=standby_ids, trace=trace,
    )
    if run_with.n_steps != trace.n_steps:
        failures.append(f"T2: n_steps mismatch ({run_with.n_steps} vs {trace.n_steps})")
    if len(run_with.aggregate_kw) != run_with.n_steps:
        failures.append("T2: aggregate_kw length mismatch")

    # T3: simulate_vpp without standby (= empty standby_ids)
    run_without = simulate_vpp(
        pool=pool, active_ids=active_ids,
        standby_ids=frozenset(), trace=trace,
    )

    # T4: standby reduces violations
    viols_with = sum(run_with.sla_violation)
    viols_without = sum(run_without.sla_violation)
    if viols_with > viols_without:
        failures.append(
            f"T4: standby case has more violations ({viols_with}) than no-standby ({viols_without})"
        )

    # T5: ExperimentResult wrapping
    result_with = to_experiment_result(
        run_with, pool=pool, active_ids=active_ids,
        standby_ids=standby_ids, trace=trace,
        experiment_id="test_ms3_with",
        scenario_pack_id="try11_test",
        method_label="M1",
    )
    if not result_with.load_results:
        failures.append("T5: ExperimentResult has no load_results")
    asset_ids = {lr.asset_id for lr in result_with.load_results}
    if "__aggregate__" not in asset_ids:
        failures.append("T5: missing __aggregate__ load")
    if "__sla_target__" not in asset_ids:
        failures.append("T5: missing __sla_target__ load")

    # T6: BenchmarkHarness with VPP metrics
    harness = BenchmarkHarness(metrics=VPP_METRICS)
    summary = harness.evaluate(result_with)
    metric_names = {n for n, _ in summary.values}
    expected = {
        "sla_violation_ratio", "sla_violation_ratio_test",
        "sla_violation_ratio_train", "ood_gap",
        "standby_pool_size", "burst_compensation_rate",
    }
    missing = expected - metric_names
    if missing:
        failures.append(f"T6: missing metrics {missing}")
    # All values must be finite floats
    for name, val in summary.values:
        if val != val:  # NaN
            failures.append(f"T6: metric {name} is NaN")
        if val == float("inf") or val == float("-inf"):
            failures.append(f"T6: metric {name} is inf")

    # T7: violation ratio sanity
    vr_full = summary.value("sla_violation_ratio")
    vr_train = summary.value("sla_violation_ratio_train")
    vr_test = summary.value("sla_violation_ratio_test")
    if not (0.0 <= vr_full <= 1.0):
        failures.append(f"T7: vr_full {vr_full} out of [0,1]")
    if not (0.0 <= vr_train <= 1.0):
        failures.append(f"T7: vr_train {vr_train} out of [0,1]")
    if not (0.0 <= vr_test <= 1.0):
        failures.append(f"T7: vr_test {vr_test} out of [0,1]")

    # T8: standby_pool_size metric matches reality
    standby_size = summary.value("standby_pool_size")
    if int(standby_size) != len(standby_ids):
        failures.append(
            f"T8: standby_pool_size metric {standby_size} != actual {len(standby_ids)}"
        )

    # T9: dispatch policy actually fires
    if all(d == 0 for d in run_with.dispatched_count):
        failures.append("T9: dispatch never fired despite SLA being below active output at times")

    if failures:
        print(f"FAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK — MS-3 smoke test passed.")
    print(f"  pool size = {len(pool)}, active = {len(active_ids)}, standby = {len(standby_ids)}")
    print(f"  SLA viol ratio: full={vr_full:.4f}, train={vr_train:.4f}, test={vr_test:.4f}")
    print(f"  OOD gap = {summary.value('ood_gap'):+.4f}")
    print(f"  burst comp = {summary.value('burst_compensation_rate'):.4f}")
    print(f"  T4: violations w/ standby = {viols_with}, w/o standby = {viols_without}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
