"""Aggregate F-M2 sweep records to a per-(feeder, method) summary.

Replaces the throwaway ``/tmp/aggregate_C3.py`` with a versioned, repo-tracked
script. The new metric breakdown introduced in Phase D-1 (NEXT_STEPS.md §3)
is reported as separate columns:

  * ``voltage_violation_ratio``              — legacy combined ratio
  * ``voltage_violation_baseline_only``      — pre-existing (no-DER) violations
  * ``voltage_violation_dispatch_induced``   — controller-introduced violations

Older sweep JSONs that pre-date Phase D-1 only carry the combined ratio;
the missing columns are reported as ``""`` to keep the schema stable.

Usage:

    PYTHONPATH=src .venv/bin/python -m tools.aggregate_results \\
        test/mvp_try11/results/try11_FM2_results.json \\
        --out test/mvp_try11/results/FM2_per_condition_metrics.csv
"""

from __future__ import annotations

import argparse
import csv
import json
import statistics
from collections import defaultdict
from pathlib import Path

# Metrics we summarise. Order matters — it drives the CSV column order.
SUMMARISED_METRICS: tuple[str, ...] = (
    "sla_violation_ratio",
    "voltage_violation_ratio",
    "voltage_violation_baseline_only",
    "voltage_violation_dispatch_induced",
    "line_overload_ratio",
    "max_line_load_pct",
    "min_voltage_pu",
    "max_voltage_pu",
)


def _safe_mean(xs: list[float]) -> float:
    return statistics.fmean(xs) if xs else float("nan")


def _safe_max(xs: list[float]) -> float:
    return max(xs) if xs else float("nan")


def aggregate(records: list[dict[str, object]]) -> list[dict[str, object]]:
    """Group records by (feeder, method_label) and reduce metrics to summaries.

    Per group we report mean and max of every metric in
    ``SUMMARISED_METRICS``, plus the number of contributing seeds.
    """
    groups: dict[tuple[str, str], list[dict[str, object]]] = defaultdict(list)
    for r in records:
        feeder = str(r.get("feeder", ""))
        label = str(r.get("method_label", r.get("method", "")))
        groups[(feeder, label)].append(r)

    rows: list[dict[str, object]] = []
    for (feeder, label), bucket in sorted(groups.items()):
        row: dict[str, object] = {
            "feeder": feeder,
            "method_label": label,
            "n_records": len(bucket),
        }
        for metric in SUMMARISED_METRICS:
            values: list[float] = []
            for r in bucket:
                metrics = r.get("metrics") or {}
                if isinstance(metrics, dict) and metric in metrics:
                    v = metrics[metric]
                    if isinstance(v, (int, float)) and v == v:  # finite check
                        values.append(float(v))
            row[f"{metric}_mean"] = _safe_mean(values) if values else ""
            row[f"{metric}_max"] = _safe_max(values) if values else ""
        rows.append(row)
    return rows


def write_csv(path: Path, rows: list[dict[str, object]]) -> None:
    if not rows:
        path.write_text("", encoding="utf-8")
        return
    fieldnames = list(rows[0].keys())
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=fieldnames)
        writer.writeheader()
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "results_json",
        type=Path,
        help="Sweep results JSON (e.g. try11_FM2_results.json)",
    )
    parser.add_argument(
        "--out",
        type=Path,
        default=None,
        help="Output CSV path (default: alongside the input, *_per_condition_metrics.csv)",
    )
    args = parser.parse_args()

    payload = json.loads(args.results_json.read_text(encoding="utf-8"))
    records = payload.get("records", [])
    if not isinstance(records, list):
        raise ValueError("'records' field must be a list")

    rows = aggregate(records)

    out_path = args.out or args.results_json.with_name(
        args.results_json.stem + "_per_condition_metrics.csv"
    )
    write_csv(out_path, rows)
    print(f"wrote {len(rows)} rows to {out_path}")

    # Console preview: focus on the dispatch-induced column so reviewers
    # spot the controller's actual responsibility at a glance.
    print()
    header = (
        f"{'feeder':<14}{'method':<20}{'voltage_combined_mean':>22}"
        f"{'baseline_only_mean':>22}{'dispatch_induced_mean':>24}"
    )
    print(header)
    print("-" * len(header))
    for row in rows:
        print(
            f"{row['feeder']:<14}{row['method_label']:<20}"
            f"{_fmt(row['voltage_violation_ratio_mean']):>22}"
            f"{_fmt(row['voltage_violation_baseline_only_mean']):>22}"
            f"{_fmt(row['voltage_violation_dispatch_induced_mean']):>24}"
        )
    return 0


def _fmt(v: object) -> str:
    if isinstance(v, float):
        return f"{v * 100:.2f}%"
    return "—"


if __name__ == "__main__":
    raise SystemExit(main())
