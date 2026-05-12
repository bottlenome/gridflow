"""Multi-scale scaling sweep — N ∈ {50, 200, 1000, 5000}.

Phase D-6 (NEXT_STEPS.md §8). Where ``run_phase1_multifeeder`` reports
per-method cost / violation across (feeder, scale) tuples, this runner
focuses on the *scaling* axis: it fixes the trace, the seeds, and a
representative feeder, and walks the pool size N over multiple methods
to expose the (Theorem 2) trade-off between MILP cost and greedy
runtime.

Default sweep:
  feeder = cigre_lv
  trace  = C1 (single-trigger, default magnitude)
  scales (N) ∈ {50, 200, 1000, 5000}
  methods ∈ {M1, M4b, M7, M8}
  seeds  ∈ {0, 1, 2}

= 1 × 1 × 4 × 4 × 3 = 48 cells.

The MILP-bound methods (M1, M7, M8) get ``timeLimit=300`` via CBC; cells
that hit the limit are recorded with ``infeasible_timeout=True``.
``run_one_cell`` (from ``run_phase1_multifeeder``) already records the
elapsed wall-clock time, which is what the Theorem 2 plot needs.
"""

from __future__ import annotations

import argparse
import csv
import json
import multiprocessing as mp
import time
from pathlib import Path

from .run_phase1_multifeeder import run_one_cell

DEFAULT_FEEDER = "cigre_lv"
DEFAULT_TRACES: tuple[str, ...] = ("C1",)
DEFAULT_SCALES: tuple[int, ...] = (50, 200, 1000, 5000)
DEFAULT_METHODS: tuple[str, ...] = ("M1", "M4b", "M7", "M8")
DEFAULT_SEEDS: tuple[int, ...] = (0, 1, 2)

# Methods that genuinely cannot run at N=5000 (variable count blows up
# CBC). M4b is greedy and stays cheap at any N.
SKIP_AT_5000: frozenset[str] = frozenset({"M1", "M7", "M8"})


def build_cell_list(
    feeder: str,
    scales: tuple[int, ...],
    traces: tuple[str, ...],
    methods: tuple[str, ...],
    seeds: tuple[int, ...],
    skip_at_5000: frozenset[str],
) -> list[tuple]:
    """Build a list of (feeder, scale, trace_id, method, seed) cells.

    Cells where ``method ∈ skip_at_5000`` and ``scale ≥ 5000`` are
    elided (they are recorded as ``timeout_skipped`` records below).
    """
    cells: list[tuple] = []
    for scale in scales:
        for trace_id in traces:
            for method in methods:
                if scale >= 5000 and method in skip_at_5000:
                    continue
                for seed in seeds:
                    cells.append((feeder, scale, trace_id, method, seed))
    return cells


def _record_skipped(
    feeder: str,
    scale: int,
    trace_id: str,
    method: str,
    seeds: tuple[int, ...],
) -> list[dict]:
    """Bookkeeping rows for cells we skipped due to known timeout."""
    return [
        {
            "feeder": feeder,
            "scale": scale,
            "trace_id": trace_id,
            "method": method,
            "method_label": method,
            "seed": seed,
            "design_cost": None,
            "n_standby": 0,
            "design_solve_time_s": None,
            "elapsed_s": None,
            "infeasible": True,
            "infeasibility_reason": (
                f"skipped at scale={scale}: MILP variant times out at this N"
            ),
            "metrics": {},
            "error": None,
            "timeout_skipped": True,
        }
        for seed in seeds
    ]


def main() -> int:
    parser = argparse.ArgumentParser(description="try11 multi-scale scaling sweep")
    parser.add_argument("--feeder", type=str, default=DEFAULT_FEEDER)
    parser.add_argument("--scales", type=int, nargs="+", default=list(DEFAULT_SCALES))
    parser.add_argument("--traces", type=str, nargs="+", default=list(DEFAULT_TRACES))
    parser.add_argument("--methods", type=str, nargs="+", default=list(DEFAULT_METHODS))
    parser.add_argument("--seeds", type=int, nargs="+", default=list(DEFAULT_SEEDS))
    parser.add_argument("--n-workers", type=int, default=4)
    parser.add_argument("--output", type=str, default=None)
    args = parser.parse_args()

    feeder = str(args.feeder)
    scales = tuple(args.scales)
    traces = tuple(args.traces)
    methods = tuple(args.methods)
    seeds = tuple(args.seeds)

    cells = build_cell_list(
        feeder, scales, traces, methods, seeds, SKIP_AT_5000
    )
    skipped: list[dict] = []
    for scale in scales:
        for trace_id in traces:
            for method in methods:
                if scale >= 5000 and method in SKIP_AT_5000:
                    skipped.extend(
                        _record_skipped(feeder, scale, trace_id, method, seeds)
                    )

    n = len(cells)
    print(
        f"[try11 scaling] feeder={feeder} cells={n} skipped={len(skipped)} "
        f"workers={args.n_workers}"
    )

    started = time.perf_counter()
    if args.n_workers <= 1:
        records = [run_one_cell(c) for c in cells]
    else:
        with mp.Pool(processes=args.n_workers) as pool_proc:
            records = []
            for i, rec in enumerate(pool_proc.imap_unordered(run_one_cell, cells)):
                records.append(rec)
                if (i + 1) % 10 == 0 or (i + 1) == n:
                    elapsed = time.perf_counter() - started
                    rate = (i + 1) / elapsed if elapsed > 0 else 0
                    eta = (n - (i + 1)) / rate if rate > 0 else 0
                    print(
                        f"  [{i + 1}/{n}] elapsed {elapsed:.0f}s, "
                        f"rate {rate:.2f}/s, ETA {eta:.0f}s"
                    )
    records.extend(skipped)

    total_elapsed = time.perf_counter() - started
    print(f"[try11 scaling] total {total_elapsed:.0f}s for {n} cells")

    output_dir = (
        Path(args.output) if args.output else
        Path(__file__).resolve().parent.parent / "results"
    )
    output_dir.mkdir(parents=True, exist_ok=True)
    out_json = output_dir / "try11_scaling_results.json"
    out_csv = output_dir / "scaling_records.csv"

    out = {
        "records": records,
        "config": {
            "feeder": feeder,
            "scales": list(scales),
            "traces": list(traces),
            "methods": list(methods),
            "seeds": list(seeds),
        },
        "elapsed_s": round(total_elapsed, 1),
        "n_cells": n,
        "n_errors": sum(1 for r in records if r.get("error")),
        "n_infeasible": sum(1 for r in records if r.get("infeasible")),
        "n_timeout_skipped": sum(1 for r in records if r.get("timeout_skipped")),
    }
    out_json.write_text(json.dumps(out, indent=2, sort_keys=True), encoding="utf-8")

    metric_names = sorted({m for r in records for m in r.get("metrics", {})})
    with out_csv.open("w", newline="", encoding="utf-8") as fh:
        w = csv.writer(fh)
        w.writerow([
            "feeder", "scale", "trace_id", "method", "method_label", "seed",
            "design_cost", "n_standby", "design_solve_time_s", "elapsed_s",
            "infeasible", "infeasibility_reason", "timeout_skipped", "error",
            *metric_names,
        ])
        for r in records:
            w.writerow(
                [
                    r.get("feeder"), r.get("scale"), r.get("trace_id"),
                    r.get("method"), r.get("method_label"), r.get("seed"),
                    r.get("design_cost"), r.get("n_standby"),
                    r.get("design_solve_time_s"), r.get("elapsed_s"),
                    r.get("infeasible", False),
                    r.get("infeasibility_reason", "") or "",
                    r.get("timeout_skipped", False),
                    r.get("error", ""),
                    *(r.get("metrics", {}).get(name, "") for name in metric_names),
                ]
            )
    print(f"Wrote {out_json}")
    print(f"Wrote {out_csv}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
