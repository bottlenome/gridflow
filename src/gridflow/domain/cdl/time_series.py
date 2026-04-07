"""TimeSeries CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime

from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import Params, params_to_dict


@dataclass(frozen=True)
class TimeSeries:
    """Time series data.

    Attributes:
        series_id: Unique series identifier.
        name: Series name.
        timestamps: Tuple of timestamps.
        values: Tuple of values.
        unit: Unit string (e.g. "kW", "V", "A").
        resolution_s: Data resolution in seconds.
        metadata: Series-level metadata as a frozen tuple-of-tuples
            (see ``gridflow.domain.util.params``).
    """

    series_id: str
    name: str
    timestamps: tuple[datetime, ...]
    values: tuple[float, ...]
    unit: str
    resolution_s: float
    metadata: Params = ()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "series_id": self.series_id,
            "name": self.name,
            "timestamps": [ts.isoformat() for ts in self.timestamps],
            "values": list(self.values),
            "unit": self.unit,
            "resolution_s": self.resolution_s,
            "metadata": params_to_dict(self.metadata),
        }

    def validate(self) -> None:
        """Validate time series attributes."""
        if not self.series_id:
            raise CDLValidationError("TimeSeries.series_id must not be empty")
        if len(self.timestamps) != len(self.values):
            raise CDLValidationError(
                f"TimeSeries timestamps ({len(self.timestamps)}) and values ({len(self.values)}) must have same length"
            )
        if self.resolution_s <= 0:
            raise CDLValidationError(f"TimeSeries.resolution_s must be positive, got {self.resolution_s}")
