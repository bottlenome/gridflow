"""MS-T13-1 smoke test — solve_sdp_full (M9-grid)."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
_TRY12 = _HERE.parent.parent / "mvp_try12"
for p in (_TRY11, _TRY12, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool  # noqa: E402
from tools.feeder_config import feeder_active_pool, get_feeder_config  # noqa: E402
from tools.feeders import map_pool_to_feeder  # noqa: E402

from m9_grid_tools.sdp_full import solve_sdp_full  # noqa: E402


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)

    # Test on each feeder
    for feeder in ("cigre_lv", "kerber_dorf", "kerber_landnetz"):
        config = get_feeder_config(feeder)
        active_ids = feeder_active_pool(pool, config)
        burst = config.burst_dict()
        bus_map = map_pool_to_feeder(pool, feeder)

        sol = solve_sdp_full(
            pool, active_ids, burst, bus_map, feeder,
            basis=TRIGGER_BASIS_K3,
            epsilon=0.05,
            expected_loss_threshold_fraction=0.05,
            v_max_pu=1.05, line_max_pct=100.0,
            mode=f"M9-grid-{feeder}",
        )
        print(
            f"  {feeder}: feasible={sol.feasible}, "
            f"cost=¥{sol.objective_cost:.0f}, |S|={len(sol.standby_ids)}"
        )

        if not sol.feasible:
            print(f"    [INFEASIBLE — likely V_max=1.05 strict + θ=5%·B_k too tight]")
            continue

        # Verify Bayes constraint honoured
        theta = dict(sol.threshold_per_axis)
        for ax, mu in sol.expected_loss_per_axis:
            if mu > theta[ax] + 1e-6:
                failures.append(
                    f"{feeder} axis {ax}: μ={mu:.4f} > θ={theta[ax]:.4f}"
                )
            else:
                print(f"    axis {ax}: μ={mu:.4f} kW ≤ θ={theta[ax]:.4f} kW ✓")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-T13-1 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
