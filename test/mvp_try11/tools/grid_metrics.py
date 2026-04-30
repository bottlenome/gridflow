"""Grid-level metrics for try11 multi-feeder evaluation.

Spec: F-M2 extension of `vpp_metrics.py`.

Adds metrics that read the synthetic loads produced by
``grid_simulator.to_grid_experiment_result``:
  * VoltageViolationRatio — fraction of (sampled) timesteps with
    voltage outside [0.95, 1.05] pu
  * LineOverloadRatio — fraction with line loading > 100%
  * PFDivergenceRatio — fraction of PF runs that diverged
  * MaxLineLoadPct — peak line loading observed
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.usecase.result import ExperimentResult


def _series(result: ExperimentResult, asset_id: str) -> tuple[float, ...]:
    for lr in result.load_results:
        if lr.asset_id == asset_id:
            return lr.supplied
    raise ValueError(f"missing synthetic load: {asset_id}")


@dataclass(frozen=True)
class VoltageViolationRatio:
    name: str = "voltage_violation_ratio"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        v_min = _series(result, "__voltage_min__")
        v_max = _series(result, "__voltage_max__")
        n = len(v_min)
        if n == 0:
            return 0.0
        violations = sum(
            1 for vmin, vmax in zip(v_min, v_max)
            if vmin < 0.95 or vmax > 1.05
        )
        return violations / n


@dataclass(frozen=True)
class LineOverloadRatio:
    name: str = "line_overload_ratio"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        line_load = _series(result, "__line_load_max__")
        n = len(line_load)
        if n == 0:
            return 0.0
        return sum(1 for ll in line_load if ll > 100.0) / n


@dataclass(frozen=True)
class MaxLineLoadPct:
    name: str = "max_line_load_pct"
    unit: str = "percent"

    def calculate(self, result: ExperimentResult) -> float:
        line_load = _series(result, "__line_load_max__")
        return max(line_load) if line_load else 0.0


@dataclass(frozen=True)
class MinVoltagePu:
    name: str = "min_voltage_pu"
    unit: str = "pu"

    def calculate(self, result: ExperimentResult) -> float:
        v_min = _series(result, "__voltage_min__")
        return min(v_min) if v_min else 1.0


@dataclass(frozen=True)
class MaxVoltagePu:
    name: str = "max_voltage_pu"
    unit: str = "pu"

    def calculate(self, result: ExperimentResult) -> float:
        v_max = _series(result, "__voltage_max__")
        return max(v_max) if v_max else 1.0


GRID_METRICS: tuple = (
    VoltageViolationRatio(),
    LineOverloadRatio(),
    MaxLineLoadPct(),
    MinVoltagePu(),
    MaxVoltagePu(),
)
