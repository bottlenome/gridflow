"""Synthetic VPP-churn loader for try11 baseline experiments.

Spec: ``docs/dataset_catalog.md``.

This loader wraps the existing ``test/mvp_try11/tools/trace_synthesizer``
deterministic synth into the dataset framework. It exists primarily so
the rest of the dataset pipeline (registry, ScenarioPack integration)
can be exercised end-to-end before any real-world loader lands.

Channels:
  * ``aggregate_active_count`` — number of active DERs at each step
  * ``aggregate_active_kw``   — total active capacity (kW) at each step
"""

from __future__ import annotations

import hashlib
from datetime import UTC, datetime, timedelta

from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetLoader,
    DatasetMetadata,
    DatasetSpec,
    DatasetTimeSeries,
)


SYNTHETIC_VPP_METADATA: DatasetMetadata = DatasetMetadata(
    dataset_id="gridflow/synthetic_vpp_churn/v1",
    title="gridflow synthetic VPP churn (v1)",
    description=(
        "Hand-crafted churn trace with C1-C8 variants used by try11 "
        "baseline experiments. Single trigger (C1), extreme burst (C2), "
        "simultaneous (C3), out-of-basis (C4), frequency shift (C5), "
        "label noise (C6), correlation reversal (C7), scarce orthogonal (C8). "
        "Deterministic given (variant, seed, pool size)."
    ),
    source="gridflow research collective",
    license=DatasetLicense.CC0_1_0,
    retrieval_url="https://github.com/bottlenome/gridflow",
    doi="",
    retrieval_method="synthetic",
    sha256="",  # filled per-call (= synthetic trace differs by seed/pool)
    time_resolution_seconds=300,  # 5 min
    period_start_iso="2026-01-01T00:00:00Z",
    period_end_iso="2026-01-31T00:00:00Z",
    units=(
        ("aggregate_active_count", "count"),
        ("aggregate_active_kw", "kW"),
    ),
    contributors=("gridflow team",),
    added_at_iso="2026-04-29T00:00:00Z",
)


class SyntheticLoader:
    """Loader for ``gridflow/synthetic_vpp_churn/v1``."""

    name: str = "synthetic"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("gridflow/synthetic_vpp_churn/")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported dataset: {spec.dataset_id}")

        # Defer the heavy import to the call site so that this loader
        # has no side effects at module-import time. The synth modules
        # live under ``test/mvp_try11/tools/``; ensure that path is on
        # sys.path before importing.
        import os
        import sys
        from pathlib import Path
        repo_root = Path(__file__).resolve().parents[4]
        try11_path = repo_root / "test" / "mvp_try11"
        if str(try11_path) not in sys.path:
            sys.path.insert(0, str(try11_path))
        from tools.der_pool import make_default_pool
        from tools.trace_synthesizer import synth_c1_single_trigger

        params = dict(spec.params)
        seed = int(params.get("seed", 0))
        pool_size = int(params.get("pool_size", 200))

        # Map pool_size to make_default_pool kwargs preserving 40/15/15/15/15 ratios
        n_ev = int(pool_size * 0.40)
        n_other = int(pool_size * 0.15)
        pool = make_default_pool(
            n_residential_ev=n_ev,
            n_commercial_fleet=n_other,
            n_industrial_battery=n_other,
            n_heat_pump=n_other,
            n_utility_battery=n_other,
            seed=seed,
        )
        trace = synth_c1_single_trigger(pool, seed=seed, sla_kw=1500.0)

        # Build time-axis as ISO timestamps
        start = datetime.fromisoformat("2026-01-01T00:00:00+00:00")
        timestamps_iso = tuple(
            (start + timedelta(minutes=t * trace.timestep_min)).isoformat()
            for t in range(trace.n_steps)
        )

        # Per-step aggregate active count and capacity
        active_count_series: list[float] = []
        active_kw_series: list[float] = []
        cap_by_idx = tuple(d.capacity_kw for d in pool)
        for row in trace.der_active_status:
            active_count_series.append(float(sum(row)))
            active_kw_series.append(
                float(sum(cap_by_idx[i] for i, a in enumerate(row) if a))
            )

        # Apply time_range filter if any
        if spec.time_range:
            start_iso, end_iso = spec.time_range
            keep = [
                i for i, ts in enumerate(timestamps_iso)
                if start_iso <= ts < end_iso
            ]
            timestamps_iso = tuple(timestamps_iso[i] for i in keep)
            active_count_series = [active_count_series[i] for i in keep]
            active_kw_series = [active_kw_series[i] for i in keep]

        # Apply channel_filter
        all_channels = (
            ("aggregate_active_count", "count", tuple(active_count_series)),
            ("aggregate_active_kw", "kW", tuple(active_kw_series)),
        )
        if spec.channel_filter:
            wanted = set(spec.channel_filter)
            channels = tuple(c for c in all_channels if c[0] in wanted)
        else:
            channels = all_channels

        # Compute payload sha256 over the value tuples for reproducibility check
        h = hashlib.sha256()
        for _, _, values in channels:
            for v in values:
                h.update(str(v).encode())
        payload_hash = h.hexdigest()

        # Replace metadata.sha256 with the actual one for this slice
        from dataclasses import replace
        sliced_metadata = replace(SYNTHETIC_VPP_METADATA, sha256=payload_hash)

        return DatasetTimeSeries(
            spec=spec,
            metadata=sliced_metadata,
            timestamps_iso=timestamps_iso,
            channels=channels,
        )
