"""MS-C2-6 smoke — end-to-end real-data-shape pipeline.

Verifies:
  1. CAISO demo CSV loads via CAISOLoader → DatasetTimeSeries
  2. AEMO demo CSV loads via AEMOTeslaVPPLoader → DatasetTimeSeries
  3. scenario_bridge produces canonical Params with provenance
  4. SyntheticLoader pipeline matches real-data-loader pipeline shape

This validates that try11's framework supports real data once contributors
drop actual CSVs in $GRIDFLOW_DATASET_ROOT.
"""

from __future__ import annotations

import os
from pathlib import Path

from gridflow.adapter.dataset import (
    AEMOTeslaVPPLoader,
    CAISOLoader,
    SyntheticLoader,
)
from gridflow.adapter.dataset.scenario_bridge import (
    dataset_to_active_count,
    pack_parameters_with_dataset,
)
from gridflow.domain.dataset import DatasetSpec
from gridflow.domain.util.params import as_params


def main() -> int:
    failures: list[str] = []

    # Set GRIDFLOW_DATASET_ROOT to point at our demo fixtures' parent
    repo_data = Path(__file__).resolve().parent.parent / "data"

    # Symlink-style: CAISOLoader expects $ROOT/<id>/data.csv
    # We arrange the layout temporarily.
    import shutil, tempfile
    tmp = Path(tempfile.mkdtemp())
    try:
        for did, src_csv in (
            ("caiso/system_load_5min/v1", repo_data / "caiso_system_load_demo.csv"),
            ("aemo/tesla_vpp_sa/v1", repo_data / "aemo_tesla_vpp_demo.csv"),
        ):
            dst = tmp.joinpath(*did.split("/")) / "data.csv"
            dst.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy(src_csv, dst)

        os.environ["GRIDFLOW_DATASET_ROOT"] = str(tmp)

        # 1. CAISO load
        caiso_loader = CAISOLoader()
        caiso_spec = DatasetSpec(dataset_id="caiso/system_load_5min/v1")
        caiso_ts = caiso_loader.load(caiso_spec)
        if caiso_ts.n_steps != 7 * 24 * 12:
            failures.append(
                f"CAISO n_steps={caiso_ts.n_steps}, expected {7*24*12}"
            )
        if caiso_ts.metadata.sha256 == "":
            failures.append("CAISO sha256 not filled")
        load_values = caiso_ts.channel("system_load_mw")
        if not all(15000 <= v <= 35000 for v in load_values):
            failures.append("CAISO load values out of [15000, 35000] MW")
        print(f"  CAISO: n_steps={caiso_ts.n_steps}, "
              f"load range=[{min(load_values):.0f}, {max(load_values):.0f}] MW, "
              f"sha256={caiso_ts.metadata.sha256[:10]}...")

        # 2. AEMO load
        aemo_loader = AEMOTeslaVPPLoader()
        aemo_spec = DatasetSpec(dataset_id="aemo/tesla_vpp_sa/v1")
        aemo_ts = aemo_loader.load(aemo_spec)
        if aemo_ts.n_steps != 30 * 24 * 12:
            failures.append(
                f"AEMO n_steps={aemo_ts.n_steps}, expected {30*24*12}"
            )
        units = aemo_ts.channel("n_units_online")
        if not all(0 <= u <= 1000 for u in units):
            failures.append("AEMO units online out of [0, 1000]")
        freqs = aemo_ts.channel("frequency_hz")
        if not all(49 <= f <= 51 for f in freqs):
            failures.append("AEMO frequency out of [49, 51] Hz")
        print(f"  AEMO: n_steps={aemo_ts.n_steps}, "
              f"units range=[{min(units):.0f}, {max(units):.0f}], "
              f"freq range=[{min(freqs):.4f}, {max(freqs):.4f}] Hz, "
              f"sha256={aemo_ts.metadata.sha256[:10]}...")

        # 3. scenario_bridge produces canonical Params with provenance
        params = pack_parameters_with_dataset(
            caiso_spec, caiso_ts.metadata,
            base_params={"feeder": "cigre_lv", "method": "M1"},
        )
        keys = {k for k, _ in params}
        for required in ("dataset_id", "dataset_sha256", "dataset_license",
                         "feeder", "method"):
            if required not in keys:
                failures.append(f"params missing key: {required}")

        # 4. Active count derivation
        counts = dataset_to_active_count(aemo_ts, count_channel="n_units_online")
        if not all(c >= 0 for c in counts):
            failures.append("active_count contains negative values")
        if len(counts) != aemo_ts.n_steps:
            failures.append(f"active_count length {len(counts)} != n_steps {aemo_ts.n_steps}")

        # 5. SyntheticLoader pipeline (cross-check)
        syn_loader = SyntheticLoader()
        syn_spec = DatasetSpec(
            dataset_id="gridflow/synthetic_vpp_churn/v1",
            params=as_params({"seed": 0, "pool_size": 50}),
        )
        syn_ts = syn_loader.load(syn_spec)
        if syn_ts.n_steps == 0:
            failures.append("synthetic n_steps == 0")
        print(f"  Synthetic: n_steps={syn_ts.n_steps}, "
              f"sha256={syn_ts.metadata.sha256[:10]}...")

    finally:
        shutil.rmtree(tmp)
        os.environ.pop("GRIDFLOW_DATASET_ROOT", None)

    if failures:
        print(f"\nFAIL: {len(failures)} issues:")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-C2-6 smoke test passed (real-data-shape pipeline validated).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
