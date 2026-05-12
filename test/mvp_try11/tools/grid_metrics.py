"""Grid-level metrics for try11 multi-feeder evaluation.

Spec: F-M2 extension of `vpp_metrics.py`.

Adds metrics that read the synthetic loads produced by
``grid_simulator.to_grid_experiment_result``:
  * VoltageViolationRatio — fraction of (sampled) timesteps with
    voltage outside [0.95, 1.05] pu (= legacy combined ratio)
  * VoltageBaselineViolationRatio — fraction violating *with no DER
    injection* (= existing-load-induced; M7 cannot improve)
  * VoltageDispatchInducedViolationRatio — fraction where the dispatch
    introduced a violation that the baseline did not have (= M7's
    actual responsibility, what reviewers should focus on)
  * LineOverloadRatio — fraction with line loading > 100%
  * PFDivergenceRatio — fraction of PF runs that diverged
  * MaxLineLoadPct — peak line loading observed

The baseline-vs-dispatch decomposition (Phase D-1) was added to address
PWRS reviewer C3: the legacy combined ratio mixes (a) existing-load
violations the controller is structurally unable to repair (positive
injection only raises voltage) with (b) dispatch-induced violations,
inflating the headline number unfairly. See ``NEXT_STEPS.md §3``.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.usecase.result import ExperimentResult


def _series(result: ExperimentResult, asset_id: str) -> tuple[float, ...]:
    for lr in result.load_results:
        if lr.asset_id == asset_id:
            return lr.supplied
    raise ValueError(f"missing synthetic load: {asset_id}")


def _violates(vmin: float, vmax: float) -> bool:
    return vmin < 0.95 or vmax > 1.05


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
            1 for vmin, vmax in zip(v_min, v_max, strict=True)
            if _violates(vmin, vmax)
        )
        return violations / n


@dataclass(frozen=True)
class VoltageBaselineViolationRatio:
    """Fraction of steps already violating with zero DER injection.

    These are violations the SDP controller cannot repair (positive
    injection only raises voltage; existing-load-induced V_min<0.95
    cannot be cured by a non-negative dispatch). Reported separately
    so reviewers can see which violations are M7's responsibility.
    """

    name: str = "voltage_violation_baseline_only"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        v_min_b = _series(result, "__voltage_baseline_min__")
        v_max_b = _series(result, "__voltage_baseline_max__")
        n = len(v_min_b)
        if n == 0:
            return 0.0
        violations = sum(
            1 for vmin, vmax in zip(v_min_b, v_max_b, strict=True)
            if _violates(vmin, vmax)
        )
        return violations / n


@dataclass(frozen=True)
class VoltageDispatchInducedViolationRatio:
    """Fraction of steps where the dispatch caused a NEW violation.

    A step counts as dispatch-induced iff the actual voltage violates
    *and* the baseline at the same step does not. This isolates the
    controller's responsibility from the feeder's structural issues.
    """

    name: str = "voltage_violation_dispatch_induced"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        v_min = _series(result, "__voltage_min__")
        v_max = _series(result, "__voltage_max__")
        v_min_b = _series(result, "__voltage_baseline_min__")
        v_max_b = _series(result, "__voltage_baseline_max__")
        n = len(v_min)
        if n == 0:
            return 0.0
        induced = sum(
            1
            for vmin, vmax, vmin_b, vmax_b in zip(
                v_min, v_max, v_min_b, v_max_b, strict=True
            )
            if _violates(vmin, vmax) and not _violates(vmin_b, vmax_b)
        )
        return induced / n


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
    VoltageBaselineViolationRatio(),
    VoltageDispatchInducedViolationRatio(),
    LineOverloadRatio(),
    MaxLineLoadPct(),
    MinVoltagePu(),
    MaxVoltagePu(),
)
