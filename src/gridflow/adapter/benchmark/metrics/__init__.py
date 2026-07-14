"""Built-in metric calculators for benchmark comparisons."""

from gridflow.adapter.benchmark.metrics.base import MetricCalculator
from gridflow.adapter.benchmark.metrics.convergence import NonConvergenceRateMetric
from gridflow.adapter.benchmark.metrics.runtime import RuntimeMetric
from gridflow.adapter.benchmark.metrics.voltage_deviation import VoltageDeviationMetric
from gridflow.adapter.benchmark.metrics.voltage_violation_rate import VoltageViolationRateMetric

BUILTIN_METRICS: tuple[MetricCalculator, ...] = (
    VoltageDeviationMetric(),
    VoltageViolationRateMetric(),
    NonConvergenceRateMetric(),
    RuntimeMetric(),
)

__all__ = [
    "BUILTIN_METRICS",
    "MetricCalculator",
    "NonConvergenceRateMetric",
    "RuntimeMetric",
    "VoltageDeviationMetric",
    "VoltageViolationRateMetric",
]
