"""NREL ResStock simulated residential load dataset loader.

Source: National Renewable Energy Laboratory (NREL) ResStock project
URL:    https://resstock.nrel.gov/
License: CC-BY-4.0 (NREL public release)

NREL ResStock provides high-resolution synthetic but physics-based
residential load datasets representing the U.S. building stock. While
"synthetic" in origin, it is widely accepted in distribution-grid
research as a quasi-real-data substitute due to extensive calibration.

Channels:
  ``total_electricity_kw`` — household total electricity (kW)
  ``hvac_electricity_kw`` — HVAC subset
  ``ev_electricity_kw``    — EV charger subset (when applicable)
"""

from __future__ import annotations

import csv
import hashlib
import os
from collections import defaultdict
from pathlib import Path

from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetMetadata,
    DatasetSpec,
    DatasetTimeSeries,
)

NREL_RESSTOCK_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="nrel/resstock_residential/v1",
    title="NREL ResStock Residential Load (15-minute)",
    description=(
        "Physics-calibrated synthetic residential electricity loads "
        "covering the U.S. building stock at 15-minute resolution. Used "
        "as quasi-real-data baseline for distribution-grid VPP research."
    ),
    source="NREL",
    license=DatasetLicense.CC_BY_4_0,
    retrieval_url="https://resstock.nrel.gov/",
    doi="",
    retrieval_method="public_download",
    sha256="",
    time_resolution_seconds=900,
    period_start_iso="",
    period_end_iso="",
    units=(
        ("total_electricity_kw", "kW"),
        ("hvac_electricity_kw", "kW"),
        ("ev_electricity_kw", "kW"),
    ),
    contributors=(),
    added_at_iso="2026-04-29T00:00:00Z",
)


def _resolve_local_path(dataset_id: str) -> Path:
    root = os.environ.get("GRIDFLOW_DATASET_ROOT")
    base = Path(root) if root else (Path.home() / ".gridflow" / "datasets")
    return base.joinpath(*dataset_id.split("/")) / "data.csv"


class NRELResStockLoader:
    """Loader for NREL ResStock CSV slices."""

    name: str = "nrel_resstock"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("nrel/resstock_")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")
        path = _resolve_local_path(spec.dataset_id)
        if not path.exists():
            raise FileNotFoundError(
                f"NREL ResStock CSV not found at {path}. Download from "
                f"https://resstock.nrel.gov/ and place at "
                f"$GRIDFLOW_DATASET_ROOT/{spec.dataset_id}/data.csv"
            )

        per_ts_total: dict[str, float] = defaultdict(float)
        per_ts_hvac: dict[str, float] = defaultdict(float)
        per_ts_ev: dict[str, float] = defaultdict(float)
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ts = row["ts_iso"]
                per_ts_total[ts] += float(row.get("total_electricity_kw", "0"))
                per_ts_hvac[ts] += float(row.get("hvac_electricity_kw", "0"))
                per_ts_ev[ts] += float(row.get("ev_electricity_kw", "0"))

        timestamps = sorted(per_ts_total.keys())
        if spec.time_range:
            start_iso, end_iso = spec.time_range
            timestamps = [t for t in timestamps if start_iso <= t < end_iso]

        all_channels = (
            ("total_electricity_kw", "kW", tuple(per_ts_total.get(t, 0.0) for t in timestamps)),
            ("hvac_electricity_kw", "kW", tuple(per_ts_hvac.get(t, 0.0) for t in timestamps)),
            ("ev_electricity_kw", "kW", tuple(per_ts_ev.get(t, 0.0) for t in timestamps)),
        )
        if spec.channel_filter:
            channels = tuple(c for c in all_channels if c[0] in set(spec.channel_filter))
        else:
            channels = all_channels

        h = hashlib.sha256()
        for _, _, values in channels:
            for v in values:
                h.update(str(v).encode())

        from dataclasses import replace

        sliced_metadata = replace(
            NREL_RESSTOCK_METADATA,
            sha256=h.hexdigest(),
            period_start_iso=timestamps[0] if timestamps else "",
            period_end_iso=timestamps[-1] if timestamps else "",
        )
        return DatasetTimeSeries(
            spec=spec,
            metadata=sliced_metadata,
            timestamps_iso=tuple(timestamps),
            channels=channels,
        )
