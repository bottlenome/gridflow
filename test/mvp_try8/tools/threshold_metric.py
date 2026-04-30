"""Threshold-parameterised metric used by the try8 validation runner.

Plugin spec: ``test.mvp_try8.tools.threshold_metric:ThresholdedFraction``.
Two instances with different ``voltage_low`` coexist in one
EvaluationPlan to exercise the §5.1.1 Option B "same plugin, two
kwargs" use case, and the same class also feeds the SensitivityAnalyzer
parameter-grid path.
"""

from __future__ import annotations

from gridflow.usecase.result import ExperimentResult


class ThresholdedFraction:
    """Fraction of recorded voltages strictly below ``voltage_low``."""

    name = "thresholded_fraction"
    unit = "ratio"

    def __init__(self, *, voltage_low: float = 0.95) -> None:
        self.voltage_low = voltage_low

    def calculate(self, result: ExperimentResult) -> float:
        voltages = tuple(v for nr in result.node_results for v in nr.voltages)
        if not voltages:
            return 0.0
        return sum(1 for v in voltages if v < self.voltage_low) / len(voltages)
