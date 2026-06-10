"""Simulation result domain models (time-series value objects).

The aggregate :class:`~gridflow.usecase.result.ExperimentResult` lives in the
Use Case layer; import it from ``gridflow.usecase.result`` instead.
"""

from gridflow.domain.result.comparison_table import (
    ComparisonTable,
    MethodRow,
    MetricSpec,
    MetricValue,
)
from gridflow.domain.result.results import (
    BranchResult,
    GeneratorResult,
    Interruption,
    LoadResult,
    NodeResult,
    RenewableResult,
)
from gridflow.domain.result.sensitivity import (
    SensitivityResult,
    VoltageSensitivityMatrix,
)

__all__ = [
    "BranchResult",
    "ComparisonTable",
    "GeneratorResult",
    "Interruption",
    "LoadResult",
    "MethodRow",
    "MetricSpec",
    "MetricValue",
    "NodeResult",
    "RenewableResult",
    "SensitivityResult",
    "VoltageSensitivityMatrix",
]
