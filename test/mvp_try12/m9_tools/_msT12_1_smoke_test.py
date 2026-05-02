"""MS-T12-1 smoke test — solve_sdp_bayes_robust (M9) basic behaviour.

Phase 1 MS-1. Verifies:

  1. Bayes posterior π = ε p / (ε p + (1-ε)(1-p)) computes correctly:
       (ε=0.05, p=0.95) → 0.500
       (ε=0.05, p=0.05) → 0.0028
       (ε=0.10, p=0.50) → 0.100
  2. M9 returns a feasible solution on a small case (try11 default pool,
     kerber_dorf at α=0.50) under a reasonable θ.
  3. M9's expected-loss-per-axis is ≤ θ_k for every axis ∈ E(A) (= the
     new constraint is binding / honoured).
  4. M9 vs M1 (try11 solve_sdp_strict) on the SAME input:
       * M9 cost ≥ M1 cost (extra constraint can only raise cost)
       * M9's selected DERs have at most as many high-prior label-flipped
         outliers as M1's (= M9 avoids the selection bias try11 N-2 found)
  5. M9 with very tight θ → infeasible (sanity that the constraint binds);
     M9 with very loose θ → equivalent to M1 (= constraint inactive).
"""

from __future__ import annotations

import sys
from pathlib import Path

# Add try11's directory to path so its `tools.*` package resolves.
_HERE = Path(__file__).resolve().parent  # = try12/m9_tools
_TRY11 = _HERE.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

# try11 reuse (= shared infrastructure per implementation_plan §7)
from tools.der_pool import (  # noqa: E402
    TRIGGER_BASIS_K3,
    make_default_pool,
    project_exposure,
)
from tools.feeder_config import feeder_active_pool, get_feeder_config  # noqa: E402
from tools.sdp_optimizer import solve_sdp_strict  # noqa: E402

# try12 contribution
from m9_tools.sdp_bayes_robust import (  # noqa: E402
    DEFAULT_PRIOR_BY_TYPE_AXIS,
    bayes_posterior,
    solve_sdp_bayes_robust,
)


def main() -> int:
    failures: list[str] = []

    # ------ (1) Bayes posterior arithmetic
    cases = [
        (0.05, 0.95, 0.500),
        (0.05, 0.05, 0.05 * 0.05 / (0.05 * 0.05 + 0.95 * 0.95)),
        (0.10, 0.50, 0.100),
        (0.0, 0.95, 0.0),
        (1.0, 0.95, 1.0),
    ]
    for eps, p, expected in cases:
        got = bayes_posterior(eps, p)
        if abs(got - expected) > 1e-9:
            failures.append(
                f"bayes_posterior(ε={eps}, p={p}) = {got}, expected {expected}"
            )
    if failures:
        return _report(failures)
    print("  ✓ Bayes posterior arithmetic checks out (5 cases)")

    # ------ (2) M9 feasibility on a real case
    pool = make_default_pool(seed=0)
    config = get_feeder_config("kerber_dorf")
    active_ids = feeder_active_pool(pool, config)
    burst = config.burst_dict()

    sol_m9 = solve_sdp_bayes_robust(
        pool, active_ids, burst,
        basis=TRIGGER_BASIS_K3,
        epsilon=0.05,
        expected_loss_threshold_fraction=0.05,  # θ_k = 5% × B_k
        mode="M9-bayes-robust",
    )
    if not sol_m9.feasible:
        failures.append("M9 should be feasible on kerber_dorf at default α with θ=0.05·B_k")
        return _report(failures)
    print(
        f"  ✓ M9 feasible: cost=¥{sol_m9.objective_cost:.0f}, "
        f"|S|={len(sol_m9.standby_ids)}"
    )

    # ------ (3) Expected-loss constraint honoured
    theta = dict(sol_m9.threshold_per_axis)
    for ax, mu in sol_m9.expected_loss_per_axis:
        if mu > theta[ax] + 1e-6:
            failures.append(
                f"axis {ax}: μ_k={mu:.4f} > θ_k={theta[ax]:.4f} "
                f"(constraint violated)"
            )
        else:
            print(
                f"    axis {ax}: μ_k={mu:.4f} kW ≤ θ_k={theta[ax]:.4f} kW ✓"
            )

    # ------ (4) M9 vs M1: cost comparison + selection bias check
    sol_m1 = solve_sdp_strict(
        pool, active_ids, burst,
        basis=TRIGGER_BASIS_K3,
        mode="M1",
    )
    if not sol_m1.feasible:
        failures.append("M1 should be feasible on the same input")
        return _report(failures)

    print(
        f"  M1 cost=¥{sol_m1.objective_cost:.0f} (|S|={len(sol_m1.standby_ids)}), "
        f"M9 cost=¥{sol_m9.objective_cost:.0f}"
    )

    if sol_m9.objective_cost + 1e-6 < sol_m1.objective_cost:
        failures.append(
            f"M9 cost ¥{sol_m9.objective_cost:.0f} < M1 cost "
            f"¥{sol_m1.objective_cost:.0f}; extra constraint should not lower cost"
        )

    # Count "high-prior label-flipped outliers" — DERs whose default exposure
    # to some active-axis is True (= prior 0.95) but observed is False.
    # M9 should picks fewer / no such outliers.
    pool_by_id = {d.der_id: d for d in pool}
    exposed_active = set()
    for d in pool:
        if d.der_id in active_ids:
            for k, ax in enumerate(TRIGGER_BASIS_K3):
                if d.trigger_exposure[
                    {"commute": 0, "weather": 1, "market": 2, "comm_fault": 3}[ax]
                ]:
                    exposed_active.add(ax)

    def _outlier_count(standby_ids: tuple[str, ...]) -> int:
        """Count picks whose prior on some exposed-active axis is high (≥ 0.5)
        and whose observed e_jk = 0 — i.e. label-flipped statistical outliers
        on the active-exposed axes.
        """
        count = 0
        for did in standby_ids:
            d = pool_by_id[did]
            obs = project_exposure(d, TRIGGER_BASIS_K3)
            for k, ax in enumerate(TRIGGER_BASIS_K3):
                if ax not in exposed_active:
                    continue
                p = DEFAULT_PRIOR_BY_TYPE_AXIS.get((d.der_type, ax), 0.05)
                if p >= 0.5 and not obs[k]:
                    count += 1
                    break  # count once per DER even if multi-axis flip
        return count

    n_out_m1 = _outlier_count(sol_m1.standby_ids)
    n_out_m9 = _outlier_count(sol_m9.standby_ids)
    print(
        f"  high-prior label-outlier picks: M1={n_out_m1}/{len(sol_m1.standby_ids)}, "
        f"M9={n_out_m9}/{len(sol_m9.standby_ids)}"
    )
    if n_out_m9 > n_out_m1:
        failures.append(
            f"M9 picked MORE outliers ({n_out_m9}) than M1 ({n_out_m1}); "
            "the new constraint should reduce or maintain outlier count"
        )

    # ------ (5) Tight / loose θ sanity
    sol_tight = solve_sdp_bayes_robust(
        pool, active_ids, burst,
        basis=TRIGGER_BASIS_K3,
        epsilon=0.05,
        expected_loss_threshold_fraction=0.0,  # θ = 0 (impossible to meet
                                               # except via zero standby
                                               # capacity, which violates
                                               # capacity coverage)
        mode="M9-tight",
    )
    if sol_tight.feasible:
        # If feasible at θ=0, every selected DER has π=0 on every axis. Check.
        all_zero = all(
            mu < 1e-9 for _, mu in sol_tight.expected_loss_per_axis
        )
        if not all_zero:
            failures.append(
                f"M9 with θ=0 is feasible but expected-loss > 0: "
                f"{sol_tight.expected_loss_per_axis}"
            )
        else:
            print("  ✓ M9 with θ=0: feasible only if all selected π=0 (utility-only mix)")
    else:
        print("  ✓ M9 with θ=0: infeasible (= constraint truly binds)")

    sol_loose = solve_sdp_bayes_robust(
        pool, active_ids, burst,
        basis=TRIGGER_BASIS_K3,
        epsilon=0.05,
        expected_loss_threshold_fraction=10.0,  # θ = 10× B_k = enormous
        mode="M9-loose",
    )
    if not sol_loose.feasible:
        failures.append("M9 with very loose θ should reduce to M1's feasible set")
    elif sol_loose.objective_cost > sol_m1.objective_cost + 1e-6:
        failures.append(
            f"M9-loose cost ¥{sol_loose.objective_cost:.0f} > M1 cost "
            f"¥{sol_m1.objective_cost:.0f}; loose θ should match M1"
        )
    else:
        print(
            f"  ✓ M9 with very loose θ: cost ¥{sol_loose.objective_cost:.0f} "
            f"≈ M1 cost ¥{sol_m1.objective_cost:.0f}"
        )

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-T12-1 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
