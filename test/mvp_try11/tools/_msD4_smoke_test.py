"""MS-D4 smoke test — feasibility envelope tooling end-to-end.

Phase D-4 (NEXT_STEPS.md §6) ships ``run_envelope`` (a tiny variant of
the F-M2 sweep parameterised by α and β) and ``aggregate_envelope``
(per-(feeder, α, β) summary + matplotlib heatmap). Running the full
3 × 6 × 4 × 8 × 3 cell sweep is the user's prerogative (~ 1 hour); this
smoke test exercises the pipeline on a tiny 1×2×2×1×1 = 4-cell sweep:

  feeder = cigre_lv
  α      ∈ {0.05, 0.20}
  β      ∈ {0.5, 1.0}
  trace  = C1
  seed   = 0
  method = M7   (M8 sized at scale=200 takes ~10s/cell; M7 is ~5×
                 faster and still exercises the same pipeline)

Verifies:

  1. ``envelope_config`` rescales sla_kw and burst proportionally.
  2. ``run_one_envelope_cell`` returns a record with α/β fields and a
     metrics dict.
  3. ``aggregate.aggregate`` returns one row per (feeder, α, β) cell
     with feasibility_rate ∈ [0, 1].
  4. Heatmap rendering succeeds when matplotlib is available, and the
     output PNG is non-empty.
"""

from __future__ import annotations

from pathlib import Path
from tempfile import TemporaryDirectory

from tools.aggregate_envelope import aggregate, render_heatmaps
from tools.run_envelope import (
    build_cell_list,
    envelope_config,
    run_one_envelope_cell,
)


def main() -> int:
    failures: list[str] = []

    # 1) envelope_config sanity
    cfg_low = envelope_config("cigre_lv", alpha=0.05, beta=0.5)
    cfg_high = envelope_config("cigre_lv", alpha=0.20, beta=1.0)
    if cfg_low.sla_kw >= cfg_high.sla_kw:
        failures.append(
            f"sla_kw should grow with α: low={cfg_low.sla_kw}, high={cfg_high.sla_kw}"
        )
    burst_low = cfg_low.burst_dict()
    burst_high = cfg_high.burst_dict()
    if burst_low["commute"] >= burst_high["commute"]:
        failures.append(
            f"burst should grow with α·β: low={burst_low['commute']}, "
            f"high={burst_high['commute']}"
        )
    print(
        f"  cfg(α=0.05,β=0.5):  sla_kw={cfg_low.sla_kw}, "
        f"burst.commute={burst_low['commute']:.1f}"
    )
    print(
        f"  cfg(α=0.20,β=1.0):  sla_kw={cfg_high.sla_kw}, "
        f"burst.commute={burst_high['commute']:.1f}"
    )

    # 2) Tiny 4-cell sweep
    cells = build_cell_list(
        feeders=("cigre_lv",),
        alphas=(0.05, 0.20),
        betas=(0.5, 1.0),
        scale=200,
        traces=("C1",),
        method="M7",
        seeds=(0,),
    )
    if len(cells) != 4:
        failures.append(f"expected 4 cells, got {len(cells)}")

    records: list[dict] = []
    for cell in cells:
        rec = run_one_envelope_cell(cell)
        records.append(rec)
        print(
            f"  cell {cell[1:4]}: feasible={not rec.get('infeasible')}, "
            f"design_cost={rec.get('design_cost')}, "
            f"elapsed={rec.get('elapsed_s')}s"
        )

    for rec in records:
        for key in ("feeder", "alpha", "beta", "scale", "trace_id", "method", "seed"):
            if key not in rec:
                failures.append(f"missing key in record: {key}")

    # 3) Aggregate
    rows = aggregate(records)
    if len(rows) != 4:
        failures.append(f"expected 4 summary rows (1 feeder × 2 α × 2 β), got {len(rows)}")
    for row in rows:
        rate = row["feasibility_rate"]
        if not (isinstance(rate, float) and 0.0 <= rate <= 1.0):
            failures.append(f"feasibility_rate out of [0,1]: {rate}")
    print()
    print(
        f"  summary: {len(rows)} cells, "
        f"feas/total = "
        + ", ".join(f"{r['n_feasible']}/{r['n_total']}" for r in rows)
    )

    # 4) Heatmap (if matplotlib is available)
    with TemporaryDirectory() as tmpdir:
        prefix = Path(tmpdir) / "env"
        written = render_heatmaps(rows, prefix)
        if not written:
            print("  heatmap skipped (matplotlib unavailable)")
        else:
            for path in written:
                size = path.stat().st_size
                if size <= 0:
                    failures.append(f"heatmap PNG empty: {path}")
                else:
                    print(f"  heatmap rendered: {path.name} ({size} bytes)")
                    # Compare against a non-trivial floor — a rendered
                    # matplotlib PNG is always > 1 KB.
                    if size < 1024:
                        failures.append(
                            f"heatmap suspiciously small ({size} bytes): {path}"
                        )

    # 5) Sanity: at least one cell was feasible (so the pipeline really
    # exercised the metric path, not just the infeasible branch).
    if not any(not r.get("infeasible") for r in records):
        failures.append("all 4 cells reported infeasible — pipeline did not exercise simulate path")

    return _report(failures)


def _report(failures: list[str]) -> int:
    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D4 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
