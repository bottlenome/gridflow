"""Phyllotactic charging schedule vs baselines on CIGRE LV.

Tests the claim: golden-angle (φ ≈ 0.618) start-time scheduling
yields lower peak load and tighter voltage envelope than synchronized
TOU, random FCFS, or uniform-grid schedules — robustly across any
N, including primes that don't divide the window.

The experiment focuses on the **resonance avoidance property** of
low-discrepancy sequences. The phyllotactic mechanism is borrowed
from plant phyllotaxis (Mitchison 1977) where the golden angle
137.5° ensures non-overlapping leaf placement for any leaf count.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time
import warnings
from pathlib import Path

warnings.filterwarnings("ignore", category=DeprecationWarning)
warnings.filterwarnings("ignore")

HERE = Path(__file__).resolve().parent
RESULTS = HERE.parent / "results"
RESULTS.mkdir(parents=True, exist_ok=True)

PHI = 0.6180339887498949  # (sqrt(5) - 1) / 2  — golden ratio fractional part


def _make_schedule(n: int, total_hours: float, mode: str, seed: int) -> list[float]:
    """Return n charging start times in [0, total_hours)."""
    if mode == "sync":
        # All EVs start at t=0 (textbook TOU rate-cutoff synchronization)
        return [0.0] * n
    if mode == "phyllo":
        # Golden-angle modulo: t_i = (i * phi) mod 1, scaled to window
        return [((i * PHI) % 1.0) * total_hours for i in range(n)]
    if mode == "uniform":
        # Equally spaced: t_i = i / n * total_hours
        return [i / n * total_hours for i in range(n)]
    if mode == "random":
        # Uniform random in window — current FCFS baseline
        rng = random.Random(seed)
        return sorted(rng.uniform(0, total_hours) for _ in range(n))
    raise ValueError(f"unknown mode: {mode}")


def _simulate_one(
    n: int,
    mode: str,
    seed: int,
    charger_bus: int = 35,
    p_charger_kw: float = 7.0,
    charge_duration_h: float = 0.5,
    total_hours: float = 1.0,
    dt_min: int = 2,
) -> dict[str, float]:
    """Simulate the load profile on CIGRE LV for one (n, mode, seed) cell.

    Returns peak_load_kw, voltage_min_pu (worst over time), v_charger_min,
    minutes_below_095 (count of timesteps where any bus < 0.95 pu).
    """
    import pandapower as pp
    import pandapower.networks as pn

    schedule = _make_schedule(n, total_hours, mode, seed)
    net = pn.create_cigre_network_lv()
    load_idx = pp.create_load(net, bus=charger_bus, p_mw=0.0, name="ev_aggregate")

    n_steps = max(1, int(total_hours * 60 / dt_min))
    peak_load_kw = 0.0
    v_min_global = 1.5  # over the full simulation
    v_charger_min = 1.5
    minutes_below_095 = 0
    minutes_below_090 = 0

    for step in range(n_steps):
        t = step * dt_min / 60.0
        # active EVs at time t
        active = sum(1 for s in schedule if s <= t < s + charge_duration_h)
        load_kw = active * p_charger_kw
        net.load.loc[load_idx, "p_mw"] = load_kw / 1000.0
        try:
            pp.runpp(net, numba=False)
            v_min = float(net.res_bus.vm_pu.min())
            v_charger = float(net.res_bus.vm_pu.iloc[charger_bus])
        except Exception:
            # divergence → record worst-case
            v_min = 0.5
            v_charger = 0.5

        peak_load_kw = max(peak_load_kw, load_kw)
        v_min_global = min(v_min_global, v_min)
        v_charger_min = min(v_charger_min, v_charger)
        if v_min < 0.95:
            minutes_below_095 += dt_min
        if v_min < 0.90:
            minutes_below_090 += dt_min

    return {
        "n_evs": n,
        "mode": mode,
        "seed": seed,
        "peak_load_kw": peak_load_kw,
        "v_min_global_pu": v_min_global,
        "v_charger_min_pu": v_charger_min,
        "minutes_below_095": minutes_below_095,
        "minutes_below_090": minutes_below_090,
    }


def main() -> int:
    started = time.perf_counter()
    # Primes / non-divisors to expose the phyllotactic robustness
    n_values = [5, 11, 17, 31]
    modes = ["sync", "phyllo", "uniform", "random"]
    seeds_random = [0, 1, 2, 3]  # only for "random" mode

    raw: list[dict[str, float]] = []
    print(f"[try10] starting factorial: n_values={n_values}, modes={modes}")
    for n in n_values:
        for mode in modes:
            seeds = seeds_random if mode == "random" else [0]
            for seed in seeds:
                cell = _simulate_one(n, mode, seed)
                raw.append(cell)
                print(
                    f"  n={n:>2} mode={mode:>8} seed={seed} "
                    f"peak={cell['peak_load_kw']:>6.1f} kW "
                    f"v_min={cell['v_min_global_pu']:>.4f} "
                    f"min<0.95={cell['minutes_below_095']:>2}"
                )
    elapsed = time.perf_counter() - started
    print(f"[try10] total elapsed: {elapsed:.1f}s")

    # Aggregate per (n, mode) — random mode averaged over seeds
    summary: dict[tuple[int, str], list[dict[str, float]]] = {}
    for r in raw:
        summary.setdefault((r["n_evs"], r["mode"]), []).append(r)

    aggregated = []
    for (n, mode), cells in summary.items():
        aggregated.append(
            {
                "n_evs": n,
                "mode": mode,
                "n_seeds": len(cells),
                "peak_load_kw_mean": statistics.fmean(c["peak_load_kw"] for c in cells),
                "peak_load_kw_max": max(c["peak_load_kw"] for c in cells),
                "v_min_global_mean": statistics.fmean(c["v_min_global_pu"] for c in cells),
                "v_min_global_worst": min(c["v_min_global_pu"] for c in cells),
                "minutes_below_095_mean": statistics.fmean(c["minutes_below_095"] for c in cells),
                "minutes_below_090_mean": statistics.fmean(c["minutes_below_090"] for c in cells),
            }
        )

    out = {
        "raw": raw,
        "aggregated": aggregated,
        "n_values": n_values,
        "modes": modes,
        "elapsed_s": round(elapsed, 1),
    }
    (RESULTS / "phyllo_results.json").write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[try10] wrote {RESULTS / 'phyllo_results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
