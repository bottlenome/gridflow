"""K (tier count) sensitivity sweep for M11 — try16 revision item 2.

Runs the same 4-dataset x 12-perm x 2-alpha protocol as the main heavy
sweep, M11 only, for K in {2, 3, 4, 6, 8, 16}.  Theorem 8
(theorems.md §6) predicts an adaptation-lag / discrimination trade-off:
expected re-entry time to Gold grows linearly in K (slow re-trust),
while small K loses history resolution — so commit-drop should be flat
or mildly U-shaped in K, not monotone.

Usage:
    python -m tools16.run_k_sensitivity [--n-perm 12]
"""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent
if str(_ROOT) not in sys.path:
    sys.path.insert(0, str(_ROOT))

from tools16.run_heavy_sweep import (  # noqa: E402
    AXES, _bootstrap_ci, _default_csvs, run_sweep,
)

K_GRID = (2, 3, 4, 6, 8, 16)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--output", type=str, default=str(_ROOT / "results"))
    parser.add_argument("--n-perm", type=int, default=12)
    args = parser.parse_args(argv)
    out_dir = Path(args.output)
    out_dir.mkdir(parents=True, exist_ok=True)
    csv_paths = _default_csvs()
    if not csv_paths:
        print("[try16] no ACN csv found", file=sys.stderr)
        return 2

    per_k: dict[str, dict] = {}
    all_cells: list[dict] = []
    for k in K_GRID:
        print(f"[try16-K] K={k}")
        cells = run_sweep(csv_paths=csv_paths, n_perm=args.n_perm,
                          methods=("M11",), k_max=k)
        cd = [c.commit_drop_frac for c in cells]
        p99 = [c.p99_unmet_kw for c in cells]
        cg = [c.coverage_gap_frac for c in cells]
        per_k[str(k)] = {
            "n_cells": len(cells),
            "commit_drop_mean_lo_hi": _bootstrap_ci(cd),
            "coverage_gap_mean_lo_hi": _bootstrap_ci(cg),
            "p99_unmet_mean_lo_hi": _bootstrap_ci(p99),
        }
        for c in cells:
            d = asdict(c)
            d["k_max"] = k
            all_cells.append(d)

    payload = {
        "config": {
            "k_grid": list(K_GRID),
            "n_perm": args.n_perm,
            "alphas": [0.10, 0.20],
            "axes": list(AXES),
            "datasets": [str(p) for p in csv_paths],
            "hash": "sha256 stable_hash (process-independent)",
        },
        "per_k": per_k,
        "cells": all_cells,
    }
    out_file = out_dir / "try16_k_sensitivity.json"
    out_file.write_text(json.dumps(payload, indent=2))
    print(f"[try16-K] wrote {out_file} ({len(all_cells)} cells)")
    print("--- K sensitivity (M11 commit_drop) ---")
    for k in K_GRID:
        cd = per_k[str(k)]["commit_drop_mean_lo_hi"]
        p99 = per_k[str(k)]["p99_unmet_mean_lo_hi"]
        print(f"  K={k:>2}: commit_drop={cd[0]*100:.2f}% "
              f"[{cd[1]*100:.2f}, {cd[2]*100:.2f}]  "
              f"p99_unmet={p99[0]:.2f} kW [{p99[1]:.2f}, {p99[2]:.2f}]")
    return 0


if __name__ == "__main__":
    sys.exit(main())
