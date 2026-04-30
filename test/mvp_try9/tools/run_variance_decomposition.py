"""try9 — Variance attribution of stochastic violation rate across factors.

Per `docs/mvp_review_policy.md` (Phase 1 §3.1) gridflow is used **only as
the experimental orchestration framework** and is not the contribution
of the resulting paper. The contribution is the variance decomposition
finding itself.

Design: see `test/mvp_try9/README.md` and `ideation_record.md`.
Output  : `results/raw_results.json`, `decomposition.json`, `variance_decomposition.png`.
"""

from __future__ import annotations

import json
import random
import statistics
import sys
import time
import warnings
from pathlib import Path

# Suppress pandapower DeprecationWarnings — they pollute the analysis log
# without changing results.
warnings.filterwarnings("ignore", category=DeprecationWarning)

HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)


# ============================================================ pandapower setup


def _build_feeder(name: str, load_level: float):
    """Build a CIGRE LV or MV pandapower network with scaled loads."""
    import pandapower.networks as pn

    if name == "cigre_lv":
        net = pn.create_cigre_network_lv()
    elif name == "cigre_mv":
        net = pn.create_cigre_network_mv()
    else:
        raise ValueError(f"Unknown feeder: {name}")
    # Scale all loads (active + reactive) by load_level. Keep an
    # immutable record of the multiplier on the network for debugging.
    net.load.loc[:, "p_mw"] *= load_level
    net.load.loc[:, "q_mvar"] *= load_level
    return net


def _candidate_pv_buses(net) -> list[int]:
    """Buses where injecting PV makes sense — non-source, non-zero voltage level."""
    # Exclude buses that are already attached to the external grid (source).
    src_buses = set(net.ext_grid["bus"].tolist()) if hasattr(net, "ext_grid") and len(net.ext_grid) > 0 else set()
    return [int(idx) for idx in net.bus.index if int(idx) not in src_buses]


def _run_one(feeder: str, load_level: float, placement_seed: int, capacity_seed: int) -> tuple[int, float, list[float]]:
    """Build a feeder, inject one PV at a seeded random (bus, capacity), run pp.

    Returns (chosen_bus, chosen_kw, voltages_pu).
    """
    import pandapower as pp

    net = _build_feeder(feeder, load_level)
    rng_bus = random.Random(placement_seed * 1000 + capacity_seed)
    rng_kw = random.Random(capacity_seed * 1000 + placement_seed + 17)
    bus = rng_bus.choice(_candidate_pv_buses(net))
    kw = rng_kw.uniform(50.0, 500.0)
    pp.create_sgen(net, bus=bus, p_mw=kw / 1000.0, name=f"pv_{bus}", type="PV")
    pp.runpp(net, numba=False)
    voltages = [float(v) for v in net.res_bus.vm_pu.tolist()]
    return bus, kw, voltages


# ============================================================ metric


def _violation_ratio(voltages: list[float], threshold_lo: float, threshold_hi: float = 1.05) -> float:
    """Fraction of buses with voltage outside [threshold_lo, threshold_hi]."""
    if not voltages:
        return 0.0
    return sum(1 for v in voltages if v < threshold_lo or v > threshold_hi) / len(voltages)


# ============================================================ ANOVA-style decomposition


def _factor_variance_fraction(
    rows: list[dict[str, object]],
    metric_key: str,
    factor_keys: list[str],
) -> dict[str, float]:
    """Sobol-style first-order variance fractions for ``factor_keys``.

    Computes for each factor f:
        S_f = Var( E[Y | f] ) / Var(Y)
    where Y is the metric and the conditional expectation is the group
    mean over rows sharing the same f value. The residual fraction is
    1 - sum(S_f) and absorbs interactions plus noise (random factors).
    """
    values = [float(row[metric_key]) for row in rows]
    if len(values) < 2:
        return {f: 0.0 for f in factor_keys}
    overall_mean = statistics.fmean(values)
    overall_var = sum((v - overall_mean) ** 2 for v in values) / len(values)
    if overall_var == 0:
        return {f: 0.0 for f in factor_keys}

    fractions: dict[str, float] = {}
    for f in factor_keys:
        # Group by factor value, take group mean, weight by group size.
        groups: dict[object, list[float]] = {}
        for row, val in zip(rows, values, strict=True):
            groups.setdefault(row[f], []).append(val)
        weighted_var_of_means = (
            sum(len(g) * (statistics.fmean(g) - overall_mean) ** 2 for g in groups.values()) / len(values)
        )
        fractions[f] = weighted_var_of_means / overall_var
    fractions["residual_and_interactions"] = max(0.0, 1.0 - sum(fractions.values()))
    return fractions


# ============================================================ main


def main() -> int:
    started_wall = time.perf_counter()
    feeders = ["cigre_lv", "cigre_mv"]
    load_levels = [0.50, 1.00]
    threshold_grid = [0.94, 0.95, 0.96]
    n_placement = 16
    n_capacity = 16

    raw_runs: list[dict[str, object]] = []
    print(f"[try9] starting factorial sweep: {len(feeders) * len(load_levels) * n_placement * n_capacity} base runs")
    for feeder in feeders:
        for load_level in load_levels:
            for ps in range(1, n_placement + 1):
                for cs in range(1, n_capacity + 1):
                    bus, kw, voltages = _run_one(feeder, load_level, ps, cs)
                    raw_runs.append(
                        {
                            "feeder": feeder,
                            "load_level": load_level,
                            "placement_seed": ps,
                            "capacity_seed": cs,
                            "pv_bus": bus,
                            "pv_kw": round(kw, 3),
                            "voltages_pu": voltages,
                            "n_buses": len(voltages),
                        }
                    )
    base_elapsed = time.perf_counter() - started_wall
    print(f"[try9] {len(raw_runs)} base runs in {base_elapsed:.1f} s")

    # Persist raw runs (without voltage vectors blowing up the file too much
    # — keep aggregate stats per row + the vectors).
    (RESULTS / "raw_results.json").write_text(json.dumps(raw_runs, indent=2), encoding="utf-8")

    # Cross-product with thresholds for the metric grid.
    metric_rows: list[dict[str, object]] = []
    for run in raw_runs:
        for thr in threshold_grid:
            metric_rows.append(
                {
                    "feeder": run["feeder"],
                    "load_level": run["load_level"],
                    "threshold": thr,
                    "placement_seed": run["placement_seed"],
                    "capacity_seed": run["capacity_seed"],
                    "violation_ratio": _violation_ratio(run["voltages_pu"], thr),  # type: ignore[arg-type]
                }
            )
    print(f"[try9] {len(metric_rows)} metric rows after threshold cross-product")

    # Variance decomposition.
    fixed_factors = ["feeder", "load_level", "threshold"]
    fractions = _factor_variance_fraction(metric_rows, "violation_ratio", fixed_factors)

    # Per-cell summary stats (for the report tables).
    cell_summary: list[dict[str, object]] = []
    for feeder in feeders:
        for load_level in load_levels:
            for thr in threshold_grid:
                cell = [
                    r["violation_ratio"]
                    for r in metric_rows
                    if r["feeder"] == feeder and r["load_level"] == load_level and r["threshold"] == thr
                ]
                cell_summary.append(
                    {
                        "feeder": feeder,
                        "load_level": load_level,
                        "threshold": thr,
                        "n": len(cell),
                        "mean": round(statistics.fmean(cell), 6),
                        "median": round(statistics.median(cell), 6),
                        "stdev": round(statistics.pstdev(cell), 6) if len(cell) > 1 else 0.0,
                    }
                )

    decomposition = {
        "n_base_runs": len(raw_runs),
        "n_metric_rows": len(metric_rows),
        "metric": "violation_ratio",
        "factors": fixed_factors,
        "variance_fractions": {k: round(v, 6) for k, v in fractions.items()},
        "factor_levels": {
            "feeder": feeders,
            "load_level": load_levels,
            "threshold": threshold_grid,
        },
        "cell_summary": cell_summary,
        "elapsed_s": round(time.perf_counter() - started_wall, 3),
    }
    (RESULTS / "decomposition.json").write_text(json.dumps(decomposition, indent=2, sort_keys=True), encoding="utf-8")
    print(f"[try9] variance fractions: {decomposition['variance_fractions']}")
    print(f"[try9] total elapsed: {decomposition['elapsed_s']} s")

    # Optional plot — falls back gracefully if matplotlib is missing.
    try:
        _plot_decomposition(decomposition, RESULTS / "variance_decomposition.png")
        print(f"[try9] wrote variance_decomposition.png")
    except ImportError:
        print(f"[try9] matplotlib not installed — skipping figure")

    return 0


def _plot_decomposition(decomposition: dict, out_path: Path) -> None:
    import matplotlib

    matplotlib.use("Agg")
    import matplotlib.pyplot as plt

    fractions = decomposition["variance_fractions"]
    labels = list(fractions.keys())
    values = [fractions[k] for k in labels]
    fig, ax = plt.subplots(figsize=(7, 4))
    bars = ax.bar(labels, values)
    ax.set_ylabel("Fraction of variance in violation_ratio")
    ax.set_title("Variance attribution across CIGRE LV+MV factorial design")
    ax.set_ylim(0, 1.0)
    for bar, v in zip(bars, values):
        ax.text(bar.get_x() + bar.get_width() / 2, v + 0.01, f"{v:.2f}", ha="center")
    plt.xticks(rotation=15, ha="right")
    plt.tight_layout()
    plt.savefig(out_path, dpi=120)
    plt.close(fig)


if __name__ == "__main__":
    sys.exit(main())
