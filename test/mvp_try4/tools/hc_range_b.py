"""hosting_capacity_mw with ANSI C84.1 Range B (0.90-1.06 pu)."""
from __future__ import annotations
from gridflow.usecase.result import ExperimentResult


class HostingCapacityMetric:
    name = "hosting_capacity_mw"
    unit = "MW"

    def __init__(self, **_kw: object) -> None:
        self._low = 0.90
        self._high = 1.06

    def calculate(self, result: ExperimentResult) -> float:
        pv_kw = 0.0
        for key, value in result.metadata.parameters:
            if key == "pv_kw":
                try:
                    pv_kw = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pv_kw = 0.0
                break
        samples: list[float] = []
        for nr in result.node_results:
            samples.extend(v for v in nr.voltages if v > 0)
        for step in result.steps:
            if step.node_result is not None:
                samples.extend(v for v in step.node_result.voltages if v > 0)
        if not samples:
            return 0.0
        if min(samples) < self._low or max(samples) > self._high:
            return 0.0
        return pv_kw / 1000.0
