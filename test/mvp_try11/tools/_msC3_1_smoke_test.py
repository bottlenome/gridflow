"""MS-C3-1 smoke test — voltage/line impact matrices for 3 feeders."""

from __future__ import annotations

import time

from tools.feeders import FEEDER_NAMES
from tools.grid_impact import compute_impact_matrix, get_impact_matrix


def main() -> int:
    failures: list[str] = []
    for name in FEEDER_NAMES:
        t0 = time.perf_counter()
        m = compute_impact_matrix(name)
        elapsed = time.perf_counter() - t0

        if m.feeder_name != name:
            failures.append(f"{name}: feeder_name mismatch")
        if not m.bus_indices:
            failures.append(f"{name}: empty bus_indices")
        if len(m.baseline_v_pu) != len(m.bus_indices):
            failures.append(f"{name}: baseline_v_pu length mismatch")
        if len(m.v_impact_per_kw) != len(m.bus_indices):
            failures.append(f"{name}: v_impact rows mismatch")
        if any(len(row) != len(m.bus_indices) for row in m.v_impact_per_kw):
            failures.append(f"{name}: v_impact column mismatch")

        # Voltage impact must be non-negative on diagonal (injection raises local V)
        diag_signs_ok = all(
            m.v_impact_per_kw[i][i] >= -1e-6 for i in range(len(m.bus_indices))
        )
        if not diag_signs_ok:
            failures.append(f"{name}: negative diagonal v_impact (probe should raise local V)")

        # Cache round-trip
        m2 = get_impact_matrix(name)
        if m2.bus_indices != m.bus_indices:
            failures.append(f"{name}: cache returned different matrix")

        print(f"  {name}: n_buses={len(m.bus_indices)}, n_lines={len(m.line_indices)}, "
              f"elapsed={elapsed:.1f}s, "
              f"baseline_v_min={min(m.baseline_v_pu):.3f}, "
              f"baseline_v_max={max(m.baseline_v_pu):.3f}, "
              f"max_v_impact={max(max(row) for row in m.v_impact_per_kw):.5f} pu/kW")

    if failures:
        print(f"\nFAIL: {len(failures)} issues:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-C3-1 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
