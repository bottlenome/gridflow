"""Metric CDL domain model."""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import Params, params_to_dict


@dataclass(frozen=True)
class Metric:
    """Evaluation metric.

    Attributes:
        name: Metric name (unique within experiment, serves as PK).
        value: Metric value.
        unit: Unit string.
        step: Corresponding step number. None for aggregate metrics.
        threshold: Threshold value for warnings. None if not applicable.
        metadata: Metric-level metadata as a frozen tuple-of-tuples
            (see ``gridflow.domain.util.params``).
    """

    name: str
    value: float
    unit: str
    step: int | None = None
    threshold: float | None = None
    metadata: Params = ()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "value": self.value,
            "unit": self.unit,
            "step": self.step,
            "threshold": self.threshold,
            "metadata": params_to_dict(self.metadata),
        }

    def validate(self) -> None:
        """Validate metric attributes."""
        if not self.name:
            raise CDLValidationError("Metric.name must not be empty")
