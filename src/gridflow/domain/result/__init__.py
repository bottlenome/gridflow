"""Simulation result domain models (time-series value objects).

The aggregate :class:`~gridflow.usecase.result.ExperimentResult` lives in the
Use Case layer; import it from ``gridflow.usecase.result`` instead.
"""

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
    "GeneratorResult",
    "Interruption",
    "LoadResult",
    "NodeResult",
    "RenewableResult",
    "SensitivityResult",
    "VoltageSensitivityMatrix",
]
