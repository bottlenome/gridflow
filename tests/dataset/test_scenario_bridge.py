"""Tests for the dataset → scenario-pack bridge."""

from __future__ import annotations

from gridflow.adapter.dataset import SyntheticLoader
from gridflow.adapter.dataset.scenario_bridge import (
    dataset_to_active_count,
    dataset_to_active_fraction,
    pack_parameters_with_dataset,
)
from gridflow.domain.dataset import DatasetSpec
from gridflow.domain.util.params import as_params


def test_pack_parameters_includes_provenance():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 0, "pool_size": 50}),
    )
    ts = loader.load(spec)
    params = pack_parameters_with_dataset(spec, ts.metadata, base_params={"feeder": "cigre_lv"})
    keys = {k for k, _ in params}
    assert "dataset_id" in keys
    assert "dataset_sha256" in keys
    assert "dataset_license" in keys
    assert "dataset_resolution_seconds" in keys
    assert "feeder" in keys


def test_active_fraction_in_unit_range():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 0, "pool_size": 200}),
    )
    ts = loader.load(spec)
    fraction = dataset_to_active_fraction(ts, pool_size=200)
    assert all(0.0 <= f <= 1.0 for f in fraction)


def test_active_count_int():
    loader = SyntheticLoader()
    spec = DatasetSpec(
        dataset_id="gridflow/synthetic_vpp_churn/v1",
        params=as_params({"seed": 0, "pool_size": 200}),
    )
    ts = loader.load(spec)
    counts = dataset_to_active_count(ts)
    assert all(isinstance(c, int) for c in counts)
    assert all(c >= 0 for c in counts)
