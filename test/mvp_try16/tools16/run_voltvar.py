"""End-to-end Volt-VAR simulation + sweep + bootstrap CI.

Per cell: (feeder_size, cloud_seed, baseline_pv_kw) drives one
deterministic time-series simulation per controller.  Metrics:

  * v_violation_frac : fraction of (bus, time-step) samples where
    V > v_upper_pu OR V < v_lower_pu
  * v_excursion_max  : max|V - 1.0| across all buses and time
  * q_energy_kvarh   : integrated absolute Q output across feeder

We then bootstrap-CI the per-cell metrics across cells.

CLI:

    python -m tools16.run_voltvar --output ./results
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

from tools16.cloud_simulator import (  # noqa: E402
    CloudEvent,
    random_event_stream,
    simulate_irradiance,
)
from tools16.controllers import (  # noqa: E402
    M0State, M3State, M11State,
    m0_init, m0_step, m3_init, m3_step, m11_init, m11_step,
)
from tools16.feeder_radial import RadialFeeder, lindistflow_voltage, make_feeder  # noqa: E402


@dataclass(frozen=True)
class CellResult:
    feeder_name: str
    n_bus: int
    cloud_seed: int
    pv_baseline_kw: float
    method: str
    v_violation_frac: float
    v_excursion_max: float
    q_energy_kvarh: float


def _simulate_one(
    feeder: RadialFeeder,
    events: tuple[CloudEvent, ...],
    duration_s: float,
    dt: float,
    method: str,
    seg_length_m: float,
    pv_baseline_factor: float = 1.0,
) -> tuple[float, float, float]:
    """Run one (cloud_stream × method) combination, return (vviol, vmax, qE)."""
    n = feeder.n_bus
    irr = simulate_irradiance(n, seg_length_m, events, duration_s, dt)
    if method == "M0":
        ctrl = m0_init(feeder)
    elif method == "M3":
        ctrl = m3_init(feeder)
    elif method == "M11":
        ctrl = m11_init(feeder)
    else:
        raise ValueError(method)

    n_steps = len(irr)
    n_violations = 0
    n_samples = 0
    v_max_excur = 0.0
    q_energy = 0.0
    q_t: tuple[float, ...] = tuple([0.0] * n)
    # Initial step: assume V = 1.0 everywhere, then iterate
    v_t: tuple[float, ...] = tuple([feeder.v0_pu] * n)
    for k in range(n_steps):
        irr_k = irr[k]
        # P injection at each bus = PV(t) - load
        p_inj = tuple(
            feeder.pv_cap_kw[i] * irr_k[i] * pv_baseline_factor - feeder.load_kw[i]
            for i in range(n)
        )
        # Step controller using *previous* voltage (causal)
        if method == "M0":
            q_t = m0_step(ctrl, v_t, dt)
        elif method == "M3":
            q_t = m3_step(ctrl, v_t, dt)
        elif method == "M11":
            q_t = m11_step(ctrl, v_t, dt)
        # Recompute voltage with new Q (one DistFlow per step)
        v_t = lindistflow_voltage(feeder, p_inj, q_t)
        # Metrics: skip first 5 s (warm-up)
        if k * dt >= 5.0:
            for i in range(1, n):
                n_samples += 1
                excur = abs(v_t[i] - 1.0)
                if excur > v_max_excur:
                    v_max_excur = excur
                if v_t[i] > feeder.v_upper_pu or v_t[i] < feeder.v_lower_pu:
                    n_violations += 1
                q_energy += abs(q_t[i]) * dt / 3600.0  # kVARh
    vviol = n_violations / max(1, n_samples)
    return vviol, v_max_excur, q_energy


def run_sweep(
    *,
    n_seeds: int = 24,
    duration_s: float = 180.0,
    dt: float = 0.5,
    seg_length_m: float = 80.0,
    feeder_sizes: tuple[int, ...] = (32, 48, 64),
    pv_baseline_factors: tuple[float, ...] = (0.85, 1.00),
) -> list[CellResult]:
    """Sweep over (feeder_size × pv_baseline × seed × method).

    Feeder default uses *stress regime* (tighter R/X, tight V band, more
    PV per bus): r=0.018 pu/seg, x=0.012 pu/seg, pv=22 kW, v_band 1.04/0.96.
    Cloud events: rate 0.1/s (fast cloud climate), v_cloud 8-25 m/s,
    L_cloud 150-800 m, shadow 0.5-0.92.
    """
    results: list[CellResult] = []
    for n_bus in feeder_sizes:
        feeder = make_feeder(
            name=f"rad{n_bus}", n_bus=n_bus,
            r_seg_pu=0.018, x_seg_pu=0.012,
            pv_cap_each_kw=22.0, load_each_kw=6.0,
            sbase_kw=1000.0, v0_pu=1.00,
            v_upper_pu=1.04, v_lower_pu=0.96,
        )
        for pv_b in pv_baseline_factors:
            for seed in range(n_seeds):
                events = random_event_stream(
                    seed, duration_s,
                    rate_per_s=0.10,
                    v_cloud_range_m_s=(8.0, 25.0),
                    L_cloud_range_m=(150.0, 800.0),
                    shadow_range=(0.5, 0.92),
                )
                for method in ("M0", "M3", "M11"):
                    vviol, vmax, qe = _simulate_one(
                        feeder, events, duration_s, dt,
                        method, seg_length_m, pv_baseline_factor=pv_b,
                    )
                    results.append(CellResult(
                        feeder_name=feeder.name,
                        n_bus=n_bus,
                        cloud_seed=seed,
                        pv_baseline_kw=pv_b,
                        method=method,
                        v_violation_frac=vviol,
                        v_excursion_max=vmax,
                        q_energy_kvarh=qe,
                    ))
    return results


def _bootstrap_ci(
    samples: list[float], n_boot: int = 2000, seed: int = 0,
    alpha: float = 0.05,
) -> tuple[float, float, float]:
    """Return (mean, lo, hi) percentile bootstrap."""
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
    by_method: dict[str, list[CellResult]] = {"M0": [], "M3": [], "M11": []}
    by_method_alpha: dict[tuple[str, float], list[CellResult]] = {}
    for r in results:
        by_method[r.method].append(r)
        key = (r.method, r.pv_baseline_kw)
        by_method_alpha.setdefault(key, []).append(r)
    out = {"per_method": {}, "per_method_alpha": {}}
    for m, lst in by_method.items():
        v = [r.v_violation_frac for r in lst]
        e = [r.v_excursion_max for r in lst]
        q = [r.q_energy_kvarh for r in lst]
        out["per_method"][m] = {
            "n_cells": len(lst),
            "v_violation_frac_mean_lo_hi": _bootstrap_ci(v),
            "v_excursion_max_mean_lo_hi": _bootstrap_ci(e),
            "q_energy_kvarh_mean_lo_hi": _bootstrap_ci(q),
        }
    for (m, alpha), lst in by_method_alpha.items():
        v = [r.v_violation_frac for r in lst]
        e = [r.v_excursion_max for r in lst]
        out["per_method_alpha"][f"{m}@pv={alpha}"] = {
            "n_cells": len(lst),
            "v_violation_frac_mean_lo_hi": _bootstrap_ci(v),
            "v_excursion_max_mean_lo_hi": _bootstrap_ci(e),
        }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=str(_ROOT / "results"))
    parser.add_argument("--n-seeds", type=int, default=24)
    parser.add_argument("--duration", type=float, default=180.0)
    parser.add_argument("--dt", type=float, default=0.5)
    args = parser.parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    print(f"[try16] running sweep n_seeds={args.n_seeds} duration={args.duration}s dt={args.dt}s")
    results = run_sweep(n_seeds=args.n_seeds, duration_s=args.duration, dt=args.dt)
    summary = summarise(results)
    payload = {
        "config": {
            "n_seeds": args.n_seeds, "duration_s": args.duration, "dt_s": args.dt,
            "feeder_sizes": [32, 48, 64],
            "pv_baseline_factors": [0.85, 1.00],
            "regime": "stress: r=0.018, x=0.012, vband=1.04/0.96, cloud_rate=0.1/s",
        },
        "summary": summary,
        "cells": [asdict(r) for r in results],
    }
    out_file = out_dir / "try16_voltvar_sweep.json"
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"[try16] wrote {out_file} ({len(results)} cells)")
    # Print summary table
    pm = summary["per_method"]
    print("--- summary ---")
    for m in ("M0", "M3", "M11"):
        s = pm[m]
        v = s["v_violation_frac_mean_lo_hi"]
        e = s["v_excursion_max_mean_lo_hi"]
        print(f"  {m}: viol={v[0]*100:.3f}% [{v[1]*100:.3f}, {v[2]*100:.3f}]  "
              f"v_excur_max={e[0]:.4f} [{e[1]:.4f}, {e[2]:.4f}] (n={s['n_cells']})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
