"""Tests for FileScenarioRegistry and the YAML pack loader."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.error import PackNotFoundError, PackValidationError
from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack
from gridflow.infra.scenario import FileScenarioRegistry, load_pack_from_yaml


def _sample_pack(pack_id: str = "ieee13@1.0.0") -> ScenarioPack:
    meta = PackMetadata(
        name="ieee13",
        version="1.0.0",
        description="IEEE 13 feeder",
        author="tester",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
        seed=42,
    )
    return ScenarioPack(
        pack_id=pack_id,
        name="ieee13",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/net"),
        timeseries_dir=Path("/ts"),
        config_dir=Path("/cfg"),
    )


class TestFileScenarioRegistry:
    def test_register_and_get_roundtrip(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        registered = reg.register(_sample_pack())
        assert registered.status == PackStatus.REGISTERED

        fetched = reg.get("ieee13@1.0.0")
        assert fetched.pack_id == "ieee13@1.0.0"
        assert fetched.status == PackStatus.REGISTERED
        assert fetched.metadata.seed == 42

    def test_get_missing_raises(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        with pytest.raises(PackNotFoundError):
            reg.get("nope")

    def test_list_all_sorted(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_sample_pack("z@1"))
        reg.register(_sample_pack("a@1"))
        packs = reg.list_all()
        assert [p.pack_id for p in packs] == ["a@1", "z@1"]

    def test_update_status(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_sample_pack())
        updated = reg.update_status("ieee13@1.0.0", PackStatus.RUNNING)
        assert updated.status == PackStatus.RUNNING
        assert reg.get("ieee13@1.0.0").status == PackStatus.RUNNING

    def test_delete(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        reg.register(_sample_pack())
        reg.delete("ieee13@1.0.0")
        with pytest.raises(PackNotFoundError):
            reg.get("ieee13@1.0.0")

    def test_reject_bad_pack_id(self, tmp_path: Path) -> None:
        reg = FileScenarioRegistry(tmp_path / "packs")
        with pytest.raises(PackValidationError):
            bad = _sample_pack("has spaces")
            reg.register(bad)


class TestLoadPackFromYaml:
    def test_loads_minimal_yaml(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "pack.yaml"
        yaml_path.write_text(
            """
pack:
  name: ieee13
  version: "1.0.0"
  description: IEEE 13 node feeder
  author: tester
  connector: opendss
  seed: 42
parameters:
  voltage_base_kv: 4.16
  max_iterations: 100
""",
            encoding="utf-8",
        )
        pack = load_pack_from_yaml(yaml_path)
        assert pack.name == "ieee13"
        assert pack.version == "1.0.0"
        assert pack.metadata.seed == 42
        assert pack.metadata.connector == "opendss"
        # parameters were normalised to tuple-of-tuples
        assert ("voltage_base_kv", 4.16) in pack.metadata.parameters

    def test_missing_required_field_raises(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "pack.yaml"
        yaml_path.write_text(
            """
pack:
  name: ieee13
  version: "1.0.0"
  description: x
  author: y
""",
            encoding="utf-8",
        )
        with pytest.raises(PackValidationError, match="connector"):
            load_pack_from_yaml(yaml_path)
