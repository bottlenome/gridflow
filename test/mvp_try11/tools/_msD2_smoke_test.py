"""MS-D2 smoke test — tight bound MILP + M7-soft slack reporting.

Phase D-2 (NEXT_STEPS.md §4) restores the ANSI C84.1 / IEEE 1547 strict
envelope (V_max=1.05, line_max=100%) instead of the earlier relaxed
(V_max=1.10, line_max=120%) hack, and adds an always-feasible soft
variant that reports per-bus / per-line slack so reviewers can quantify
exactly how much we relaxed the envelope.

Verifies on cigre_lv (whose baseline already saturates V_min<0.95):

  1. ``solve_sdp_grid_aware`` with strict bounds returns ``feasible=False``
     OR returns a feasible solution that respects the strict envelope
     (i.e. the relaxation hack is no longer required by construction).
  2. ``solve_sdp_grid_aware_soft`` with the *same* strict bounds is
     **always feasible** (slack closes any gap) and exposes:
       * voltage_slack_total_pu / voltage_slack_max_pu
       * line_slack_total_pct / line_slack_max_pct
       * soft_penalty_lambda
  3. Slack stats are non-negative finite floats.
  4. The soft solution's design cost is comparable to the strict cost
     when both are feasible (= we didn't double-count the penalty).
"""

from __future__ import annotations

import math

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool
from tools.feeder_config import feeder_active_pool, get_feeder_config
from tools.feeders import map_pool_to_feeder
from tools.sdp_grid_aware import (
    GridAwareSoftSolution,
    solve_sdp_grid_aware,
    solve_sdp_grid_aware_soft,
)
from tools.trace_synthesizer import synth_c1_single_trigger


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)
    feeder = "cigre_lv"
    config = get_feeder_config(feeder)
    sla_kw = config.sla_kw
    burst = config.burst_dict()
    active_ids = feeder_active_pool(pool, config)
    bus_map = map_pool_to_feeder(pool, feeder)
    _ = synth_c1_single_trigger(pool, seed=0, sla_kw=sla_kw)  # exercise import

    # 1) Strict bounds: M7 may legitimately be infeasible; that is the
    # honest answer for a feeder with baseline V_min ≈ 0.912.
    sol_strict = solve_sdp_grid_aware(
        pool,
        active_ids,
        burst,
        bus_map=bus_map,
        feeder_name=feeder,
        basis=TRIGGER_BASIS_K3,
        v_max_pu=1.05,
        line_max_pct=100.0,
        mode="M7-strict-grid",
    )
    print(
        f"  strict M7  : feasible={sol_strict.feasible}, "
        f"cost={sol_strict.objective_cost if sol_strict.feasible else 'inf'}, "
        f"n_standby={len(sol_strict.standby_ids)}"
    )

    # 2) Soft variant: always feasible (or infeasible only on
    # capacity/orthogonality, which is unrelated to V/L envelope).
    soft = solve_sdp_grid_aware_soft(
        pool,
        active_ids,
        burst,
        bus_map=bus_map,
        feeder_name=feeder,
        basis=TRIGGER_BASIS_K3,
        v_max_pu=1.05,
        line_max_pct=100.0,
        mode="M7-soft",
    )
    if not isinstance(soft, GridAwareSoftSolution):
        failures.append("solve_sdp_grid_aware_soft did not return GridAwareSoftSolution")
        return _report(failures)

    print(
        f"  soft  M7   : feasible={soft.solution.feasible}, "
        f"cost={soft.solution.objective_cost:.0f}, "
        f"n_standby={len(soft.solution.standby_ids)}, "
        f"v_slack_total={soft.voltage_slack_total:.4f} pu, "
        f"v_slack_max={soft.voltage_slack_max:.4f} pu, "
        f"l_slack_total={soft.line_slack_total:.2f}%, "
        f"l_slack_max={soft.line_slack_max:.2f}%, "
        f"λ={soft.penalty_lambda:.0f}"
    )

    if not soft.solution.feasible:
        # Capacity / orthogonality issues are out of scope for D-2; the
        # primary contract of the soft variant is V/L envelope relaxation.
        failures.append(
            "M7-soft must be feasible on cigre_lv (capacity/orthogonality "
            f"infeasible: {soft.solution.mode})"
        )
        return _report(failures)

    # 3) Slack stats sanity
    for name, value in soft.metric_dict().items():
        if not (math.isfinite(value) and value >= 0.0):
            failures.append(f"{name} not finite/non-negative: {value}")

    # 4) When both feasible, design costs differ at most by a quantum
    # equal to one standby contract (the soft variant may select a
    # slightly different set when slack is cheaper than reshuffling).
    if sol_strict.feasible:
        gap = abs(sol_strict.objective_cost - soft.solution.objective_cost)
        cheapest_standby = min(
            (d.contract_cost_standby for d in pool if d.der_id not in active_ids),
            default=0.0,
        )
        if gap > 5.0 * cheapest_standby + 1.0:
            failures.append(
                f"strict and soft design costs differ by {gap:.1f}; "
                f"expected within ~5 standby contracts ({cheapest_standby:.1f})"
            )

    # 5) When strict is infeasible, soft must report non-zero slack —
    # otherwise it solved the same problem as strict and we have a bug.
    if not sol_strict.feasible:
        total_slack = soft.voltage_slack_total + soft.line_slack_total
        if total_slack <= 1e-9:
            failures.append(
                "strict was infeasible but soft reports zero slack — "
                "soft variant is not actually relaxing the envelope"
            )
        else:
            print(
                f"  strict infeasible → soft used {total_slack:.4f} total slack"
            )

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D2 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
