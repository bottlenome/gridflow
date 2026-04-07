"""Domain layer interfaces for Scenario Pack persistence."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gridflow.domain.scenario.scenario_pack import ScenarioPack


@runtime_checkable
class ScenarioRepositoryInterface(Protocol):
    """Protocol for Scenario Pack persistence and retrieval."""

    def save(self, pack: ScenarioPack) -> None: ...
    def find_by_id(self, pack_id: str) -> ScenarioPack | None: ...
    def list_all(self) -> list[ScenarioPack]: ...
    def delete(self, pack_id: str) -> None: ...
