"""JEPX (Japan Electric Power Exchange) wholesale price loader.

Source: 日本卸電力取引所 (JEPX)
URL:    https://www.jepx.org/electricpower/market-data/spot/
License: CC-BY-4.0 (JEPX permits redistribution with attribution)

JEPX publishes 30-minute spot prices freely. This loader reads a
locally cached CSV and exposes:
  ``spot_price_jpy_per_kwh`` — JEPX spot price (¥/kWh)

Time resolution: 30 minutes (= 48 slots/day, JEPX day-ahead market)
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

JEPX_SPOT_PRICE_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="jepx/spot_price/v1",
    title="JEPX Spot Market Price (30-minute)",
    description=(
        "Day-ahead spot market clearing price (¥/kWh) for the Japan "
        "Electric Power Exchange. 48 slots per day (30-min resolution)."
    ),
    source="日本卸電力取引所 JEPX",
    license=DatasetLicense.CC_BY_4_0,
    retrieval_url="https://www.jepx.org/electricpower/market-data/spot/",
    doi="",
    retrieval_method="public_download",
    sha256="",
    time_resolution_seconds=1800,
    period_start_iso="",
    period_end_iso="",
    units=(("spot_price_jpy_per_kwh", "JPY/kWh"),),
    contributors=(),
    added_at_iso="2026-04-29T00:00:00Z",
)


def _resolve_local_path(dataset_id: str) -> Path:
    root = os.environ.get("GRIDFLOW_DATASET_ROOT")
    base = Path(root) if root else (Path.home() / ".gridflow" / "datasets")
    return base.joinpath(*dataset_id.split("/")) / "data.csv"


class JEPXLoader:
    """Loader for JEPX spot market CSV."""

    name: str = "jepx"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("jepx/")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")
        path = _resolve_local_path(spec.dataset_id)
        if not path.exists():
            raise FileNotFoundError(
                f"JEPX CSV not found at {path}. Download from "
                f"https://www.jepx.org/electricpower/market-data/spot/ "
                f"and place at $GRIDFLOW_DATASET_ROOT/{spec.dataset_id}/data.csv"
            )

        timestamps: list[str] = []
        prices: list[float] = []
        with path.open(encoding="utf-8") as fh:
            reader = csv.DictReader(fh)
            for row in reader:
                timestamps.append(row["ts_iso"])
                prices.append(float(row.get("spot_price_jpy_per_kwh", "0")))

        if spec.time_range:
            start_iso, end_iso = spec.time_range
            keep = [i for i, t in enumerate(timestamps) if start_iso <= t < end_iso]
            timestamps = [timestamps[i] for i in keep]
            prices = [prices[i] for i in keep]

        all_channels = (("spot_price_jpy_per_kwh", "JPY/kWh", tuple(prices)),)
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
            JEPX_SPOT_PRICE_METADATA,
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
