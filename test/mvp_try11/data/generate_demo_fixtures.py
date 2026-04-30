"""Generate demo CSV fixtures matching published real-data schemas.

These are NOT real data — synthetic but structured identically to what
real CAISO / AEMO / Pecan Street CSV downloads produce. They exist so
the gridflow ``Dataset`` pipeline can be exercised end-to-end without
requiring a contributor to fetch ~GB of real data.

Each fixture is deterministic (fixed seed) and small (≤ 10 K rows).
"""

from __future__ import annotations

import csv
import math
import random
from datetime import datetime, timedelta
from pathlib import Path


HERE = Path(__file__).resolve().parent


def _generate_caiso_demo() -> Path:
    """7 days × 5-min CAISO system load (synthetic but realistic)."""
    rng = random.Random(42)
    start = datetime(2024, 1, 1, 0, 0, 0)
    n_steps = 7 * 24 * 12  # 5 min × 24 × 7

    rows = []
    for step in range(n_steps):
        ts = start + timedelta(minutes=5 * step)
        hour = ts.hour + ts.minute / 60.0
        # Diurnal pattern: peak 4 pm, valley 4 am
        diurnal = 25000 + 3500 * math.sin(2 * math.pi * (hour - 4) / 24)
        # Weekend reduction (~5% lower)
        weekend = 0 if ts.weekday() < 5 else -1500
        noise = rng.gauss(0, 200)
        load_mw = max(15000, diurnal + weekend + noise)
        rows.append({
            "ts_iso": ts.isoformat() + "Z",
            "system_load_mw": f"{load_mw:.1f}",
        })

    out = HERE / "caiso_system_load_demo.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(fh, fieldnames=("ts_iso", "system_load_mw"))
        w.writeheader()
        w.writerows(rows)
    return out


def _generate_aemo_tesla_vpp_demo() -> Path:
    """30 days × 5-min AEMO Tesla VPP availability."""
    rng = random.Random(43)
    start = datetime(2024, 1, 1, 0, 0, 0)
    n_steps = 30 * 24 * 12

    # ~1000 Tesla Powerwall units, ~5 kW each, 50 Hz target
    n_max = 1000
    cap_per_unit_kw = 5.0

    rows = []
    for step in range(n_steps):
        ts = start + timedelta(minutes=5 * step)
        hour = ts.hour + ts.minute / 60.0
        # Diurnal: more units online overnight (charging) vs evening (discharging)
        diurnal_factor = 0.85 + 0.10 * math.sin(2 * math.pi * (hour - 12) / 24)
        # Random outages / maintenance
        availability = max(0.5, min(1.0, diurnal_factor + rng.gauss(0, 0.03)))
        n_online = int(n_max * availability)
        cap_kw = n_online * cap_per_unit_kw
        # Frequency wandering ±0.05 Hz, with occasional 0.1 Hz events
        freq = 50.0 + rng.gauss(0, 0.02)
        if rng.random() < 0.001:  # rare 0.1 Hz event
            freq += rng.choice([-0.1, 0.1])
        rows.append({
            "ts_iso": ts.isoformat() + "Z",
            "n_units_online": n_online,
            "total_capacity_kw": f"{cap_kw:.1f}",
            "frequency_hz_observed": f"{freq:.4f}",
        })

    out = HERE / "aemo_tesla_vpp_demo.csv"
    with out.open("w", newline="", encoding="utf-8") as fh:
        w = csv.DictWriter(
            fh,
            fieldnames=("ts_iso", "n_units_online", "total_capacity_kw", "frequency_hz_observed"),
        )
        w.writeheader()
        w.writerows(rows)
    return out


def main() -> int:
    p1 = _generate_caiso_demo()
    p2 = _generate_aemo_tesla_vpp_demo()
    print(f"wrote {p1} ({p1.stat().st_size / 1024:.1f} KB)")
    print(f"wrote {p2} ({p2.stat().st_size / 1024:.1f} KB)")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
