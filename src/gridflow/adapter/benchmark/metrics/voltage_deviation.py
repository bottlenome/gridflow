"""Voltage deviation metric: RMS |V - 1.0| pu across all node voltages.

Formula (DD-ALG-002):
    dev = sqrt( mean( (V_i - 1.0)^2 ) )  over every bus / step

Returns 0.0 for empty inputs — callers treat the missing-data case as
"no deviation observed" rather than propagating a NaN.
"""

from __future__ import annotations

import math

from gridflow.domain.error import MetricCalculationError
from gridflow.usecase.result import ExperimentResult


class VoltageDeviationMetric:
    name = "voltage_deviation"
    unit = "pu"

    def calculate(self, result: ExperimentResult) -> float:
        samples: list[float] = []
        for node_result in result.node_results:
            samples.extend(node_result.voltages)
        for step in result.steps:
            if step.node_result is not None:
                samples.extend(step.node_result.voltages)

        if not samples:
            return 0.0

        try:
            mean_sq = sum((v - 1.0) ** 2 for v in samples) / len(samples)
            return math.sqrt(mean_sq)
        except (TypeError, ValueError) as exc:
            raise MetricCalculationError(
                "voltage_deviation calculation failed",
                context={"sample_count": len(samples)},
                cause=exc,
            ) from exc
