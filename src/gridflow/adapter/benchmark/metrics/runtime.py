"""Runtime metric: total experiment wall-clock time (seconds)."""

from __future__ import annotations

from gridflow.usecase.result import ExperimentResult


class RuntimeMetric:
    name = "runtime"
    unit = "s"

    def calculate(self, result: ExperimentResult) -> float:
        return float(result.elapsed_s)
