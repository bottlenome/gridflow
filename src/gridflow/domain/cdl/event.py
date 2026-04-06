"""Event CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import datetime

from gridflow.domain.error import CDLValidationError

VALID_TARGET_TYPES = frozenset({"node", "edge", "asset"})


@dataclass(frozen=True)
class Event:
    """Simulation event.

    Attributes:
        event_id: Unique event identifier.
        event_type: Event type (e.g. "fault", "switch", "setpoint", "load_change", "generation_change").
        timestamp: Event occurrence time.
        target_id: Target element identifier (Node.node_id, Edge.edge_id, or Asset.asset_id).
        target_type: Target element type ("node" | "edge" | "asset").
        parameters: Event-specific parameters.
    """

    event_id: str
    event_type: str
    timestamp: datetime
    target_id: str
    target_type: str
    parameters: dict[str, object] = field(default_factory=dict)

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "event_id": self.event_id,
            "event_type": self.event_type,
            "timestamp": self.timestamp.isoformat(),
            "target_id": self.target_id,
            "target_type": self.target_type,
            "parameters": dict(self.parameters),
        }

    def validate(self) -> None:
        """Validate event attributes."""
        if not self.event_id:
            raise CDLValidationError("Event.event_id must not be empty")
        if self.target_type not in VALID_TARGET_TYPES:
            raise CDLValidationError(f"Event.target_type must be one of {VALID_TARGET_TYPES}, got '{self.target_type}'")
