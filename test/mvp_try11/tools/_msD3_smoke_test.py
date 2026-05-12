"""MS-D3 smoke test — joint active+standby MILP (M8) on cigre_lv.

Phase D-3 (NEXT_STEPS.md §5) lifts the active pool from a deterministic
``feeder_active_pool`` pick to a binary decision variable, allowing the
MILP to (a) avoid placing active DERs at buses that crash V_min and
(b) pick injection-capable DERs whose placement raises baseline V_min
above 0.95 — i.e. structurally repair the cigre_lv issue D-1 surfaced.

Verifies:

  1. M8 returns a feasible solution on cigre_lv with the strict envelope
     (V_max=1.05, V_min=0.95, line_max=100%) — something M1 with the
     legacy fixed-active pool cannot guarantee.
  2. The active pool M8 picked satisfies the V_min ≥ 0.95 constraint by
     itself (i.e. ``worst_v_min_pu`` ≥ 0.95 within numerical tolerance).
  3. The active pool covers ≥ 70 % of the SLA target (capacity floor).
  4. Mutual exclusion holds: no DER appears in both active and standby.
  5. Trigger orthogonality holds: for every axis exposed by the chosen
     active pool, no chosen standby DER is exposed.

The test does NOT require M8 to be cheaper than M1 — joint optimisation
buys feasibility on a feeder that M1 could not satisfy. Cost rises
modestly because the active pool is constrained (was free of grid
considerations before).
"""

from __future__ import annotations

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool, project_exposure
from tools.feeder_config import get_feeder_config
from tools.feeders import map_pool_to_feeder
from tools.sdp_full_milp import solve_sdp_full


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)
    feeder = "cigre_lv"
    config = get_feeder_config(feeder)
    sla_kw = config.sla_kw
    burst = config.burst_dict()
    bus_map = map_pool_to_feeder(pool, feeder)

    sol = solve_sdp_full(
        pool,
        bus_map=bus_map,
        feeder_name=feeder,
        burst_kw=burst,
        sla_target_kw=sla_kw,
        basis=TRIGGER_BASIS_K3,
        v_max_pu=1.05,
        v_min_pu=0.95,
        line_max_pct=100.0,
        mode="M8-full",
    )

    print(
        f"  M8: feasible={sol.feasible}, "
        f"cost={sol.objective_cost:.0f} (active={sol.active_cost:.0f}, "
        f"standby={sol.standby_cost:.0f}), "
        f"|active|={len(sol.active_ids)}, |standby|={len(sol.standby_ids)}, "
        f"worst_v_min={sol.worst_v_min_pu:.4f}"
    )
    print(
        "  active exposed axes: "
        + ", ".join(
            f"{name}={'Y' if exposed else 'n'}"
            for name, exposed in zip(
                TRIGGER_BASIS_K3, sol.active_exposed_axes, strict=True
            )
        )
    )

    # 1) Feasibility
    if not sol.feasible:
        failures.append("M8 should be feasible on cigre_lv under strict envelope")
        return _report(failures)

    # 2) Active-only V_min must respect the constraint (numerical tol 1e-4)
    if sol.worst_v_min_pu < 0.95 - 1e-4:
        failures.append(
            f"worst_v_min_pu={sol.worst_v_min_pu:.5f} < 0.95 — V_min "
            "constraint should clear after M8 chose actives"
        )

    # 3) Active SLA capacity floor
    active_caps = {d.der_id: d.capacity_kw for d in pool}
    active_total_kw = sum(active_caps[d_id] for d_id in sol.active_ids)
    floor_kw = 0.70 * sla_kw
    if active_total_kw + 1e-6 < floor_kw:
        failures.append(
            f"active capacity {active_total_kw:.1f} kW < 70 % SLA floor "
            f"{floor_kw:.1f} kW"
        )
    else:
        print(
            f"  active capacity = {active_total_kw:.1f} kW "
            f"(SLA floor = {floor_kw:.1f} kW)"
        )

    # 4) Mutual exclusion
    overlap = set(sol.active_ids) & set(sol.standby_ids)
    if overlap:
        failures.append(f"DERs in both active and standby: {sorted(overlap)}")

    # 5) Trigger orthogonality
    pool_by_id = {d.der_id: d for d in pool}
    for k, axis in enumerate(TRIGGER_BASIS_K3):
        if not sol.active_exposed_axes[k]:
            continue
        offending = [
            sid
            for sid in sol.standby_ids
            if project_exposure(pool_by_id[sid], TRIGGER_BASIS_K3)[k]
        ]
        if offending:
            failures.append(
                f"orthogonality on axis '{axis}' violated by standby: "
                f"{offending[:3]}{'…' if len(offending) > 3 else ''}"
            )

    # 6) Standby coverage per (exposed) trigger
    for axis, kw_orth in sol.coverage_per_trigger:
        burst_kw = float(config.burst_dict().get(axis, 0.0))
        if burst_kw > 0 and kw_orth + 1e-6 < burst_kw:
            failures.append(
                f"standby capacity orthogonal to '{axis}' = {kw_orth:.1f} kW "
                f"< burst {burst_kw:.1f} kW"
            )

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D3 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
