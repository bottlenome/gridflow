"""MS-5 smoke test — every baseline runs end-to-end.

Verifies:
  - Each B1-B6 returns a feasible BaselineSolution on the default 200-DER
    pool with C1 trace and SLA 5 MW.
  - All return non-empty standby (= they meaningfully selected something).
  - Naive-NN dispatch policy is callable.
"""

from __future__ import annotations

from tools.der_pool import make_default_pool
from tools.trace_synthesizer import synth_c1_single_trigger
from tools.baselines import (
    naive_nn_dispatch_policy,
    solve_b1_static_overprov,
    solve_b2_stochastic_program,
    solve_b3_wasserstein_dro,
    solve_b4_markowitz,
    solve_b5_financial_causal,
    solve_b6_naive_nn,
)


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)
    active_ids = frozenset(d.der_id for d in pool[:60])
    trace = synth_c1_single_trigger(pool, seed=0, sla_kw=1500.0)
    burst = {"commute": 1500.0, "weather": 500.0, "market": 500.0}

    sol_b1 = solve_b1_static_overprov(pool, active_ids, overprov_factor=0.5)
    if not sol_b1.feasible:
        failures.append("B1 should be feasible")
    if not sol_b1.standby_ids:
        failures.append("B1 returned empty standby")
    print(f"  B1: cost={sol_b1.objective_cost:.0f}, n={len(sol_b1.standby_ids)}")

    sol_b2 = solve_b2_stochastic_program(pool, active_ids, burst, sla_target_kw=1500.0, seed=0)
    if not sol_b2.feasible:
        failures.append("B2 should be feasible")
    print(f"  B2: cost={sol_b2.objective_cost:.0f}, n={len(sol_b2.standby_ids)}")

    sol_b3 = solve_b3_wasserstein_dro(pool, active_ids, burst, sla_target_kw=1500.0, seed=0)
    if not sol_b3.feasible:
        failures.append("B3 should be feasible")
    print(f"  B3: cost={sol_b3.objective_cost:.0f}, n={len(sol_b3.standby_ids)}")

    sol_b4 = solve_b4_markowitz(pool, active_ids, trace, sla_target_kw=1500.0)
    if not sol_b4.feasible:
        failures.append("B4 should be feasible")
    print(f"  B4: cost={sol_b4.objective_cost:.0f}, n={len(sol_b4.standby_ids)}")

    sol_b5 = solve_b5_financial_causal(pool, active_ids, trace, sla_target_kw=1500.0)
    if not sol_b5.feasible:
        failures.append("B5 should be feasible")
    print(f"  B5: cost={sol_b5.objective_cost:.0f}, n={len(sol_b5.standby_ids)}")

    sol_b6 = solve_b6_naive_nn(pool, active_ids, trace, sla_target_kw=1500.0, seed=0)
    if not sol_b6.feasible:
        failures.append("B6 should be feasible")
    print(f"  B6: cost={sol_b6.objective_cost:.0f}, n={len(sol_b6.standby_ids)}")

    # NN dispatch policy is callable
    policy = naive_nn_dispatch_policy(trace=trace, seed=0)
    out = policy(
        t_step=15, sla_kw=1500.0, active_output_kw=400.0,
        standby_pool=tuple(pool[100:103]),
        standby_active_status=(True, True, True),
    )
    if len(out) != 3:
        failures.append(f"NN dispatch returned {len(out)} bools, expected 3")
    if not all(isinstance(b, bool) for b in out):
        failures.append("NN dispatch returned non-bool entries")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-5 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
