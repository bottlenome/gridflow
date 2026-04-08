"""Built-in metric calculators for benchmark comparisons."""

from gridflow.adapter.benchmark.metrics.base import MetricCalculator
from gridflow.adapter.benchmark.metrics.runtime import RuntimeMetric
from gridflow.adapter.benchmark.metrics.voltage_deviation import VoltageDeviationMetric

BUILTIN_METRICS: tuple[MetricCalculator, ...] = (
    VoltageDeviationMetric(),
    RuntimeMetric(),
)

__all__ = [
    "BUILTIN_METRICS",
    "MetricCalculator",
    "RuntimeMetric",
    "VoltageDeviationMetric",
]
