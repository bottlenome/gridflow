"""Convert a heavy-sweep summary JSON into a canonical ComparisonTable JSON.

Bridges the try16 study output to ``gridflow export paper`` (AS-5 /
QA-6: sweep -> paper-ready LaTeX table in < 3 steps):

    1. python -m tools16.run_heavy_sweep --n-perm 12
    2. python -m tools16.export_comparison_table
    3. gridflow export paper results/try16_comparison_table.json -o results/paper

Usage:
    python -m tools16.export_comparison_table [--input ...] [--output ...]
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_ROOT = _HERE.parent

METHOD_ORDER = ("M1", "M10", "M11", "Fang", "Singh")


def build_table(sweep: dict) -> dict:
    per_method = sweep["summary"]["per_method"]
    config = sweep["config"]
    rows = []
    for method in METHOD_ORDER:
        if method not in per_method:
            continue
        s = per_method[method]
        cd = s["commit_drop_mean_lo_hi"]
        cg = s["coverage_gap_mean_lo_hi"]
        p99 = s["p99_unmet_mean_lo_hi"]
        rows.append({
            "method": method,
            "n": s["n_cells"],
            "values": [
                {"mean": cd[0] * 100, "ci_low": cd[1] * 100, "ci_high": cd[2] * 100},
                {"mean": cg[0] * 100, "ci_low": cg[1] * 100, "ci_high": cg[2] * 100},
                {"mean": p99[0], "ci_low": p99[1], "ci_high": p99[2]},
            ],
        })
    n_cells = sum(r["n"] for r in rows)
    return {
        "title": "VPP standby selection under heavy-tail churn (ACN-Data)",
        "metrics": [
            {"name": "commit_drop", "unit": "%", "objective": "min"},
            {"name": "coverage_gap", "unit": "%", "objective": "min"},
            {"name": "p99_unmet", "unit": "kW", "objective": "min"},
        ],
        "rows": rows,
        "conditions": [
            ["datasets", "ACN-Data Caltech 2019-01..03 + JPL 2019-01"],
            ["n_cells", str(n_cells)],
            ["perm_seeds", str(config.get("n_perm", "?"))],
            ["sla_alphas", ", ".join(str(a) for a in config.get("alphas", ()))],
            ["bootstrap", "percentile, n=2000"],
        ],
        "highlight": "M11",
    }


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--input", type=str,
                        default=str(_ROOT / "results" / "try16_heavy_sweep.json"))
    parser.add_argument("--output", type=str,
                        default=str(_ROOT / "results" / "try16_comparison_table.json"))
    args = parser.parse_args(argv)
    sweep = json.loads(Path(args.input).read_text())
    table = build_table(sweep)
    Path(args.output).write_text(json.dumps(table, indent=2))
    print(f"[try16] wrote {args.output}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
