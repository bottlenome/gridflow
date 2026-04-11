#!/usr/bin/env python3
"""Verify that the per-pack 3-run experiments produce identical voltages.

Checks C-1 (reproducibility crisis) from ``docs/research_landscape.md`` by
loading every ``results/der_*_run*.json`` produced by ``run_der_sweep.sh``
and asserting that, for each DER penetration level, the three runs yield
**bit-identical** voltage tuples.

Exit code:
    0  - all 5 DER levels × 3 runs are bit-identical
    1  - at least one mismatch (details printed to stderr)

Usage:
    python verify_reproducibility.py results/der_*_run*.json
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path
from typing import Any

import numpy as np


_FILE_RE = re.compile(r"der_(?P<pct>\d+)_run(?P<run>\d+)\.json$")


def _extract_voltages(path: Path) -> np.ndarray:
    """Pull the first node_result voltage vector out of an experiment JSON."""
    with path.open() as fh:
        data = json.load(fh)
    # CLI ``gridflow run`` emits a thin summary: {experiment_id, pack_id, ...,
    # result_path}. Follow ``result_path`` to the full ExperimentResult JSON
    # that gridflow persisted.
    if "result_path" in data and "node_results" not in data:
        with open(data["result_path"]) as fh:
            data = json.load(fh)

    if not data.get("node_results"):
        raise ValueError(f"{path}: no node_results found in experiment JSON")
    # NodeResult voltages are stored as list[float]; concatenate all nodes so
    # we compare the full vector across all buses.
    parts: list[float] = []
    for nr in data["node_results"]:
        parts.extend(float(v) for v in nr["voltages"])
    return np.asarray(parts, dtype=np.float64)


def _group_by_level(paths: list[Path]) -> dict[str, dict[int, Path]]:
    """Group files by DER penetration level and run index."""
    groups: dict[str, dict[int, Path]] = defaultdict(dict)
    for p in paths:
        m = _FILE_RE.search(p.name)
        if m is None:
            print(f"[skip] {p} does not match der_<pct>_run<N>.json", file=sys.stderr)
            continue
        pct = m["pct"]
        run = int(m["run"])
        groups[pct][run] = p
    return groups


def _verify_level(pct: str, runs: dict[int, Path]) -> tuple[bool, str]:
    """Return (ok, message) for a single DER level's 3 runs."""
    run_ids = sorted(runs.keys())
    if len(run_ids) < 2:
        return False, f"DER {pct}%: need at least 2 runs, got {len(run_ids)}"
    vectors: dict[int, np.ndarray] = {r: _extract_voltages(runs[r]) for r in run_ids}

    first = vectors[run_ids[0]]
    for r in run_ids[1:]:
        v = vectors[r]
        if v.shape != first.shape:
            return False, (
                f"DER {pct}%: run{run_ids[0]} shape {first.shape} vs "
                f"run{r} shape {v.shape}"
            )
        if not np.array_equal(first, v):
            # Show the worst per-element diff for diagnostics.
            diff = np.abs(first - v)
            idx = int(np.argmax(diff))
            return False, (
                f"DER {pct}%: run{run_ids[0]} != run{r} "
                f"(max |Δ|={diff[idx]:.3e} at index {idx}, "
                f"a={first[idx]:.15g}, b={v[idx]:.15g})"
            )
    return True, f"DER {pct}%: {len(run_ids)} runs bit-identical ({first.size} bus voltages)"


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "files",
        nargs="+",
        type=Path,
        help="results/der_*_run*.json files",
    )
    args = parser.parse_args(argv)

    groups = _group_by_level(args.files)
    if not groups:
        print("no files matched der_<pct>_run<N>.json", file=sys.stderr)
        return 1

    all_ok = True
    for pct in sorted(groups.keys(), key=int):
        ok, msg = _verify_level(pct, groups[pct])
        marker = "OK " if ok else "FAIL"
        print(f"[{marker}] {msg}")
        if not ok:
            all_ok = False

    if all_ok:
        print("")
        print(f"SUCCESS: all {len(groups)} DER levels are reproducible "
              "(3 runs each, bit-identical).")
        return 0
    print("")
    print("FAILURE: at least one DER level is NOT reproducible.", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
