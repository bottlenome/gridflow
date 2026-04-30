"""AEMO South Australia Tesla VPP report dataset loader.

Source: Australian Energy Market Operator (AEMO) South Australia VPP report
URL:    https://aemo.com.au/-/media/files/electricity/nem/security_and_reliability/
        ancillary_services/vpp/sa-vpp-update-...
License: Public-Domain (AEMO publishes for transparency)

AEMO publishes periodic reports on the South Australian Tesla Powerwall
VPP performance, including aggregate availability and dispatch records.
This loader reads a tabular extraction (CSV) of those reports.

Expected CSV schema:
  ts_iso, n_units_online, total_capacity_kw, frequency_hz_observed

Channels:
  ``n_units_online``      — count
  ``total_capacity_kw``   — kW
  ``frequency_hz``        — Hz
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


AEMO_TESLA_VPP_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="aemo/tesla_vpp_sa/v1",
    title="AEMO South Australia Tesla VPP — Aggregate Availability",
    description=(
        "Tabular extraction from AEMO's quarterly South Australia Virtual "
        "Power Plant (Tesla Powerwall) report. Includes per-interval "
        "online unit counts, aggregate capacity, and observed system "
        "frequency. Public-domain. Used as real-world VPP availability "
        "validation in try11."
    ),
    source="Australian Energy Market Operator",
    license=DatasetLicense.PUBLIC_DOMAIN,
    retrieval_url=(
        "https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/"
        "nem-events-and-reports/vpp-demonstrations"
    ),
    doi="",
    retrieval_method="public_download",
    sha256="",
    time_resolution_seconds=300,
    period_start_iso="",
    period_end_iso="",
    units=(
        ("n_units_online", "count"),
        ("total_capacity_kw", "kW"),
        ("frequency_hz", "Hz"),
    ),
    contributors=(),
    added_at_iso="2026-04-29T00:00:00Z",
)


def _resolve_local_path(dataset_id: str) -> Path:
    root = os.environ.get("GRIDFLOW_DATASET_ROOT")
    base = Path(root) if root else (Path.home() / ".gridflow" / "datasets")
    return base.joinpath(*dataset_id.split("/")) / "data.csv"


class AEMOTeslaVPPLoader:
    """Loader for AEMO South Australia Tesla VPP CSV."""

    name: str = "aemo_tesla_vpp"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("aemo/tesla_vpp_")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")
        path = _resolve_local_path(spec.dataset_id)
        if not path.exists():
            raise FileNotFoundError(
                f"AEMO VPP CSV not found at {path}. Extract tabular data "
                f"from the AEMO VPP report and place at "
                f"$GRIDFLOW_DATASET_ROOT/{spec.dataset_id}/data.csv"
            )
        timestamps: list[str] = []
        units_online: list[float] = []
        cap_kw: list[float] = []
        freq_hz: list[float] = []
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                timestamps.append(row["ts_iso"])
                units_online.append(float(row.get("n_units_online", "0")))
                cap_kw.append(float(row.get("total_capacity_kw", "0")))
                freq_hz.append(float(row.get("frequency_hz_observed", "50")))

        if spec.time_range:
            start_iso, end_iso = spec.time_range
            keep = [
                i for i, t in enumerate(timestamps)
                if start_iso <= t < end_iso
            ]
            timestamps = [timestamps[i] for i in keep]
            units_online = [units_online[i] for i in keep]
            cap_kw = [cap_kw[i] for i in keep]
            freq_hz = [freq_hz[i] for i in keep]

        all_channels = (
            ("n_units_online", "count", tuple(units_online)),
            ("total_capacity_kw", "kW", tuple(cap_kw)),
            ("frequency_hz", "Hz", tuple(freq_hz)),
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
            AEMO_TESLA_VPP_METADATA,
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
