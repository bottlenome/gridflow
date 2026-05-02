"""CAISO 5-minute system load dataset loader.

Source: California ISO Open Access Same-time Information System (OASIS)
URL:    http://oasis.caiso.com/
License: Public-Domain (US federal energy information)

CAISO publishes 5-minute and hourly load data freely. This loader reads
a locally cached CSV (downloaded by the contributor) and exposes:
  ``system_load_mw`` — total system load (MW)

To use:
  1. Visit http://oasis.caiso.com/ and download SLD_FCST or RTM data
  2. Save as ``$GRIDFLOW_DATASET_ROOT/caiso/system_load_5min/<version>/data.csv``
  3. Set sha256 in the metadata for verification

CAISO is **public domain** so the metadata can list a sha256 of the
canonical published file once a contributor verifies one.
"""

from __future__ import annotations

import csv
import hashlib
import os
from pathlib import Path

from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetMetadata,
    DatasetSpec,
    DatasetTimeSeries,
)

CAISO_SYSTEM_LOAD_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="caiso/system_load_5min/v1",
    title="CAISO System Load (5-minute)",
    description=(
        "Real-time system load (MW) for the California ISO control area, "
        "5-minute resolution. Public-domain data published via OASIS."
    ),
    source="California ISO",
    license=DatasetLicense.PUBLIC_DOMAIN,
    retrieval_url="http://oasis.caiso.com/",
    doi="",
    retrieval_method="public_download",
    sha256="",  # filled per slice
    time_resolution_seconds=300,
    period_start_iso="",
    period_end_iso="",
    units=(("system_load_mw", "MW"),),
    contributors=(),
    added_at_iso="2026-04-29T00:00:00Z",
)


def _resolve_local_path(dataset_id: str) -> Path:
    root = os.environ.get("GRIDFLOW_DATASET_ROOT")
    base = Path(root) if root else Path.home() / ".gridflow" / "datasets"
    return base.joinpath(*dataset_id.split("/")) / "data.csv"


class CAISOLoader:
    """Loader for CAISO OASIS load CSV slices."""

    name: str = "caiso"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("caiso/")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")
        path = _resolve_local_path(spec.dataset_id)
        if not path.exists():
            raise FileNotFoundError(
                f"CAISO CSV not found at {path}. Download from "
                f"http://oasis.caiso.com/ and place under "
                f"$GRIDFLOW_DATASET_ROOT/{spec.dataset_id}/data.csv"
            )

        # Expect: ts_iso, system_load_mw
        timestamps: list[str] = []
        loads: list[float] = []
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                timestamps.append(row["ts_iso"])
                loads.append(float(row.get("system_load_mw", "0")))

        if spec.time_range:
            start_iso, end_iso = spec.time_range
            kept = [(t, load) for t, load in zip(timestamps, loads, strict=True) if start_iso <= t < end_iso]
            timestamps = [t for t, _ in kept]
            loads = [load for _, load in kept]

        all_channels = (("system_load_mw", "MW", tuple(loads)),)
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
            CAISO_SYSTEM_LOAD_METADATA,
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
