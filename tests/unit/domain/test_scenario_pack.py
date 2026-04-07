"""Tests for ScenarioPack and PackMetadata domain models."""

from dataclasses import FrozenInstanceError
from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.error import PackValidationError
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack
from gridflow.domain.util.params import as_params, get_param


def _make_meta(**overrides: object) -> PackMetadata:
    defaults: dict[str, object] = dict(
        name="ieee13",
        version="1.0.0",
        description="test",
        author="test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
    )
    defaults.update(overrides)
    return PackMetadata(**defaults)  # type: ignore[arg-type]


def _make_pack(meta: PackMetadata | None = None, **overrides: object) -> ScenarioPack:
    meta = meta or _make_meta()
    defaults: dict[str, object] = dict(
        pack_id="pack-001",
        name="ieee13",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/data/network"),
        timeseries_dir=Path("/data/timeseries"),
        config_dir=Path("/data/config"),
    )
    defaults.update(overrides)
    return ScenarioPack(**defaults)  # type: ignore[arg-type]


class TestPackMetadata:
    def test_create_metadata(self) -> None:
        meta = _make_meta()
        assert meta.name == "ieee13"
        assert meta.seed is None
        assert meta.parameters == ()

    def test_metadata_with_seed_and_params(self) -> None:
        meta = _make_meta(seed=42, parameters=as_params({"solver": "direct"}))
        assert meta.seed == 42
        assert get_param(meta.parameters, "solver") == "direct"

    def test_metadata_is_hashable(self) -> None:
        assert hash(_make_meta()) == hash(_make_meta())

    def test_metadata_to_dict(self) -> None:
        meta = _make_meta(seed=7)
        d = meta.to_dict()
        assert d["seed"] == 7
        assert d["connector"] == "opendss"
        assert d["parameters"] == {}


class TestScenarioPack:
    def test_create_pack(self) -> None:
        pack = _make_pack()
        assert pack.pack_id == "pack-001"
        assert pack.status == PackStatus.DRAFT

    def test_pack_status_is_immutable(self) -> None:
        pack = _make_pack()
        with pytest.raises(FrozenInstanceError):
            pack.status = PackStatus.VALIDATED  # type: ignore[misc]

    def test_pack_with_status_returns_new_instance(self) -> None:
        pack = _make_pack()
        updated = pack.with_status(PackStatus.REGISTERED)
        assert pack.status == PackStatus.DRAFT
        assert updated.status == PackStatus.REGISTERED
        assert pack is not updated

    def test_pack_validate_ok(self) -> None:
        _make_pack().validate()  # no exception

    def test_pack_validate_empty_pack_id(self) -> None:
        pack = _make_pack(pack_id="")
        with pytest.raises(PackValidationError, match="pack_id"):
            pack.validate()

    def test_pack_validate_name_mismatch(self) -> None:
        pack = _make_pack(name="mismatch")
        with pytest.raises(PackValidationError, match="name"):
            pack.validate()

    def test_pack_validate_version_mismatch(self) -> None:
        meta = _make_meta(version="2.0.0")
        pack = _make_pack(meta=meta)
        with pytest.raises(PackValidationError, match="version"):
            pack.validate()

    def test_pack_to_dict_roundtrip(self) -> None:
        pack = _make_pack().with_status(PackStatus.REGISTERED)
        d = pack.to_dict()
        assert d["status"] == "registered"
        assert d["pack_id"] == "pack-001"
