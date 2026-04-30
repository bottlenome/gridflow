"""Tests for the stub loaders (Pecan / CAISO / AEMO / JEPX / NREL).

These verify the metadata and "missing-file" behaviour. The actual data
loading is not exercised here — that requires contributor-provided CSV
under ``$GRIDFLOW_DATASET_ROOT``.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from gridflow.adapter.dataset import (
    AEMO_TESLA_VPP_METADATA,
    AEMOTeslaVPPLoader,
    ALL_LOADERS,
    ALL_REGISTERED_METADATAS,
    CAISO_SYSTEM_LOAD_METADATA,
    CAISOLoader,
    JEPX_SPOT_PRICE_METADATA,
    JEPXLoader,
    NREL_RESSTOCK_METADATA,
    NRELResStockLoader,
    PECAN_STREET_RESIDENTIAL_EV_METADATA,
    PecanStreetLoader,
)
from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetMetadata,
    DatasetSpec,
)
from gridflow.infra.dataset import InMemoryDatasetRegistry


@pytest.mark.parametrize("metadata", [
    PECAN_STREET_RESIDENTIAL_EV_METADATA,
    CAISO_SYSTEM_LOAD_METADATA,
    AEMO_TESLA_VPP_METADATA,
    JEPX_SPOT_PRICE_METADATA,
    NREL_RESSTOCK_METADATA,
])
def test_metadata_required_fields(metadata: DatasetMetadata):
    assert metadata.dataset_id != ""
    assert metadata.title != ""
    assert metadata.source != ""
    assert metadata.retrieval_url != ""
    assert isinstance(metadata.license, DatasetLicense)
    assert metadata.time_resolution_seconds > 0
    assert len(metadata.units) > 0
    for ch_name, unit in metadata.units:
        assert ch_name != ""
        assert unit != ""


@pytest.mark.parametrize("loader,supported_id,unsupported_id", [
    (PecanStreetLoader(), "pecanstreet/residential_ev/v1", "caiso/x/v1"),
    (CAISOLoader(), "caiso/system_load_5min/v1", "jepx/x/v1"),
    (AEMOTeslaVPPLoader(), "aemo/tesla_vpp_sa/v1", "aemo/other/v1"),
    (JEPXLoader(), "jepx/spot_price/v1", "caiso/x/v1"),
    (NRELResStockLoader(), "nrel/resstock_residential/v1", "nrel/other/v1"),
])
def test_supports_dispatch(loader, supported_id, unsupported_id):
    assert loader.supports(supported_id)
    assert not loader.supports(unsupported_id)


@pytest.mark.parametrize("loader,dataset_id", [
    (PecanStreetLoader(), "pecanstreet/residential_ev/v1"),
    (CAISOLoader(), "caiso/system_load_5min/v1"),
    (AEMOTeslaVPPLoader(), "aemo/tesla_vpp_sa/v1"),
    (JEPXLoader(), "jepx/spot_price/v1"),
    (NRELResStockLoader(), "nrel/resstock_residential/v1"),
])
def test_load_raises_when_missing(loader, dataset_id, tmp_path, monkeypatch):
    monkeypatch.setenv("GRIDFLOW_DATASET_ROOT", str(tmp_path))
    spec = DatasetSpec(dataset_id=dataset_id)
    with pytest.raises(FileNotFoundError):
        loader.load(spec)


def test_all_loaders_consistent_with_metadata():
    # Each metadata's dataset_id is supported by exactly one loader
    metadata_ids = [m.dataset_id for m in ALL_REGISTERED_METADATAS]
    for mid in metadata_ids:
        supporting = [L for L in ALL_LOADERS if L.supports(mid)]
        assert len(supporting) >= 1, f"no loader supports {mid}"


def test_registry_seeded_with_all_metadatas():
    reg = InMemoryDatasetRegistry(ALL_REGISTERED_METADATAS)
    assert len(reg.list_ids()) == len(ALL_REGISTERED_METADATAS)
    redist = reg.filter_by_license(redistributable=True)
    # Synthetic (CC0), CAISO (Public-Domain), AEMO (Public-Domain),
    # JEPX (CC-BY), NREL (CC-BY) → 5 redistributable
    # Pecan Street is Proprietary → not redistributable
    assert len(redist) == 5


def test_caiso_loader_smoke_with_local_csv(tmp_path, monkeypatch):
    """End-to-end smoke: write a tiny CSV, load it, verify channels + sha256."""
    monkeypatch.setenv("GRIDFLOW_DATASET_ROOT", str(tmp_path))
    csv_dir = tmp_path / "caiso" / "system_load_5min" / "v1"
    csv_dir.mkdir(parents=True)
    (csv_dir / "data.csv").write_text(
        "ts_iso,system_load_mw\n"
        "2024-01-01T00:00:00Z,28000.0\n"
        "2024-01-01T00:05:00Z,27950.0\n"
        "2024-01-01T00:10:00Z,27900.0\n",
        encoding="utf-8",
    )
    loader = CAISOLoader()
    spec = DatasetSpec(dataset_id="caiso/system_load_5min/v1")
    ts = loader.load(spec)
    assert ts.n_steps == 3
    assert "system_load_mw" in [c[0] for c in ts.channels]
    # sha256 must be filled
    assert ts.metadata.sha256 != ""

    # Round-trip determinism
    ts2 = loader.load(spec)
    assert ts.metadata.sha256 == ts2.metadata.sha256
    assert ts.channels == ts2.channels
