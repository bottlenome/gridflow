"""ExperimentMetadata CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from gridflow.domain.error import CDLValidationError


@dataclass(frozen=True)
class ExperimentMetadata:
    """Experiment metadata.

    Attributes:
        experiment_id: Unique experiment identifier.
        created_at: Experiment creation timestamp.
        scenario_pack_id: ID of the scenario pack used.
        connector: Connector name used.
        seed: Random seed. None if not specified.
        parameters: Experiment parameters.
    """

    experiment_id: str
    created_at: datetime
    scenario_pack_id: str
    connector: str
    seed: int | None = None
    parameters: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "experiment_id": self.experiment_id,
            "created_at": self.created_at.isoformat(),
            "scenario_pack_id": self.scenario_pack_id,
            "connector": self.connector,
            "seed": self.seed,
            "parameters": dict(self.parameters),
        }

    def validate(self) -> None:
        """Validate experiment metadata attributes."""
        if not self.experiment_id:
            raise CDLValidationError("ExperimentMetadata.experiment_id must not be empty")
        if not self.scenario_pack_id:
            raise CDLValidationError("ExperimentMetadata.scenario_pack_id must not be empty")
        if not self.connector:
            raise CDLValidationError("ExperimentMetadata.connector must not be empty")
