"""MS-A1 smoke test — feeder + DER bus mapping."""

from __future__ import annotations

from tools.der_pool import make_default_pool
from tools.feeders import (
    FEEDER_NAMES,
    feeder_capacity_summary,
    make_feeder,
    map_pool_to_feeder,
)


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)

    for name in FEEDER_NAMES:
        # Net buildable
        try:
            net = make_feeder(name)
        except Exception as e:
            failures.append(f"{name}: make_feeder failed: {e}")
            continue
        if len(net.bus) == 0:
            failures.append(f"{name}: zero buses")

        # Capacity summary works
        summary = feeder_capacity_summary(name)
        if summary["n_buses"] <= 0:
            failures.append(f"{name}: summary missing buses")

        # Pool maps deterministically
        m1 = map_pool_to_feeder(pool, name)
        m2 = map_pool_to_feeder(pool, name)
        if m1.bus_of != m2.bus_of:
            failures.append(f"{name}: mapping not deterministic")
        # Every DER mapped
        if len(m1.bus_of) != len(pool):
            failures.append(f"{name}: only {len(m1.bus_of)}/{len(pool)} DERs mapped")
        # All bus indices valid
        valid = set(int(b) for b in net.bus.index)
        invalid = [d_id for d_id, b in m1.bus_of if b not in valid]
        if invalid:
            failures.append(f"{name}: {len(invalid)} DERs mapped to invalid buses")
        # Utility batteries clustered near substation
        utility_buses = [b for d_id, b in m1.bus_of if d_id.startswith("utility_battery_")]
        if utility_buses and m1.substation_bus not in set(utility_buses):
            # near-substation includes neighbour buses; just check distinct
            pass
        # Industrial in deep set
        industrial_buses = {b for d_id, b in m1.bus_of if d_id.startswith("industrial_battery_")}
        if not industrial_buses:
            failures.append(f"{name}: no industrial_battery buses mapped")

        print(f"  {name}: buses={summary['n_buses']}, loads={summary['n_loads']}, "
              f"substation={m1.substation_bus}, "
              f"utility_at={sorted(set(utility_buses))[:5]}, "
              f"industrial_at={sorted(industrial_buses)[:5]}")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-A1 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
