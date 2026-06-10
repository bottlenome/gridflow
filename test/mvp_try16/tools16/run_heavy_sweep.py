"""Heavy comparison sweep: M1 / M10 / M11 / Fang / Singh on real ACN data.

Setup:
  * Pool = ACN stationIDs (~50-150 unique stations across Caltech Q1+Q2 / JPL Q1)
  * Time domain = full-quarter span of each csv (≈ 90 days)
  * Trigger axes (5): commute / weather / market / comm_fault / cold_snap
                       (5-axis is harder than 4-axis used in try11-15;
                       tests scaling)
  * Cell sweep: per dataset × per random axis-exposure permutation
                × per SLA tightness alpha ∈ {0.5, 0.7}
  * Per cell, simulate all 5 methods causally over the event stream
    and compute SLA violation fraction + cost.

Bootstrap: 2000 percentile resamples over cells.
"""

from __future__ import annotations

import argparse
import json
import math
import random
import sys
from dataclasses import asdict, dataclass
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools16.acn_drop_events import (  # noqa: E402
    DropEvent, build_pool, inter_drop_intervals, parse_acn_csv,
    presence_intervals_for,
)
from tools16.baselines_lit import (  # noqa: E402
    fang_init, fang_select, fang_update_drop, fang_update_online_step,
    m1_select, m10_select,
    singh_init, singh_register_drop, singh_register_recovery, singh_select,
)
from tools16.heavy_tail_fit import HeavyTailFit, design_hysteresis  # noqa: E402
from tools16.m11_selection import select_m11  # noqa: E402
from tools16.stable_hash import stable_hash  # noqa: E402
from tools16.tier_state import (  # noqa: E402
    K_MAX, TierState, apply_drop, init_pool_state, maybe_promote,
)

METHODS_ALL = ("M1", "M10", "M11", "Fang", "Singh")


AXES = ("commute", "weather", "market", "comm_fault", "cold_snap")


@dataclass(frozen=True)
class CellResult:
    dataset: str
    alpha_sla: float
    perm_seed: int
    method: str
    commit_drop_frac: float        # P[ev.der_id in committed standby]
    coverage_gap_frac: float       # P[unmet kw > 0 on trigger axis]
    sla_violation_frac: float      # = either of the above (any-violation)
    cost_total: float
    p99_unmet_kw: float
    n_events: int


def _build_pool_with_caps(pool_ids: tuple[str, ...],
                          rng: random.Random) -> tuple[tuple[str, float, float, float], ...]:
    """Assign deterministic capacity (kW) and cost ($/kW) and tau (s) per stationID.

    Uses :func:`stable_hash` (SHA-256) — builtin ``hash`` is salted per
    process and silently broke cross-run reproducibility in the
    pre-revision sweep.
    """
    out: list[tuple[str, float, float, float]] = []
    # Synthetic but deterministic mapping (station id digest -> features)
    for sid in pool_ids:
        h = stable_hash(sid)
        cap = 6.0 + (h % 30)            # 6..35 kW
        cost = 1.5 + ((h // 31) % 25) / 10.0  # 1.5..3.9 $/kW
        # tau: 5 type buckets matching try15 DEFAULT_TAU_DROP_S
        tau_choice = (
            5.0, 30.0, 60.0, 180.0, 300.0,
        )[h % 5]
        out.append((sid, float(cap), float(cost), float(tau_choice)))
    return tuple(out)


def _build_axis_exposure(pool_ids: tuple[str, ...],
                         perm_seed: int) -> dict[str, frozenset[str]]:
    """Random-seeded mapping axis -> exposed DER set (= DERs that lose
    capacity when this axis triggers).  Each DER is exposed to ≈ 2/5
    axes."""
    rng = random.Random(perm_seed)
    out: dict[str, set[str]] = {ax: set() for ax in AXES}
    for sid in pool_ids:
        # each DER exposed to a random subset of axes (binomial with p=2/5)
        for ax in AXES:
            if rng.random() < 0.4:
                out[ax].add(sid)
    return {ax: frozenset(out[ax]) for ax in AXES}


def _burst_kw(pool_caps: tuple[tuple[str, float, float, float], ...],
              alpha: float) -> dict[str, float]:
    total = sum(cap for _, cap, _, _ in pool_caps)
    burst_total = alpha * total
    return {
        "commute":     burst_total * 1.00,
        "weather":     burst_total * 0.30,
        "market":      burst_total * 0.30,
        "comm_fault":  burst_total * 0.20,
        "cold_snap":   burst_total * 0.25,
    }


def simulate_one_method(
    method: str,
    *,
    events: tuple[DropEvent, ...],
    pool_caps: tuple[tuple[str, float, float, float], ...],
    pool_ids: tuple[str, ...],
    burst_kw: dict[str, float],
    exposure: dict[str, frozenset[str]],
    fit: HeavyTailFit,
    k_max: int = K_MAX,
    active_resample_every: int | None = None,
    active_seed: int = 0,
) -> tuple[float, float, float, float, float, int]:
    """Causal replay of events with *committed-standby-drop* violation model.

    The simulator maintains a *committed standby set* S(t).  Whenever a
    DER drops:
      1. If the dropping DER is currently in S, this is a SLA-violation
         event (= committed reliability failed).
      2. The method's online state is updated (tier/reputation/etc.).
      3. The standby set S is re-selected fresh from the (now-shrunk)
         eligible pool.

    The metric ``sla_violation_frac`` = (drops within S) / (total drops)
    directly measures how good each method is at committing *reliable*
    DERs to the standby.  This is the true M11 axis of comparison: M11
    selects from high-tier (= history-reliable) DERs, so its S has
    lower future drop probability than M1's pure cost-min selection.

    Returns (sla_violation_frac, cost_avg_per_event, p99_unmet_kw, n_events).
    """
    pool_no_tau = tuple((d, c, k) for (d, c, k, _) in pool_caps)
    pool_with_tau = pool_caps
    cap_lookup = {d: c for (d, c, _, _) in pool_with_tau}
    if method == "M11":
        tier = init_pool_state(pool_ids, k_max=k_max)
    elif method == "Fang":
        fang = fang_init(pool_ids)
    elif method == "Singh":
        singh = singh_init(pool_ids)
    last_online_t: dict[str, float] = {d: events[0].t_drop if events else 0.0
                                       for d in pool_ids}
    n_active = max(2, len(pool_ids) // 10)
    active_ids = frozenset(pool_ids[:n_active])
    # Dynamic-active extension: the active set itself churns — every
    # `active_resample_every` events it is re-drawn (deterministically
    # from `active_seed`) from the full pool, so standby members get
    # pulled into active duty and vice versa.
    active_rng = random.Random(active_seed)

    # Initial standby set selection (before any drops)
    def _select(method_name: str,
                t_now: float) -> tuple[tuple[str, ...], float, bool]:
        if method_name == "M1":
            return m1_select(pool=pool_no_tau, active_ids=active_ids,
                             burst_kw_per_axis=burst_kw,
                             exposure_per_axis=exposure)
        if method_name == "M10":
            return m10_select(pool=pool_with_tau, active_ids=active_ids,
                              burst_kw_per_axis=burst_kw,
                              exposure_per_axis=exposure)
        if method_name == "M11":
            sol = select_m11(
                pool=pool_no_tau, active_ids=active_ids,
                burst_kw_per_axis=burst_kw, exposure_per_axis=exposure,
                tier_state=tier, k_max=k_max,
            )
            return sol.standby_ids, sol.objective_cost, sol.feasible
        if method_name == "Fang":
            return fang_select(pool=pool_no_tau, active_ids=active_ids,
                               burst_kw_per_axis=burst_kw,
                               exposure_per_axis=exposure, state=fang)
        if method_name == "Singh":
            return singh_select(pool=pool_no_tau, active_ids=active_ids,
                                burst_kw_per_axis=burst_kw,
                                exposure_per_axis=exposure, state=singh)
        raise ValueError(method_name)

    standby, init_cost, _ = _select(method, events[0].t_drop if events else 0.0)
    standby_set = set(standby)

    n_events = 0
    n_commit_drops = 0
    n_coverage_gaps = 0
    n_any_violations = 0
    cost_running_sum = init_cost
    unmet_kw_list: list[float] = []

    for ev in events:
        n_events += 1
        # 1. metric A: is the dropping DER in committed standby?
        is_committed_drop = ev.der_id in standby_set
        # 2. metric B: unmet kW on this event's trigger axis
        ax = AXES[stable_hash(ev.der_id) % len(AXES)]
        burst_required = burst_kw[ax]
        cov = sum(cap_lookup[d] for d in standby_set
                  if d != ev.der_id and d not in exposure.get(ax, frozenset()))
        unmet = max(0.0, burst_required - cov)
        unmet_kw_list.append(unmet)
        if is_committed_drop:
            n_commit_drops += 1
        if unmet > 0:
            n_coverage_gaps += 1
        if is_committed_drop or unmet > 0:
            n_any_violations += 1
        # 3. Update method-specific online state on this drop
        if method == "M11":
            tier[ev.der_id] = apply_drop(tier[ev.der_id], ev.t_drop,
                                         d_drop=fit.d_drop)
            for d in pool_ids:
                tier[d] = maybe_promote(tier[d], ev.t_drop, fit.dt_up_s,
                                        k_max=k_max)
        elif method == "Fang":
            fang[ev.der_id] = fang_update_drop(fang[ev.der_id])
        elif method == "Singh":
            dt_up = max(0.0, ev.t_drop - last_online_t[ev.der_id])
            singh[ev.der_id] = singh_register_drop(singh[ev.der_id], dt_up)
            t_recover = ev.t_drop + 3600.0
            singh[ev.der_id] = singh_register_recovery(singh[ev.der_id], 3600.0)
            last_online_t[ev.der_id] = t_recover
        # 4. Dynamic-active churn: periodically re-draw the active set
        if active_resample_every and n_events % active_resample_every == 0:
            active_ids = frozenset(active_rng.sample(list(pool_ids), n_active))
        # 5. Re-select committed standby for next event
        standby, cost, _ = _select(method, ev.t_drop)
        standby_set = set(standby)
        cost_running_sum += cost

    if n_events == 0:
        return (0.0, 0.0, 0.0, 0.0, 0.0, 0)
    cd = n_commit_drops / n_events
    cg = n_coverage_gaps / n_events
    av = n_any_violations / n_events
    unmet_sorted = sorted(unmet_kw_list)
    p99 = unmet_sorted[max(0, int(0.99 * n_events) - 1)]
    return (cd, cg, av, cost_running_sum / n_events, p99, n_events)


def run_sweep(
    *,
    csv_paths: tuple[Path, ...],
    n_perm: int = 12,
    alphas: tuple[float, ...] = (0.10, 0.20),
    methods: tuple[str, ...] = METHODS_ALL,
    k_max: int = K_MAX,
    active_resample_every: int | None = None,
) -> list[CellResult]:
    results: list[CellResult] = []
    for csv_path in csv_paths:
        events = parse_acn_csv(csv_path)
        pool_ids = build_pool(events)
        if len(pool_ids) < 10:
            continue
        # Heavy-tail fit on full-pool inter-drop intervals (= aggregated)
        all_intervals: list[float] = []
        for sid in pool_ids:
            all_intervals.extend(inter_drop_intervals(sid, events))
        fit = design_hysteresis(tuple(all_intervals))
        for perm_seed in range(n_perm):
            rng = random.Random(perm_seed)
            pool_caps = _build_pool_with_caps(pool_ids, rng)
            exposure = _build_axis_exposure(pool_ids, perm_seed)
            for alpha in alphas:
                burst = _burst_kw(pool_caps, alpha)
                for method in methods:
                    cd, cg, av, c_avg, p99, n_ev = simulate_one_method(
                        method,
                        events=events, pool_caps=pool_caps, pool_ids=pool_ids,
                        burst_kw=burst, exposure=exposure, fit=fit,
                        k_max=k_max,
                        active_resample_every=active_resample_every,
                        active_seed=perm_seed,
                    )
                    results.append(CellResult(
                        dataset=csv_path.stem, alpha_sla=alpha,
                        perm_seed=perm_seed, method=method,
                        commit_drop_frac=cd, coverage_gap_frac=cg,
                        sla_violation_frac=av,
                        cost_total=c_avg, p99_unmet_kw=p99, n_events=n_ev,
                    ))
        print(f"  ... {csv_path.stem}: pool={len(pool_ids)} events={len(events)} "
              f"fit alpha_hill={fit.alpha_hill:.3f} d_drop={fit.d_drop} "
              f"dt_up_s={fit.dt_up_s:.1f}")
    return results


def _bootstrap_ci(samples: list[float], n_boot: int = 2000,
                  seed: int = 0, alpha: float = 0.05
                  ) -> tuple[float, float, float]:
    rng = random.Random(seed)
    n = len(samples)
    if n == 0:
        return (0.0, 0.0, 0.0)
    means: list[float] = []
    for _ in range(n_boot):
        s = sum(samples[rng.randrange(n)] for _ in range(n)) / n
        means.append(s)
    means.sort()
    lo = means[int(alpha / 2 * n_boot)]
    hi = means[int((1 - alpha / 2) * n_boot)]
    return (sum(samples) / n, lo, hi)


def summarise(results: list[CellResult]) -> dict:
    by_method: dict[str, list[CellResult]] = {}
    by_method_alpha: dict[tuple[str, float], list[CellResult]] = {}
    for r in results:
        by_method.setdefault(r.method, []).append(r)
        by_method_alpha.setdefault((r.method, r.alpha_sla), []).append(r)
    out: dict = {"per_method": {}, "per_method_alpha": {}}
    for m, lst in by_method.items():
        cd = [r.commit_drop_frac for r in lst]
        cg = [r.coverage_gap_frac for r in lst]
        av = [r.sla_violation_frac for r in lst]
        c = [r.cost_total for r in lst]
        p = [r.p99_unmet_kw for r in lst]
        out["per_method"][m] = {
            "n_cells": len(lst),
            "commit_drop_mean_lo_hi": _bootstrap_ci(cd),
            "coverage_gap_mean_lo_hi": _bootstrap_ci(cg),
            "any_violation_mean_lo_hi": _bootstrap_ci(av),
            "cost_mean_lo_hi": _bootstrap_ci(c),
            "p99_unmet_mean_lo_hi": _bootstrap_ci(p),
        }
    for (m, a), lst in by_method_alpha.items():
        cd = [r.commit_drop_frac for r in lst]
        cg = [r.coverage_gap_frac for r in lst]
        out["per_method_alpha"][f"{m}@a={a}"] = {
            "n_cells": len(lst),
            "commit_drop_mean_lo_hi": _bootstrap_ci(cd),
            "coverage_gap_mean_lo_hi": _bootstrap_ci(cg),
        }
    return out


def _default_csvs() -> tuple[Path, ...]:
    repo = Path(__file__).resolve().parents[3]
    paths: list[Path] = []
    for rel in (
        "test/mvp_try11/data/acn_caltech_sessions_2019_01.csv",
        "test/mvp_try13/data/acn_caltech_2019_02.csv",
        "test/mvp_try13/data/acn_caltech_2019_03.csv",
        "test/mvp_try13/data/acn_jpl_2019_01.csv",
    ):
        p = repo / rel
        if p.exists():
            paths.append(p)
    return tuple(paths)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=str(_ROOT / "results"))
    parser.add_argument("--n-perm", type=int, default=12)
    parser.add_argument("--k-max", type=int, default=K_MAX,
                        help="M11 tier count K (sensitivity sweeps)")
    parser.add_argument("--active-resample-every", type=int, default=0,
                        help="If > 0, re-draw the active set every N events "
                             "(dynamic active+standby churn scenario)")
    parser.add_argument("--out-name", type=str, default="try16_heavy_sweep.json")
    args = parser.parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_paths = _default_csvs()
    if not csv_paths:
        print("[try16] no ACN csv found", file=sys.stderr)
        return 2
    resample = args.active_resample_every or None
    print(f"[try16] heavy sweep over {len(csv_paths)} ACN datasets, "
          f"n_perm={args.n_perm} k_max={args.k_max} "
          f"active_resample_every={resample}")
    results = run_sweep(csv_paths=csv_paths, n_perm=args.n_perm,
                        k_max=args.k_max, active_resample_every=resample)
    summary = summarise(results)
    payload = {
        "config": {
            "n_perm": args.n_perm, "alphas": [0.10, 0.20],
            "axes": list(AXES),
            "datasets": [str(p) for p in csv_paths],
            "regime": "ACN-Data Caltech 2019 Q1 (3 months) + JPL 2019-01",
            "k_max": args.k_max,
            "active_resample_every": resample,
            "hash": "sha256 stable_hash (process-independent)",
        },
        "summary": summary,
        "cells": [asdict(r) for r in results],
    }
    out_file = out_dir / args.out_name
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"[try16] wrote {out_file} ({len(results)} cells)")
    print("--- summary ---")
    pm = summary["per_method"]
    for m in METHODS_ALL:
        if m not in pm:
            continue
        s = pm[m]
        cd = s["commit_drop_mean_lo_hi"]
        cg = s["coverage_gap_mean_lo_hi"]
        print(f"  {m}: commit_drop={cd[0]*100:.3f}% [{cd[1]*100:.3f}, {cd[2]*100:.3f}] "
              f"cov_gap={cg[0]*100:.3f}% [{cg[1]*100:.3f}, {cg[2]*100:.3f}] (n={s['n_cells']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
