"""MS-D5 smoke test — real-data trace adapter (PWRS C2 path).

Phase D-5 (NEXT_STEPS.md §7) ships ``real_data_trace`` — the bridge from
a registered ``DatasetTimeSeries`` to the simulator's ``ChurnTrace``.
The full reviewer-grade validation requires actually fetching CAISO /
AEMO / Pecan Street data via ``tools/fetch_caiso.py`` (network and / or
academic registration required); this smoke test verifies the adapter
end-to-end against the demo CSVs already shipped under
``test/mvp_try11/data/`` (= published-schema synthetics that mirror
real CAISO and AEMO files), so we know the pipeline works the moment
real data lands at ``$GRIDFLOW_DATASET_ROOT/<id>/data.csv``.

Verifies:

  1. ``build_trace_from_load_signal`` consumes a CAISO-shape CSV (via
     :class:`gridflow.adapter.dataset.CAISOLoader`) and returns a
     :class:`ChurnTrace` whose shape matches the synthetic generators
     (so ``grid_simulate`` will accept it).
  2. ``build_trace_from_active_count`` consumes an AEMO-shape CSV
     (active count = ``n_units_online``) and returns a usable trace.
  3. End-to-end: feed the real-data trace through ``grid_simulate`` +
     ``BenchmarkHarness`` and check that the same metrics come out as
     for a synthetic trace (no NaN, no exceptions).
"""

from __future__ import annotations

import os
import shutil
import tempfile
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkHarness
from gridflow.adapter.dataset import (
    AEMO_TESLA_VPP_METADATA,
    CAISO_SYSTEM_LOAD_METADATA,
    AEMOTeslaVPPLoader,
    CAISOLoader,
)
from gridflow.domain.dataset import DatasetSpec

from tools.der_pool import make_default_pool
from tools.feeder_config import feeder_active_pool, get_feeder_config
from tools.feeders import map_pool_to_feeder
from tools.grid_metrics import GRID_METRICS
from tools.grid_simulator import grid_simulate, to_grid_experiment_result
from tools.real_data_trace import (
    build_trace_from_active_count,
    build_trace_from_load_signal,
    trace_summary,
)
from tools.sdp_grid_aware import solve_sdp_grid_aware
from tools.vpp_metrics import VPP_METRICS
from tools.vpp_simulator import all_standby_dispatch_policy

DEMO_DIR = Path(__file__).resolve().parent.parent / "data"
CAISO_DEMO = DEMO_DIR / "caiso_system_load_demo.csv"
AEMO_DEMO = DEMO_DIR / "aemo_tesla_vpp_demo.csv"


def _stage_demo_csv(tmp_root: Path, dataset_id: str, src: Path) -> None:
    """Copy a demo CSV into the loader's expected path layout."""
    target = tmp_root.joinpath(*dataset_id.split("/")) / "data.csv"
    target.parent.mkdir(parents=True, exist_ok=True)
    shutil.copyfile(src, target)


def _resolve_real_data_pipeline(
    failures: list[str], tmp_root: Path
) -> None:
    os.environ["GRIDFLOW_DATASET_ROOT"] = str(tmp_root)

    # Stage the demo CSVs at the canonical dataset_ids
    _stage_demo_csv(tmp_root, CAISO_SYSTEM_LOAD_METADATA.dataset_id, CAISO_DEMO)
    _stage_demo_csv(tmp_root, AEMO_TESLA_VPP_METADATA.dataset_id, AEMO_DEMO)

    pool = make_default_pool(seed=0)
    feeder = "kerber_dorf"  # easy feeder; cigre_lv has structural V_min issues
    config = get_feeder_config(feeder)
    bus_map = map_pool_to_feeder(pool, feeder)
    active_ids = feeder_active_pool(pool, config)

    # 1) CAISO load signal → ChurnTrace
    caiso_ts = CAISOLoader().load(
        DatasetSpec(dataset_id=CAISO_SYSTEM_LOAD_METADATA.dataset_id)
    )
    if not caiso_ts.timestamps_iso:
        failures.append("CAISO loader returned empty time series")
        return
    trace_caiso = build_trace_from_load_signal(
        caiso_ts, pool, sla_kw=config.sla_kw, seed=0,
        trace_id="REAL-caiso", trigger="weather",
    )
    s = trace_summary(trace_caiso)
    print(
        f"  CAISO real trace: n_steps={s['n_steps']}, "
        f"events={s['n_events']} ({s['events_by_trigger']}), "
        f"avail mean={s['availability_mean']}/{s['pool_size']}"
    )
    if s["n_events"] == 0:
        failures.append(
            "CAISO load signal produced 0 events — threshold mis-calibrated"
        )
    if s["n_steps"] != len(caiso_ts.timestamps_iso):
        failures.append(
            f"CAISO trace n_steps={s['n_steps']} ≠ "
            f"dataset n_timestamps={len(caiso_ts.timestamps_iso)}"
        )

    # 2) AEMO active-count → ChurnTrace
    aemo_ts = AEMOTeslaVPPLoader().load(
        DatasetSpec(
            dataset_id=AEMO_TESLA_VPP_METADATA.dataset_id,
            channel_filter=("n_units_online",),
        )
    )
    trace_aemo = build_trace_from_active_count(
        aemo_ts, pool, sla_kw=config.sla_kw, seed=0,
        trace_id="REAL-aemo", count_channel="n_units_online",
        trigger="commute",
    )
    s2 = trace_summary(trace_aemo)
    print(
        f"  AEMO real trace : n_steps={s2['n_steps']}, "
        f"events={s2['n_events']} ({s2['events_by_trigger']}), "
        f"avail mean={s2['availability_mean']}/{s2['pool_size']}"
    )
    if s2["n_events"] == 0:
        failures.append(
            "AEMO active count produced 0 events — threshold mis-calibrated"
        )

    # 3) End-to-end: simulate one of the real-data traces and check
    # the metrics dict comes out clean (no NaN, no exceptions).
    sol = solve_sdp_grid_aware(
        pool, active_ids, dict(config.burst_dict()),
        bus_map=bus_map, feeder_name=feeder,
        v_max_pu=1.05, line_max_pct=100.0, mode="M7-strict-grid",
    )
    if not sol.feasible:
        failures.append("M7 must be feasible on kerber_dorf for the smoke test")
        return
    run = grid_simulate(
        pool=pool, active_ids=active_ids,
        standby_ids=frozenset(sol.standby_ids),
        trace=trace_caiso, feeder_name=feeder, bus_map=bus_map,
        dispatch_policy=all_standby_dispatch_policy,
        sample_every=24,
    )
    result = to_grid_experiment_result(
        run, pool=pool, active_ids=active_ids,
        standby_ids=frozenset(sol.standby_ids),
        trace=trace_caiso,
        experiment_id="msD5_caiso_M7", scenario_pack_id="try11_msD5",
        method_label="M7-strict",
    )
    summary = BenchmarkHarness(metrics=VPP_METRICS + GRID_METRICS).evaluate(result)
    metrics = dict(summary.values)
    for key in (
        "sla_violation_ratio",
        "voltage_violation_ratio",
        "voltage_violation_baseline_only",
        "voltage_violation_dispatch_induced",
    ):
        v = metrics.get(key)
        if not isinstance(v, (int, float)) or v != v:  # NaN check
            failures.append(f"metric {key} not finite: {v}")
    print(
        f"  real-data sweep on M7 (kerber_dorf):"
        f" sla_v={metrics['sla_violation_ratio'] * 100:.2f}%,"
        f" V_combined={metrics['voltage_violation_ratio'] * 100:.2f}%,"
        f" V_dispatch_induced={metrics['voltage_violation_dispatch_induced'] * 100:.2f}%"
    )


def main() -> int:
    failures: list[str] = []
    if not CAISO_DEMO.exists() or not AEMO_DEMO.exists():
        print(f"[MS-D5] missing demo fixtures: {CAISO_DEMO}, {AEMO_DEMO}")
        return 1

    saved_env = os.environ.get("GRIDFLOW_DATASET_ROOT")
    with tempfile.TemporaryDirectory() as tmp:
        try:
            _resolve_real_data_pipeline(failures, Path(tmp))
        finally:
            if saved_env is None:
                os.environ.pop("GRIDFLOW_DATASET_ROOT", None)
            else:
                os.environ["GRIDFLOW_DATASET_ROOT"] = saved_env

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-D5 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
