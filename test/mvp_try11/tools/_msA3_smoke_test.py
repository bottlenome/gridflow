"""MS-A3 smoke test — multi-scale pool + per-feeder config."""

from __future__ import annotations

from tools.der_pool import SCALE_PROFILES, make_scaled_pool
from tools.feeder_config import FEEDER_TRAFO_MVA, feeder_active_pool, get_feeder_config


def main() -> int:
    failures: list[str] = []

    # 1. Each scale produces correct pool size
    for scale, profile in SCALE_PROFILES.items():
        pool = make_scaled_pool(scale, seed=0)
        expected = sum(profile.values())
        if len(pool) != expected:
            failures.append(f"scale={scale}: pool size {len(pool)} != expected {expected}")
        # Type ratios preserved (residential_ev / total ≈ 0.40 for all scales)
        n_ev = sum(1 for d in pool if d.der_type == "residential_ev")
        ratio = n_ev / len(pool)
        if not (0.35 < ratio < 0.45):
            failures.append(f"scale={scale}: ev ratio {ratio:.2f} outside [0.35, 0.45]")

    # 2. Determinism
    p1 = make_scaled_pool(200, seed=0)
    p2 = make_scaled_pool(200, seed=0)
    if p1 != p2:
        failures.append("scaled pool not deterministic")

    # 3. Per-feeder config sized to transformer
    pool = make_scaled_pool(200, seed=0)
    for name, trafo_mva in FEEDER_TRAFO_MVA.items():
        cfg = get_feeder_config(name)
        expected_sla = round(trafo_mva * 1000 * 0.50)
        if cfg.sla_kw != expected_sla:
            failures.append(f"{name}: sla {cfg.sla_kw} != expected {expected_sla}")
        if cfg.n_active_ev <= 0:
            failures.append(f"{name}: zero active EV")
        # Burst dict has all 4 axes
        bd = cfg.burst_dict()
        for axis in ("commute", "weather", "market", "comm_fault"):
            if axis not in bd:
                failures.append(f"{name}: missing burst axis {axis}")

        # Active pool extraction
        active = feeder_active_pool(pool, cfg)
        if len(active) != cfg.n_active_ev:
            failures.append(
                f"{name}: active size {len(active)} != config {cfg.n_active_ev}"
            )

        print(f"  {name}: trafo={trafo_mva}MVA, sla={cfg.sla_kw:.0f}kW, "
              f"n_active={cfg.n_active_ev}, burst={bd}")

    # 4. Larger scales actually grow
    p_50 = make_scaled_pool(50, seed=0)
    p_5000 = make_scaled_pool(5000, seed=0)
    if not (len(p_50) < len(p_5000)):
        failures.append("p_50 should be smaller than p_5000")

    # 5. SLA / burst values are floats and finite
    for name in FEEDER_TRAFO_MVA:
        cfg = get_feeder_config(name)
        for k, v in cfg.burst_kw:
            if not isinstance(v, float) or v != v or v == float("inf"):
                failures.append(f"{name}: burst {k}={v} non-finite")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-A3 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
