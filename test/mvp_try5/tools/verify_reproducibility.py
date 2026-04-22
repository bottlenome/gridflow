#!/usr/bin/env python3
"""Verify bit-identical reproducibility of a SweepResult.

Compares two SweepResult JSONs and checks:
  1. Physics metrics (hosting_capacity_*, voltage_deviation_*) must be
     bit-identical between runs.
  2. Runtime metrics (runtime_*) are expected to vary (wall-clock timing)
     and are reported but do not cause failure.

Exit code 0 = physics metrics identical, 1 = physics differences found.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

# Metrics that depend on wall-clock timing and are expected to differ
RUNTIME_METRICS = {"runtime_max", "runtime_mean", "runtime_median", "runtime_min", "runtime_stdev"}


def _load(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("run1", type=Path, help="First SweepResult JSON")
    p.add_argument("run2", type=Path, help="Second SweepResult JSON (rerun)")
    args = p.parse_args()

    a = _load(args.run1)
    b = _load(args.run2)

    a_metrics = a.get("aggregated_metrics", {})
    b_metrics = b.get("aggregated_metrics", {})

    all_keys = sorted(set(a_metrics.keys()) | set(b_metrics.keys()))
    physics_diffs: list[str] = []
    runtime_diffs: list[str] = []
    identical = 0

    for key in all_keys:
        av = a_metrics.get(key)
        bv = b_metrics.get(key)
        if av == bv:
            identical += 1
        elif key in RUNTIME_METRICS:
            runtime_diffs.append(f"  {key}: run1={av}  run2={bv}  (expected: wall-clock variance)")
        else:
            physics_diffs.append(f"  {key}: run1={av}  run2={bv}")

    n_a = len(a.get("experiment_ids", []))
    n_b = len(b.get("experiment_ids", []))

    print(f"Reproducibility check: {args.run1.name} vs {args.run2.name}")
    print(f"  experiment count: run1={n_a}  run2={n_b}  {'MATCH' if n_a == n_b else 'MISMATCH'}")
    print(f"  plan_hash: run1={a.get('plan_hash')}  run2={b.get('plan_hash')}")
    print(f"  metrics compared: {len(all_keys)}")
    print(f"  bit-identical: {identical}")
    print(f"  runtime variance (expected): {len(runtime_diffs)}")
    print(f"  physics differences (unexpected): {len(physics_diffs)}")

    if n_a != n_b:
        physics_diffs.append(f"  experiment_count: run1={n_a}  run2={n_b}")

    if a.get("plan_hash") != b.get("plan_hash"):
        physics_diffs.append(f"  plan_hash: run1={a.get('plan_hash')}  run2={b.get('plan_hash')}")

    if runtime_diffs:
        print("\nRUNTIME VARIANCE (expected, not a failure):")
        for d in runtime_diffs:
            print(d)

    if physics_diffs:
        print("\nPHYSICS DIFFERENCES FOUND (unexpected):")
        for d in physics_diffs:
            print(d)
        print("\nVERDICT: FAIL - physics metrics are NOT bit-identical")
        return 1
    else:
        print("\nVERDICT: PASS - all physics metrics are bit-identical")
        print("  (runtime metrics vary as expected due to wall-clock timing)")
        return 0


if __name__ == "__main__":
    sys.exit(main())
