"""Asset CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import Params, params_to_dict


@dataclass(frozen=True)
class Asset:
    """Power equipment asset.

    Attributes:
        asset_id: Unique asset identifier.
        name: Asset name.
        asset_type: Asset type (e.g. "pv", "battery", "load").
        node_id: Connected node ID (references Node.node_id).
        rated_power_kw: Rated power in kW.
        parameters: Asset-specific additional parameters as a frozen
            tuple-of-tuples (see ``gridflow.domain.util.params``).
    """

    asset_id: str
    name: str
    asset_type: str
    node_id: str
    rated_power_kw: float
    parameters: Params = ()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "asset_id": self.asset_id,
            "name": self.name,
            "asset_type": self.asset_type,
            "node_id": self.node_id,
            "rated_power_kw": self.rated_power_kw,
            "parameters": params_to_dict(self.parameters),
        }

    def validate(self) -> None:
        """Validate asset attributes."""
        if not self.asset_id:
            raise CDLValidationError("Asset.asset_id must not be empty")
        if not self.node_id:
            raise CDLValidationError("Asset.node_id must not be empty")
        if self.rated_power_kw < 0:
            raise CDLValidationError(f"Asset.rated_power_kw must be non-negative, got {self.rated_power_kw}")
