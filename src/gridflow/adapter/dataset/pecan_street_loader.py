"""Pecan Street residential EV / PV / battery dataset loader.

Source: Pecan Street Inc. (https://www.pecanstreet.org/dataport/)
License: Proprietary research-use (academic registration required)

This loader is a **stub**: it does NOT redistribute the dataset payload
(license forbids), but it knows the metadata schema and how to read a
locally-cached CSV that contributors fetch themselves.

To use:
  1. Register at https://www.pecanstreet.org/dataport/
  2. Download the residential EV charging dataset for your range
  3. Save as ``$GRIDFLOW_DATASET_ROOT/pecanstreet/residential_ev/<version>/data.csv``
  4. Set the sha256 below to match your file (one-line: ``sha256sum data.csv``)
  5. Use ``DatasetSpec(dataset_id="pecanstreet/residential_ev/<version>", ...)``

Expected CSV schema (one row per (timestamp, household)):
  ``ts_iso, household_id, ev_power_kw, ev_connected``

The loader aggregates per-timestep:
  ``aggregate_active_count`` = number of households with ev_connected=1
  ``aggregate_active_kw``    = sum of ev_power_kw across households
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

# Registered metadata for the canonical Pecan Street EV slice.
# The sha256 is empty here because the actual file lives only on the
# contributor's machine; the loader fills the sliced sha256 at load time.
PECAN_STREET_RESIDENTIAL_EV_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="pecanstreet/residential_ev/v1",
    title="Pecan Street Residential EV Charging Dataport",
    description=(
        "5-minute residential EV charging power and connection state for "
        "Austin, TX households. Acquired via Pecan Street Dataport "
        "(academic registration required). Used as primary VPP DER "
        "availability validation in try11."
    ),
    source="Pecan Street Inc.",
    license=DatasetLicense.PROPRIETARY_RESEARCH,
    retrieval_url="https://www.pecanstreet.org/dataport/",
    doi="",
    retrieval_method="registration_required",
    sha256="",
    time_resolution_seconds=300,
    period_start_iso="",
    period_end_iso="",
    units=(
        ("aggregate_active_count", "count"),
        ("aggregate_active_kw", "kW"),
    ),
    contributors=(),  # filled when a contributor adds their cache
    added_at_iso="2026-04-29T00:00:00Z",
)


def _resolve_local_path(dataset_id: str) -> Path:
    """Resolve the local CSV path for a given dataset_id.

    Two ways:
      * env var ``GRIDFLOW_DATASET_ROOT`` (preferred)
      * default ``~/.gridflow/datasets/<dataset_id>/data.csv``
    """
    root = os.environ.get("GRIDFLOW_DATASET_ROOT")
    base = Path(root) if root else Path.home() / ".gridflow" / "datasets"
    return base.joinpath(*dataset_id.split("/")) / "data.csv"


class PecanStreetLoader:
    """Loader for Pecan Street Dataport CSV slices."""

    name: str = "pecanstreet"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("pecanstreet/")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")

        path = _resolve_local_path(spec.dataset_id)
        if not path.exists():
            raise FileNotFoundError(
                f"Pecan Street CSV not found at {path}. See docstring of pecan_street_loader.py for setup."
            )

        # Read CSV; expect columns: ts_iso, household_id, ev_power_kw, ev_connected
        per_ts_count: dict[str, int] = defaultdict(int)
        per_ts_kw: dict[str, float] = defaultdict(float)
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                ts = row["ts_iso"]
                connected = bool(int(row.get("ev_connected", "0")))
                power = float(row.get("ev_power_kw", "0"))
                if connected:
                    per_ts_count[ts] += 1
                per_ts_kw[ts] += power

        # Apply time_range filter
        timestamps = sorted(per_ts_count.keys() | per_ts_kw.keys())
        if spec.time_range:
            start_iso, end_iso = spec.time_range
            timestamps = [t for t in timestamps if start_iso <= t < end_iso]

        active_count = tuple(float(per_ts_count.get(t, 0)) for t in timestamps)
        active_kw = tuple(per_ts_kw.get(t, 0.0) for t in timestamps)

        all_channels = (
            ("aggregate_active_count", "count", active_count),
            ("aggregate_active_kw", "kW", active_kw),
        )
        if spec.channel_filter:
            channels = tuple(c for c in all_channels if c[0] in set(spec.channel_filter))
        else:
            channels = all_channels

        # Compute sha256 for this slice
        h = hashlib.sha256()
        for _, _, values in channels:
            for v in values:
                h.update(str(v).encode())
        sliced_sha = h.hexdigest()

        from dataclasses import replace

        sliced_metadata = replace(
            PECAN_STREET_RESIDENTIAL_EV_METADATA,
            sha256=sliced_sha,
            period_start_iso=timestamps[0] if timestamps else "",
            period_end_iso=timestamps[-1] if timestamps else "",
        )

        return DatasetTimeSeries(
            spec=spec,
            metadata=sliced_metadata,
            timestamps_iso=tuple(timestamps),
            channels=channels,
        )
