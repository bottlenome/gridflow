#!/usr/bin/env python3
"""Plot DER penetration vs voltage metrics for the MVP sweep.

Reads one JSON per DER level (typically ``results/der_*_run1.json``),
computes:

    * ``voltage_deviation`` — RMSE against 1.0 pu (same definition as
      the gridflow Benchmark Harness voltage_deviation metric).
    * ``voltage_violation_ratio`` — fraction of buses whose magnitude
      falls outside the ANSI C84.1 Range A band [0.95, 1.05] pu.
    * ``max_over_voltage`` / ``min_under_voltage`` — headroom signals.

Produces a single matplotlib figure showing all four series against
``parameters.der_penetration_pct``.

Usage:
    python plot_hosting_capacity.py results/der_*_run1.json -o out.png
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path

import numpy as np

_FILE_RE = re.compile(r"der_(?P<pct>\d+)_run(?P<run>\d+)\.json$")

# ANSI C84.1 Range A band (normal service voltage range) — widely used
# in hosting capacity literature (see research_landscape.md C-10).
V_LOW = 0.95
V_HIGH = 1.05


@dataclass
class Point:
    pct: int
    voltage_deviation: float
    violation_ratio: float
    max_over: float
    min_under: float
    n_buses: int


def _load_experiment(path: Path) -> tuple[int, np.ndarray]:
    """Return (der_penetration_pct, voltages_vector) from an experiment JSON."""
    with path.open() as fh:
        data = json.load(fh)
    if "result_path" in data and "node_results" not in data:
        with open(data["result_path"]) as fh:
            data = json.load(fh)

    # der_penetration_pct lives in parameters as a sorted tuple-of-pairs
    # (CLAUDE.md §0.1); gridflow serializes it as a dict.
    params = data.get("metadata", {}).get("parameters", {}) or {}
    pct = int(params.get("der_penetration_pct", -1))

    if not data.get("node_results"):
        raise ValueError(f"{path}: no node_results")
    voltages: list[float] = []
    for nr in data["node_results"]:
        voltages.extend(float(v) for v in nr["voltages"])
    return pct, np.asarray(voltages, dtype=np.float64)


def _compute_point(pct: int, voltages: np.ndarray) -> Point:
    # Filter out any bus rows that came back as zero (disconnected phases).
    mask = voltages > 0
    v = voltages[mask]
    if v.size == 0:
        return Point(pct, 0.0, 0.0, 0.0, 0.0, 0)
    voltage_deviation = float(np.sqrt(np.mean((v - 1.0) ** 2)))
    over = v > V_HIGH
    under = v < V_LOW
    violation_ratio = float((over | under).sum()) / v.size
    max_over = float(max(0.0, v.max() - V_HIGH))
    min_under = float(max(0.0, V_LOW - v.min()))
    return Point(
        pct=pct,
        voltage_deviation=voltage_deviation,
        violation_ratio=violation_ratio,
        max_over=max_over,
        min_under=min_under,
        n_buses=int(v.size),
    )


def _collect(paths: list[Path]) -> list[Point]:
    seen: dict[int, Point] = {}
    for path in paths:
        m = _FILE_RE.search(path.name)
        if m is None:
            print(f"[skip] {path}: does not match der_<pct>_run<N>.json", file=sys.stderr)
            continue
        pct, voltages = _load_experiment(path)
        # Cross-check the filename matches parameters.der_penetration_pct
        # so we fail loudly on mismatched inputs.
        file_pct = int(m["pct"])
        if pct != -1 and pct != file_pct:
            print(
                f"[warn] {path}: filename pct={file_pct} but "
                f"parameters.der_penetration_pct={pct}",
                file=sys.stderr,
            )
            pct = file_pct
        elif pct == -1:
            pct = file_pct
        if pct in seen:
            continue  # first run only (deterministic, so runs are equal)
        seen[pct] = _compute_point(pct, voltages)
    return sorted(seen.values(), key=lambda p: p.pct)


def _render(points: list[Point], outfile: Path) -> None:
    import matplotlib
    matplotlib.use("Agg")  # headless
    import matplotlib.pyplot as plt

    xs = [p.pct for p in points]
    dev = [p.voltage_deviation for p in points]
    vio = [p.violation_ratio for p in points]
    over = [p.max_over for p in points]
    under = [p.min_under for p in points]

    fig, axes = plt.subplots(2, 2, figsize=(10, 7), sharex=True)
    fig.suptitle(
        "IEEE 13 × DER penetration sweep — gridflow MVP try 1",
        fontsize=13,
    )

    ax = axes[0, 0]
    ax.plot(xs, dev, marker="o", color="C0")
    ax.set_title("voltage_deviation (RMSE vs 1.0 pu)")
    ax.set_ylabel("pu")
    ax.grid(True, alpha=0.3)

    ax = axes[0, 1]
    ax.plot(xs, vio, marker="o", color="C1")
    ax.set_title(f"violation_ratio (buses outside [{V_LOW}, {V_HIGH}] pu)")
    ax.set_ylabel("fraction")
    ax.set_ylim(-0.02, 1.02)
    ax.grid(True, alpha=0.3)

    ax = axes[1, 0]
    ax.plot(xs, over, marker="o", color="C3", label="max over")
    ax.plot(xs, under, marker="s", color="C2", label="min under")
    ax.set_title("headroom vs ANSI C84.1 Range A")
    ax.set_xlabel("DER penetration [%]")
    ax.set_ylabel("|Δ pu|")
    ax.legend()
    ax.grid(True, alpha=0.3)

    ax = axes[1, 1]
    ax.axis("off")
    text_lines = ["Summary", ""]
    for p in points:
        text_lines.append(
            f"  DER {p.pct:>3d}%  | dev={p.voltage_deviation:.4f}  "
            f"vio={p.violation_ratio:.2%}  buses={p.n_buses}"
        )
    ax.text(
        0.02, 0.95, "\n".join(text_lines),
        family="monospace", fontsize=9, va="top", ha="left",
    )

    fig.tight_layout(rect=(0, 0, 1, 0.96))
    outfile.parent.mkdir(parents=True, exist_ok=True)
    fig.savefig(outfile, dpi=120)
    print(f"wrote {outfile}")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("files", nargs="+", type=Path, help="results/der_*_run1.json")
    parser.add_argument(
        "-o", "--output",
        type=Path, default=Path("hosting_capacity.png"),
        help="output PNG path",
    )
    parser.add_argument(
        "--no-plot",
        action="store_true",
        help="just print the summary, don't touch matplotlib",
    )
    args = parser.parse_args(argv)

    points = _collect(args.files)
    if not points:
        print("no matching experiment JSONs", file=sys.stderr)
        return 1

    print("pct | voltage_deviation | violation_ratio | max_over | min_under | n_buses")
    print("----+-------------------+-----------------+----------+-----------+--------")
    for p in points:
        print(
            f"{p.pct:>3d} | {p.voltage_deviation:>17.6f} | "
            f"{p.violation_ratio:>15.4f} | {p.max_over:>8.4f} | "
            f"{p.min_under:>9.4f} | {p.n_buses:>7d}"
        )

    if args.no_plot:
        return 0
    try:
        _render(points, args.output)
    except Exception as exc:  # pragma: no cover - depends on matplotlib env
        print(f"[warn] plotting skipped: {exc}", file=sys.stderr)
        return 0
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
