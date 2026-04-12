#!/usr/bin/env python3
"""Compare two SweepResult JSONs (OpenDSS vs pandapower).

For each shared aggregated metric we report the absolute difference and
the relative difference (baseline = OpenDSS).

Change from try2: relative delta now uses OpenDSS as baseline denominator
(standard academic convention) instead of max(|a|, |b|).
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any


def _load(path: Path) -> dict[str, Any]:
    with path.open() as fh:
        return json.load(fh)


def _compare(a: dict[str, Any], b: dict[str, Any]) -> dict[str, Any]:
    a_metrics = a.get("aggregated_metrics", {}) or {}
    b_metrics = b.get("aggregated_metrics", {}) or {}
    keys = sorted(set(a_metrics.keys()) | set(b_metrics.keys()))
    rows = []
    for key in keys:
        av = a_metrics.get(key)
        bv = b_metrics.get(key)
        delta = None
        rel = None
        if isinstance(av, (int, float)) and isinstance(bv, (int, float)):
            delta = bv - av
            # Baseline = OpenDSS (a). If baseline is zero, use pandapower (b).
            # If both zero, relative is 0.
            denom = abs(av) if abs(av) > 0 else abs(bv)
            rel = (delta / denom) if denom > 0 else 0.0
        rows.append(
            {
                "metric": key,
                "opendss": av,
                "pandapower": bv,
                "delta": delta,
                "relative_delta": rel,
                "baseline": "opendss",
            }
        )
    return {
        "opendss_sweep_id": a.get("sweep_id"),
        "pandapower_sweep_id": b.get("sweep_id"),
        "opendss_n_experiments": len(a.get("experiment_ids", [])),
        "pandapower_n_experiments": len(b.get("experiment_ids", [])),
        "opendss_elapsed_s": a.get("elapsed_s"),
        "pandapower_elapsed_s": b.get("elapsed_s"),
        "relative_delta_method": "baseline (OpenDSS denominator)",
        "metrics": rows,
    }


def main() -> int:
    p = argparse.ArgumentParser(description=__doc__)
    p.add_argument("--opendss", type=Path, required=True)
    p.add_argument("--pandapower", type=Path, required=True)
    p.add_argument("--output", type=Path, required=True)
    args = p.parse_args()

    a = _load(args.opendss)
    b = _load(args.pandapower)
    report = _compare(a, b)

    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(report, indent=2, sort_keys=True), encoding="utf-8")

    print(
        f"OpenDSS    : {report['opendss_n_experiments']} experiments, "
        f"{report['opendss_elapsed_s']:.2f}s"
    )
    print(
        f"pandapower : {report['pandapower_n_experiments']} experiments, "
        f"{report['pandapower_elapsed_s']:.2f}s"
    )
    print(f"relative_delta method: {report['relative_delta_method']}")
    print()
    print(f"{'metric':<40} {'opendss':>12} {'pandapower':>12} {'delta':>12} {'rel':>8}")
    print("-" * 90)
    for row in report["metrics"]:
        ad = row["opendss"]
        bd = row["pandapower"]
        delta = row["delta"]
        rel = row["relative_delta"]
        a_str = f"{ad:.4f}" if isinstance(ad, (int, float)) else str(ad)
        b_str = f"{bd:.4f}" if isinstance(bd, (int, float)) else str(bd)
        delta_str = f"{delta:+.4f}" if isinstance(delta, (int, float)) else "-"
        rel_str = f"{rel:+.2%}" if isinstance(rel, (int, float)) else "-"
        print(f"{row['metric']:<40} {a_str:>12} {b_str:>12} {delta_str:>12} {rel_str:>8}")

    print(f"\nwrote {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
