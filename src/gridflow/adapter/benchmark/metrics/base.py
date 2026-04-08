"""Metric calculator Protocol.

Every concrete metric must:
    1. Expose a unique ``name`` used as the lookup key.
    2. Implement :meth:`calculate`, returning a plain ``float`` (unit is
       the caller's responsibility).

``MetricCalculator`` is intentionally ``runtime_checkable`` so adapters
without a shared base class still pass ``isinstance`` checks.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from gridflow.usecase.result import ExperimentResult


@runtime_checkable
class MetricCalculator(Protocol):
    """Pure computation over an :class:`ExperimentResult`."""

    name: str
    unit: str

    def calculate(self, result: ExperimentResult) -> float: ...
