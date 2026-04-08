"""Structural tests for the ScenarioRegistry Protocol."""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from gridflow.domain.scenario import (
    PackMetadata,
    PackStatus,
    ScenarioPack,
    ScenarioRegistry,
)


class _InMemoryRegistry:
    """Minimal in-memory implementation used to verify Protocol compliance."""

    def __init__(self) -> None:
        self._store: dict[str, ScenarioPack] = {}

    def register(self, pack: ScenarioPack) -> ScenarioPack:
        pack.validate()
        registered = pack.with_status(PackStatus.REGISTERED)
        self._store[pack.pack_id] = registered
        return registered

    def get(self, pack_id: str) -> ScenarioPack:
        return self._store[pack_id]

    def list_all(self) -> tuple[ScenarioPack, ...]:
        return tuple(self._store[k] for k in sorted(self._store))

    def update_status(self, pack_id: str, new_status: PackStatus) -> ScenarioPack:
        updated = self._store[pack_id].with_status(new_status)
        self._store[pack_id] = updated
        return updated

    def delete(self, pack_id: str) -> None:
        del self._store[pack_id]


def _make_pack(pack_id: str = "p1") -> ScenarioPack:
    meta = PackMetadata(
        name="n",
        version="1.0.0",
        description="d",
        author="a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
    )
    return ScenarioPack(
        pack_id=pack_id,
        name="n",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/n"),
        timeseries_dir=Path("/t"),
        config_dir=Path("/c"),
    )


def test_in_memory_registry_satisfies_protocol() -> None:
    registry: ScenarioRegistry = _InMemoryRegistry()
    assert isinstance(registry, ScenarioRegistry)
    pack = registry.register(_make_pack())
    assert pack.status == PackStatus.REGISTERED
    assert registry.get("p1").pack_id == "p1"
    assert registry.list_all() == (pack,)
    updated = registry.update_status("p1", PackStatus.RUNNING)
    assert updated.status == PackStatus.RUNNING
