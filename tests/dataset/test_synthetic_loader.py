"""Tests for the synthetic dataset loader.

These mirror the contributor checklist in ``docs/dataset_contribution.md`` §2 Step 4.
"""

from __future__ import annotations

import sys
from dataclasses import is_dataclass

import pytest

from gridflow.adapter.dataset import SYNTHETIC_VPP_METADATA, SyntheticLoader
from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetMetadata,
    DatasetSpec,
    DatasetTimeSeries,
)
from gridflow.domain.util.params import as_params
from gridflow.infra.dataset import FilesystemDatasetRegistry, InMemoryDatasetRegistry


# Add repo root so the ``test/mvp_try11.tools.*`` import inside the loader works
import os as _os
sys.path.insert(0, _os.path.dirname(_os.path.dirname(_os.path.dirname(__file__))))


def test_supports_correct_id():
    loader = SyntheticLoader()
    assert loader.supports("gridflow/synthetic_vpp_churn/v1") is True


def test_supports_rejects_other_id():
    loader = SyntheticLoader()
    assert loader.supports("pecanstreet/residential_ev/2024-01") is False


def test_metadata_immutable():
    # Frozen dataclass enforces immutability
    assert is_dataclass(SYNTHETIC_VPP_METADATA)
    with pytest.raises((AttributeError, Exception)):
        SYNTHETIC_VPP_METADATA.dataset_id = "mutated"  # type: ignore[misc]


def test_metadata_required_fields():
    m = SYNTHETIC_VPP_METADATA
    assert m.dataset_id == "gridflow/synthetic_vpp_churn/v1"
    assert m.license == DatasetLicense.CC0_1_0
    assert m.time_resolution_seconds == 300
    assert len(m.units) >= 1


def test_load_returns_correct_channels():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 0, "pool_size": 200}),
    )
    ts = loader.load(spec)
    assert isinstance(ts, DatasetTimeSeries)
    assert ts.n_steps > 0
    assert ts.metadata.dataset_id == spec.dataset_id
    channel_names = {c[0] for c in ts.channels}
    assert "aggregate_active_count" in channel_names
    assert "aggregate_active_kw" in channel_names


def test_load_deterministic():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 7, "pool_size": 50}),
    )
    ts1 = loader.load(spec)
    ts2 = loader.load(spec)
    assert ts1.timestamps_iso == ts2.timestamps_iso
    assert ts1.channels == ts2.channels
    assert ts1.metadata.sha256 == ts2.metadata.sha256


def test_channel_filter():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 0, "pool_size": 50}),
        channel_filter=("aggregate_active_kw",),
    )
    ts = loader.load(spec)
    assert len(ts.channels) == 1
    assert ts.channels[0][0] == "aggregate_active_kw"


def test_in_memory_registry_basic():
    reg = InMemoryDatasetRegistry((SYNTHETIC_VPP_METADATA,))
    assert "gridflow/synthetic_vpp_churn/v1" in reg.list_ids()
    m = reg.get_metadata("gridflow/synthetic_vpp_churn/v1")
    assert m.title == SYNTHETIC_VPP_METADATA.title
    with pytest.raises(KeyError):
        reg.get_metadata("nope/none/v0")


def test_registry_filter_by_license():
    reg = InMemoryDatasetRegistry((SYNTHETIC_VPP_METADATA,))
    redist = reg.filter_by_license(redistributable=True)
    assert len(redist) == 1
    not_redist = reg.filter_by_license(redistributable=False)
    assert len(not_redist) == 0


def test_filesystem_registry_round_trip(tmp_path):
    reg = FilesystemDatasetRegistry(tmp_path)
    reg.write(SYNTHETIC_VPP_METADATA)
    # Reload from disk
    reg2 = FilesystemDatasetRegistry(tmp_path)
    assert "gridflow/synthetic_vpp_churn/v1" in reg2.list_ids()
    m = reg2.get_metadata("gridflow/synthetic_vpp_churn/v1")
    assert m.dataset_id == SYNTHETIC_VPP_METADATA.dataset_id
    assert m.license == SYNTHETIC_VPP_METADATA.license
