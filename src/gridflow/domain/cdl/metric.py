"""Metric CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import CDLValidationError


@dataclass(frozen=True)
class Metric:
    """Evaluation metric.

    Attributes:
        name: Metric name (unique within experiment, serves as PK).
        value: Metric value.
        unit: Unit string.
        step: Corresponding step number. None for aggregate metrics.
        threshold: Threshold value for warnings. None if not applicable.
    """

    name: str
    value: float
    unit: str
    step: int | None = None
    threshold: float | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "step": self.step,
            "threshold": self.threshold,
        }

    def validate(self) -> None:
        """Validate metric attributes."""
        if not self.name:
            raise CDLValidationError("Metric.name must not be empty")
