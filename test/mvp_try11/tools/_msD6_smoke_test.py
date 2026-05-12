"""MS-D6 smoke test — multi-scale scaling tooling end-to-end.

Phase D-6 (NEXT_STEPS.md §8) ships ``run_scaling`` (a sweep variant
focused on N) and ``plot_scaling`` (cost / solve-time curves). Running
the full 4 × 4 × 3 = 48-cell sweep at N=5000 takes too long for an
in-process smoke test (the Theorem 2 plot's headline takes minutes per
M1 cell at N=5000), so this test exercises the pipeline on a tiny
2 × 2 × 1 = 4-cell sweep:

  feeder = cigre_lv
  trace  = C1
  scales ∈ {50, 200}
  methods ∈ {M1, M4b}
  seeds  = {0}

Verifies:

  1. ``build_cell_list`` returns the expected cell count and skips the
     5000-cell entries listed in ``SKIP_AT_5000``.
  2. ``run_one_cell`` (re-imported from run_phase1_multifeeder) runs
     each cell to completion with both methods.
  3. ``aggregate`` (from plot_scaling) groups records by (method, N)
     correctly and reports finite mean_cost / mean_time.
  4. Plot rendering succeeds and produces a non-empty PNG (when
     matplotlib is available).
  5. Sanity: at N=200 the MILP (M1) cost ≤ greedy (M4b) cost. Both
     methods achieve feasibility in the cell.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from tools.plot_scaling import aggregate, render
from tools.run_scaling import (
    SKIP_AT_5000,
    build_cell_list,
)
from tools.run_phase1_multifeeder import run_one_cell


def main() -> int:
    failures: list[str] = []

    # 1) Cell-list shape
    cells = build_cell_list(
        feeder="cigre_lv",
        scales=(50, 200),
        traces=("C1",),
        methods=("M1", "M4b"),
        seeds=(0,),
        skip_at_5000=SKIP_AT_5000,
    )
    if len(cells) != 4:
        failures.append(f"expected 4 cells, got {len(cells)}: {cells}")

    # Test that scale=5000 + M1 cell is correctly skipped
    cells_with_5000 = build_cell_list(
        feeder="cigre_lv",
        scales=(5000,),
        traces=("C1",),
        methods=("M1", "M4b"),
        seeds=(0,),
        skip_at_5000=SKIP_AT_5000,
    )
    methods_at_5000 = sorted({c[3] for c in cells_with_5000})
    if methods_at_5000 != ["M4b"]:
        failures.append(
            f"5000-scale cells should keep only M4b, got {methods_at_5000}"
        )

    # 2) Run the 4 cells
    records: list[dict] = []
    for cell in cells:
        rec = run_one_cell(cell)
        records.append(rec)
        print(
            f"  cell {cell[1]}/{cell[3]}/seed{cell[4]}: "
            f"feasible={not rec.get('infeasible') and not rec.get('error')}, "
            f"cost={rec.get('design_cost')}, "
            f"design_time_s={rec.get('design_solve_time_s')}, "
            f"elapsed={rec.get('elapsed_s')}"
        )

    feasibility_ok = all(
        not r.get("infeasible") and not r.get("error") for r in records
    )
    if not feasibility_ok:
        failures.append("at least one of the 4 cells reported infeasible / error")

    # 3) Aggregate (records use method_label, e.g. "M4b-greedy")
    data = aggregate(records)
    seen_labels = set(data.keys())
    if not any(label.startswith("M1") for label in seen_labels):
        failures.append(f"aggregate missing M1 family; got {seen_labels}")
    if not any(label.startswith("M4b") for label in seen_labels):
        failures.append(f"aggregate missing M4b family; got {seen_labels}")
    for method, per_scale in data.items():
        for scale, stats in per_scale.items():
            for key in ("mean_cost", "mean_time"):
                v = stats[key]
                if not isinstance(v, float) or v != v:
                    failures.append(
                        f"{method}@{scale}: {key} not finite ({v})"
                    )

    # 4) Plot
    with TemporaryDirectory() as tmp:
        out_png = Path(tmp) / "scaling.png"
        try:
            render(data, out_png)
        except SystemExit as e:
            print(f"  plot skipped (matplotlib unavailable): {e}")
        else:
            size = out_png.stat().st_size
            if size < 1024:
                failures.append(f"plot PNG suspiciously small ({size} B)")
            else:
                print(f"  plot rendered: {size} bytes")

    # 5) Sanity: M1 (MILP) cost ≤ M4b (greedy) cost at the same N=200,
    # following Theorem 2's ln(K)+1 bound (M4b ≤ M1·(ln 3 + 1) ≈ 2.1·M1).
    m1_label = next((lbl for lbl in seen_labels if lbl.startswith("M1")), None)
    m4b_label = next((lbl for lbl in seen_labels if lbl.startswith("M4b")), None)
    if m1_label and m4b_label:
        m1_at_200 = data[m1_label].get(200, {}).get("mean_cost")
        m4b_at_200 = data[m4b_label].get(200, {}).get("mean_cost")
        if (
            isinstance(m1_at_200, float)
            and isinstance(m4b_at_200, float)
            and m1_at_200 == m1_at_200
            and m4b_at_200 == m4b_at_200
        ):
            if m4b_at_200 + 1e-6 < m1_at_200:
                failures.append(
                    f"{m4b_label} greedy ({m4b_at_200:.1f}) < {m1_label} "
                    f"MILP ({m1_at_200:.1f}) at N=200 — MILP should be optimum"
                )
            else:
                print(
                    f"  Theorem-2 sanity: {m1_label}={m1_at_200:.0f}, "
                    f"{m4b_label}={m4b_at_200:.0f} (greedy ≥ MILP)"
                )

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D6 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
