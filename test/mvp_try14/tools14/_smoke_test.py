"""Smoke test for try14: M9-grid-soft, MV feeder, ACN phase-invert."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
_TRY12 = _HERE.parent.parent / "mvp_try12"
_TRY13 = _HERE.parent.parent / "mvp_try13"
for p in (_TRY11, _TRY12, _TRY13, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.der_pool import TRIGGER_BASIS_K3, make_default_pool  # noqa: E402
from tools.feeder_config import feeder_active_pool, get_feeder_config  # noqa: E402
from tools.feeders import map_pool_to_feeder  # noqa: E402

from tools14.sdp_full_soft import solve_sdp_full_soft  # noqa: E402


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)

    for feeder in ("cigre_lv", "kerber_dorf", "kerber_landnetz"):
        config = get_feeder_config(feeder)
        active_ids = feeder_active_pool(pool, config)
        burst = config.burst_dict()
        bus_map = map_pool_to_feeder(pool, feeder)

        # Force the harder operating point for cigre_lv where try13 found infeasibility
        sla_kw = config.sla_kw if feeder != "cigre_lv" else config.sla_kw * 1.4  # ~ α=0.7
        scaled_burst = {ax: bk * (sla_kw / config.sla_kw) for ax, bk in burst.items()}

        sol = solve_sdp_full_soft(
            pool, active_ids, scaled_burst, bus_map, feeder,
            basis=TRIGGER_BASIS_K3,
            epsilon=0.05,
            expected_loss_threshold_fraction=0.05,
            slack_lambda=1e6,
            v_max_pu=1.05, line_max_pct=100.0,
            mode=f"M9-grid-soft-{feeder}",
        )
        slack_total = sum(s for _, s in sol.slack_per_axis)
        print(
            f"  {feeder} (sla={sla_kw:.0f} kW): feasible={sol.feasible}, "
            f"cost=¥{sol.objective_cost:.0f}, |S|={len(sol.standby_ids)}, "
            f"slack_total={slack_total:.4f} kW"
        )
        if not sol.feasible:
            failures.append(f"{feeder}: M9-grid-soft must always be feasible (slack closes any gap)")

    if failures:
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — try14 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
