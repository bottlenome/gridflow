"""LP/MILP centralised optimum vs phyllotactic schedule (heterogeneous EVs).

Tests whether the proposed phyllotactic primitive falls behind a
*real* centralised optimiser when EVs are heterogeneous (mixed
charge-duration / deadline). The previous experiment used identical
EVs, in which case `uniform` is the LP optimum analytically; this
experiment introduces variability that the LP can exploit but
phyllo cannot.

Slot-based MILP:
    x_{i,s} ∈ {0,1}  (EV i starts at slot s, 1 if so)
    Σ_s x_{i,s} = 1  for each EV i
    s ≤ S - L_i  (must finish before window closes)
    peak ≥ Σ_i Σ_{s : s ≤ k < s+L_i} P_i · x_{i,s}  for each timestep k
    minimise peak

Solved by PuLP / CBC (default open-source solver).
"""

from __future__ import annotations

import json
import math
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

PHI = 0.6180339887498949


# ============================================================ EV scenario


def _make_heterogeneous_evs(n: int, seed: int) -> list[dict]:
    """Return N EVs with mixed energy / arrival / deadline.

    energy_kwh ∈ {3, 4, 5, 6, 7}  → durations 0.43..1.00 h at 7 kW
    arrival ∈ {0, 0.1, 0.2} (most plug in at start, some later)
    deadline = 1.0  (window end), all must finish by W=1h
    """
    rng = random.Random(seed)
    evs = []
    for i in range(n):
        energy_kwh = rng.choice([3.0, 4.0, 5.0, 6.0, 7.0])
        arrival = rng.choice([0.0, 0.1, 0.2])
        evs.append(
            {
                "ev_id": i,
                "energy_kwh": energy_kwh,
                "p_kw": 7.0,
                "duration_h": energy_kwh / 7.0,
                "arrival_h": arrival,
                "deadline_h": 1.0,
            }
        )
    return evs


# ============================================================ schedules


def _phyllo_start_times(evs: list[dict], window_h: float = 1.0) -> list[float]:
    """phyllotactic with deadline / arrival clipping.

    Plain phyllo: t_n = (n·φ) mod W. If infeasible (arrival > t or
    t + duration > deadline), clip to feasible window [arrival,
    deadline - duration]. If feasible window empty (= EV cannot fit
    at all), set t = arrival_h and accept the deadline violation;
    we record this in metrics.
    """
    starts = []
    for n, ev in enumerate(evs):
        raw = (n * PHI) % window_h
        feas_lo = ev["arrival_h"]
        feas_hi = ev["deadline_h"] - ev["duration_h"]
        if feas_hi < feas_lo:
            # EV cannot fit
            t = feas_lo
        else:
            t = max(feas_lo, min(feas_hi, raw))
        starts.append(t)
    return starts


def _uniform_start_times(evs: list[dict], window_h: float = 1.0) -> list[float]:
    """Equally spaced within each EV's feasible window.

    Same clipping convention as phyllo.
    """
    n = len(evs)
    starts = []
    for i, ev in enumerate(evs):
        raw = i / n * window_h
        feas_lo = ev["arrival_h"]
        feas_hi = ev["deadline_h"] - ev["duration_h"]
        if feas_hi < feas_lo:
            t = feas_lo
        else:
            t = max(feas_lo, min(feas_hi, raw))
        starts.append(t)
    return starts


def _milp_start_times(
    evs: list[dict],
    window_h: float = 1.0,
    dt_min: int = 2,
) -> tuple[list[float], dict]:
    """Solve slot-based MILP for peak-load minimisation.

    Returns (start_times_h, solver_info).
    """
    import pulp

    dt_h = dt_min / 60.0
    s_total = int(round(window_h / dt_h))  # number of slots (timesteps)
    # For each EV: feasible start slots
    durations_slots = [int(math.ceil(ev["duration_h"] / dt_h)) for ev in evs]
    arrival_slots = [int(math.floor(ev["arrival_h"] / dt_h)) for ev in evs]
    feasible_slots: list[list[int]] = []
    for i, ev in enumerate(evs):
        # ev must start at slot s such that arrival_slot ≤ s ≤ s_total - L_i
        lo = arrival_slots[i]
        hi = s_total - durations_slots[i]
        if hi < lo:
            # infeasible — pick latest feasible (clipped at lo)
            feasible_slots.append([lo])
        else:
            feasible_slots.append(list(range(lo, hi + 1)))

    # MILP
    prob = pulp.LpProblem("ev_milp", pulp.LpMinimize)
    x = {
        (i, s): pulp.LpVariable(f"x_{i}_{s}", cat="Binary")
        for i in range(len(evs))
        for s in feasible_slots[i]
    }
    peak = pulp.LpVariable("peak", lowBound=0)

    # each EV picks exactly one start slot
    for i in range(len(evs)):
        prob += pulp.lpSum(x[(i, s)] for s in feasible_slots[i]) == 1

    # peak ≥ sum of active EV powers at each timestep
    for k in range(s_total):
        active_terms = []
        for i, ev in enumerate(evs):
            for s in feasible_slots[i]:
                if s <= k < s + durations_slots[i]:
                    active_terms.append(ev["p_kw"] * x[(i, s)])
        if active_terms:
            prob += peak >= pulp.lpSum(active_terms)

    prob += peak  # objective

    started = time.perf_counter()
    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=60)
    status = prob.solve(solver)
    solve_s = time.perf_counter() - started

    starts: list[float] = []
    for i in range(len(evs)):
        chosen_s = None
        for s in feasible_slots[i]:
            v = pulp.value(x[(i, s)])
            if v is not None and v > 0.5:
                chosen_s = s
                break
        if chosen_s is None:
            chosen_s = feasible_slots[i][0]
        starts.append(chosen_s * dt_h)
    info = {
        "status": pulp.LpStatus[status],
        "objective_kw": float(pulp.value(peak) or 0.0),
        "solve_s": round(solve_s, 3),
        "n_binary_vars": len(x),
        "n_constraints": s_total + len(evs),
    }
    return starts, info


def _random_start_times(evs: list[dict], window_h: float, seed: int) -> list[float]:
    rng = random.Random(seed)
    starts = []
    for ev in evs:
        feas_lo = ev["arrival_h"]
        feas_hi = ev["deadline_h"] - ev["duration_h"]
        if feas_hi < feas_lo:
            starts.append(feas_lo)
        else:
            starts.append(rng.uniform(feas_lo, feas_hi))
    return starts


# ============================================================ simulation


def _simulate(
    evs: list[dict],
    start_times: list[float],
    charger_bus: int = 35,
    window_h: float = 1.0,
    dt_min: int = 2,
) -> dict:
    """Compute peak load + voltage envelope on CIGRE LV for given schedule."""
    import pandapower as pp
    import pandapower.networks as pn

    net = pn.create_cigre_network_lv()
    load_idx = pp.create_load(net, bus=charger_bus, p_mw=0.0, name="ev_aggregate")

    n_steps = int(round(window_h * 60 / dt_min))
    peak_load_kw = 0.0
    v_min = 1.5
    deadline_violations = 0
    for i, (ev, t) in enumerate(zip(evs, start_times, strict=True)):
        if t + ev["duration_h"] > ev["deadline_h"] + 1e-6:
            deadline_violations += 1

    for step in range(n_steps):
        t = step * dt_min / 60.0
        load_kw = 0.0
        for ev, st in zip(evs, start_times, strict=True):
            if st <= t < st + ev["duration_h"]:
                load_kw += ev["p_kw"]
        net.load.loc[load_idx, "p_mw"] = load_kw / 1000.0
        try:
            pp.runpp(net, numba=False)
            this_v_min = float(net.res_bus.vm_pu.min())
        except Exception:
            this_v_min = 0.5
        peak_load_kw = max(peak_load_kw, load_kw)
        v_min = min(v_min, this_v_min)

    return {
        "peak_load_kw": peak_load_kw,
        "v_min_global_pu": v_min,
        "deadline_violations": deadline_violations,
    }


# ============================================================ main


def main() -> int:
    started_wall = time.perf_counter()

    n_evs = 11  # heterogeneous fleet, prime to avoid trivial uniform optimality
    seeds = [0, 1, 2, 3, 4]  # 5 different EV mixes
    modes = ["sync", "random", "uniform", "phyllo", "milp"]

    print(f"[try10/lp] N={n_evs}, seeds={seeds}, modes={modes}")
    raw = []
    for seed in seeds:
        evs = _make_heterogeneous_evs(n_evs, seed)
        durations = [ev["duration_h"] for ev in evs]
        print(
            f"\n  seed={seed}  durations(h) = {[round(d, 2) for d in durations]}  "
            f"sum={sum(durations):.2f}"
        )

        # Compute schedules per mode
        schedules: dict[str, list[float]] = {}
        milp_info = None
        for mode in modes:
            if mode == "sync":
                schedules[mode] = [ev["arrival_h"] for ev in evs]  # all start at arrival
            elif mode == "random":
                schedules[mode] = _random_start_times(evs, 1.0, seed)
            elif mode == "uniform":
                schedules[mode] = _uniform_start_times(evs, 1.0)
            elif mode == "phyllo":
                schedules[mode] = _phyllo_start_times(evs, 1.0)
            elif mode == "milp":
                schedules[mode], milp_info = _milp_start_times(evs, 1.0)
            else:
                raise ValueError(mode)

        # Simulate each
        for mode in modes:
            metrics = _simulate(evs, schedules[mode])
            row = {
                "n_evs": n_evs,
                "seed": seed,
                "mode": mode,
                **metrics,
            }
            if mode == "milp" and milp_info is not None:
                row["milp_objective_kw"] = milp_info["objective_kw"]
                row["milp_solve_s"] = milp_info["solve_s"]
                row["milp_n_binaries"] = milp_info["n_binary_vars"]
            raw.append(row)
            extra = ""
            if mode == "milp" and milp_info is not None:
                extra = f"  obj={milp_info['objective_kw']:.1f}kW solve={milp_info['solve_s']}s"
            print(
                f"    {mode:>8}: peak={metrics['peak_load_kw']:>5.1f}kW "
                f"v_min={metrics['v_min_global_pu']:.4f} "
                f"deadlines_violated={metrics['deadline_violations']}{extra}"
            )

    elapsed = time.perf_counter() - started_wall
    print(f"\n[try10/lp] total elapsed: {elapsed:.1f}s")

    # Aggregate per mode (mean across 5 seeds)
    by_mode: dict[str, list[dict]] = {}
    for r in raw:
        by_mode.setdefault(r["mode"], []).append(r)

    aggregated = []
    for mode, rs in by_mode.items():
        aggregated.append(
            {
                "mode": mode,
                "n_seeds": len(rs),
                "peak_load_kw_mean": round(statistics.fmean(r["peak_load_kw"] for r in rs), 2),
                "peak_load_kw_max": max(r["peak_load_kw"] for r in rs),
                "v_min_mean": round(statistics.fmean(r["v_min_global_pu"] for r in rs), 4),
                "v_min_worst": min(r["v_min_global_pu"] for r in rs),
                "deadline_violations_total": sum(r["deadline_violations"] for r in rs),
            }
        )

    # phyllo / milp gap calculation
    phyllo_means = next(a["peak_load_kw_mean"] for a in aggregated if a["mode"] == "phyllo")
    milp_means = next(a["peak_load_kw_mean"] for a in aggregated if a["mode"] == "milp")
    gap_pct = (phyllo_means - milp_means) / milp_means * 100.0 if milp_means > 0 else 0.0

    out = {
        "raw": raw,
        "aggregated": aggregated,
        "phyllo_milp_gap_pct": round(gap_pct, 2),
        "elapsed_s": round(elapsed, 1),
    }
    out_path = RESULTS / "phyllo_vs_milp.json"
    out_path.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")
    print(f"\n[try10/lp] phyllo / milp peak gap = {gap_pct:.2f}% (positive = phyllo worse)")
    print(f"[try10/lp] wrote {out_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
