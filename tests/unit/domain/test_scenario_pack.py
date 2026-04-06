"""Tests for ScenarioPack and PackMetadata domain models."""

from datetime import UTC, datetime
from pathlib import Path

from gridflow.domain.scenario import PackMetadata, PackStatus, ScenarioPack


class TestPackMetadata:
    def test_create_metadata(self) -> None:
        meta = PackMetadata(
            name="ieee13",
            version="1.0.0",
            description="IEEE 13-node test feeder",
            author="test",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            connector="opendss",
        )
        assert meta.name == "ieee13"
        assert meta.seed is None
        assert meta.parameters == {}

    def test_metadata_with_seed(self) -> None:
        meta = PackMetadata(
            name="ieee13",
            version="1.0.0",
            description="test",
            author="test",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            connector="opendss",
            seed=42,
            parameters={"solver": "direct"},
        )
        assert meta.seed == 42
        assert meta.parameters["solver"] == "direct"


class TestScenarioPack:
    def test_create_pack(self) -> None:
        meta = PackMetadata(
            name="ieee13",
            version="1.0.0",
            description="test",
            author="test",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            connector="opendss",
        )
        pack = ScenarioPack(
            pack_id="pack-001",
            name="ieee13",
            version="1.0.0",
            metadata=meta,
            network_dir=Path("/data/network"),
            timeseries_dir=Path("/data/timeseries"),
            config_dir=Path("/data/config"),
        )
        assert pack.pack_id == "pack-001"
        assert pack.status == PackStatus.DRAFT

    def test_pack_status_transition(self) -> None:
        meta = PackMetadata(
            name="ieee13",
            version="1.0.0",
            description="test",
            author="test",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            connector="opendss",
        )
        pack = ScenarioPack(
            pack_id="pack-001",
            name="ieee13",
            version="1.0.0",
            metadata=meta,
            network_dir=Path("/data/network"),
            timeseries_dir=Path("/data/timeseries"),
            config_dir=Path("/data/config"),
            status=PackStatus.VALIDATED,
        )
        assert pack.status == PackStatus.VALIDATED
