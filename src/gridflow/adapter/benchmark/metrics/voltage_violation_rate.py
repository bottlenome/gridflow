"""Voltage-violation-rate metric: fraction of bus voltages outside an envelope.

Issue #22. A voltage *deviation* (RMS) does not tell you how often a bus
actually breached its operating band, which is the quantity a distribution
study usually cares about. This metric reports the fraction of sampled bus
voltages that fall outside ``[v_min, v_max]``.

The envelope is an explicit parameter, defaulting to the ANSI C84.1 Range A
service band (0.95-1.05 pu). Making the band explicit is deliberate: comparing
a violation rate measured under a relaxed band against a strict band was one of
the misjudgments (try11's "5x reduction") this project is closing, so the band
travels with the number. Issue #24 makes the band mandatory in evaluation
contexts; here a documented ANSI default keeps the metric usable out of the box.
"""

from __future__ import annotations

from gridflow.domain.error import MetricCalculationError
from gridflow.usecase.result import ExperimentResult


class VoltageViolationRateMetric:
    name = "voltage_violation_rate"
    unit = "ratio"

    def __init__(self, *, v_min: float = 0.95, v_max: float = 1.05) -> None:
        if v_min > v_max:
            raise MetricCalculationError(
                f"voltage_violation_rate: v_min ({v_min}) must be <= v_max ({v_max})",
            )
        self.v_min = v_min
        self.v_max = v_max

    def calculate(self, result: ExperimentResult) -> float:
        samples: list[float] = []
        for node_result in result.node_results:
            samples.extend(node_result.voltages)
        for step in result.steps:
            if step.node_result is not None:
                samples.extend(step.node_result.voltages)

        if not samples:
            # No voltage data observed → no violations to report (consistent
            # with VoltageDeviationMetric's empty-input handling; never a NaN).
            return 0.0

        violations = sum(1 for v in samples if v < self.v_min or v > self.v_max)
        return violations / len(samples)
