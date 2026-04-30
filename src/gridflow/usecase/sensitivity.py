"""SensitivityAnalyzer — REQ-F-016 / detailed_design 03b §3.7.

Post-processes a set of already-simulated :class:`ExperimentResult`
objects under a parametric metric sweep (e.g. "evaluate the same
voltage data at 11 different threshold values") and returns a
:class:`SensitivityResult` curve. Optionally also computes a
bus x bus voltage sensitivity matrix from PV-injection experiments.

Design principles (CLAUDE.md §0.1):
    * Pure UseCase — no Connector, no Registry. Inputs are already-
      computed ExperimentResults.
    * `MetricCalculator` is the Strategy injection point: callers pass
      a class whose constructor accepts the swept kwarg.
    * Frozen `SensitivityResult` / `VoltageSensitivityMatrix` outputs
      so the entire chain stays hashable / round-trippable.

Why this is a separate class from :class:`Evaluator` (§5.1.1 Option B
post-processing): Evaluator applies a *fixed* set of MetricSpecs to N
experiments. SensitivityAnalyzer applies *one* metric class with K
different kwarg values to the same N experiments → produces a 1-D
curve (parameter → mean metric). Both share the underlying
MetricCalculator Protocol and the BenchmarkHarness machinery, but
their output shapes (per-experiment column tuple vs sensitivity curve)
and call patterns differ enough that splitting keeps each focused on
one job (CLAUDE.md §0.5.1).
"""

from __future__ import annotations

import math
import random
import statistics
from collections.abc import Sequence

from gridflow.adapter.benchmark.metric_registry import load_metric_plugin
from gridflow.domain.error import GridflowError
from gridflow.domain.result import SensitivityResult, VoltageSensitivityMatrix
from gridflow.domain.util.params import get_param
from gridflow.usecase.result import ExperimentResult


class SensitivityAnalysisError(GridflowError):
    """Raised when the analyser cannot complete (empty input, bad plugin, etc.)."""

    error_code = "E-30100"


class SensitivityAnalyzer:
    """Drive a parameter sweep on a fixed set of experiments.

    Stateless — the caller owns ExperimentResults and the metric class.
    """

    def analyze(
        self,
        *,
        experiments: Sequence[ExperimentResult],
        parameter_name: str,
        parameter_grid: Sequence[float],
        metric_plugin: str,
        metric_kwargs_base: dict[str, object] | None = None,
        feeder_id: str = "unknown",
        bootstrap_n: int = 0,
        bootstrap_seed: int = 0,
    ) -> SensitivityResult:
        """Re-evaluate ``experiments`` at each ``parameter_grid`` point.

        Args:
            experiments: Already-simulated experiments to re-evaluate.
                All must come from the same sweep / scenario; the
                analyser does not check this — feeder_id is the
                provenance signal the caller is responsible for.
            parameter_name: The metric kwarg key being swept.
            parameter_grid: Ordered values to evaluate ``metric_plugin``
                at; each becomes one point on the output curve.
            metric_plugin: ``"module:Class"`` plugin spec; instantiated
                fresh for every grid point with
                ``{**metric_kwargs_base, parameter_name: value}``.
            metric_kwargs_base: Other kwargs forwarded to the plugin
                constructor (constants across the sweep).
            feeder_id: Provenance label written to the result.
            bootstrap_n: If > 0, resample the experiments ``bootstrap_n``
                times with replacement at each grid point and emit
                95% CI bounds on the mean.
            bootstrap_seed: Seed for bootstrap resampling.

        Returns:
            :class:`SensitivityResult` with the metric curve.
        """
        if not experiments:
            raise SensitivityAnalysisError("SensitivityAnalyzer.analyze: experiments must be non-empty")
        if not parameter_grid:
            raise SensitivityAnalysisError("SensitivityAnalyzer.analyze: parameter_grid must be non-empty")

        base_kwargs = dict(metric_kwargs_base or {})
        if parameter_name in base_kwargs:
            # Caller put the swept key into the base — the loop below
            # will overwrite it; warn loudly through the error rather
            # than silently shadowing.
            raise SensitivityAnalysisError(
                f"parameter_name '{parameter_name}' must not also appear in metric_kwargs_base; "
                "the per-grid-point value would silently override it"
            )

        # Probe the metric_plugin once so a bad spec fails fast rather
        # than after the first grid point.
        try:
            probe = load_metric_plugin(metric_plugin, kwargs={**base_kwargs, parameter_name: parameter_grid[0]})
        except Exception as exc:
            raise SensitivityAnalysisError(
                f"failed to load metric plugin '{metric_plugin}': {exc}",
                cause=exc,
            ) from exc
        metric_name = probe.name

        means: list[float] = []
        ci_lower: list[float] = []
        ci_upper: list[float] = []
        for value in parameter_grid:
            kwargs = {**base_kwargs, parameter_name: value}
            metric = load_metric_plugin(metric_plugin, kwargs=kwargs)
            per_exp_values = [float(metric.calculate(exp)) for exp in experiments]
            means.append(float(statistics.fmean(per_exp_values)))
            if bootstrap_n > 0:
                lo, hi = _bootstrap_ci(per_exp_values, bootstrap_n=bootstrap_n, seed=bootstrap_seed)
                ci_lower.append(lo)
                ci_upper.append(hi)

        return SensitivityResult(
            feeder_id=feeder_id,
            parameter_name=parameter_name,
            parameter_values=tuple(float(v) for v in parameter_grid),
            metric_name=metric_name,
            metric_values=tuple(means),
            confidence_lower=tuple(ci_lower),
            confidence_upper=tuple(ci_upper),
        )

    def analyze_voltage_matrix(
        self,
        *,
        experiments: Sequence[ExperimentResult],
    ) -> VoltageSensitivityMatrix:
        """Estimate dV_j / dP_i from PV-injection experiments.

        Each experiment's :class:`ExperimentMetadata.parameters` must
        carry ``pv_bus`` (the bus index where PV was injected) and
        ``pv_kw`` (active power injection in kW). A baseline experiment
        with ``pv_kw == 0`` (or equivalent absent injection) is needed
        as the reference voltage vector.

        Returns the bus x bus matrix S = ΔV / ΔP, the bus_ids in row /
        column order, and S's largest singular value (a scalar
        figure-of-merit).
        """
        if not experiments:
            raise SensitivityAnalysisError("SensitivityAnalyzer.analyze_voltage_matrix: experiments must be non-empty")

        injection_records = [_extract_injection(exp) for exp in experiments]
        baseline = next(
            (record for record in injection_records if record.pv_kw == 0.0),
            None,
        )
        if baseline is None:
            raise SensitivityAnalysisError(
                "analyze_voltage_matrix needs a baseline experiment with pv_kw == 0; "
                "provide one explicitly so ΔV is well-defined"
            )

        # Sanity-check that at least one experiment has a positive
        # injection — without it the matrix is all zeros which is not a
        # useful answer. Note the explicit ``is not None`` rather than
        # ``if r.pv_bus`` because ``pv_bus=0`` (a valid integer bus
        # index) is falsy under Python truthiness.
        if not any(r.pv_bus is not None and r.pv_kw > 0 for r in injection_records):
            raise SensitivityAnalysisError("analyze_voltage_matrix needs at least one experiment with pv_kw > 0")

        # Group experiments by injection bus (multiple kW levels per bus
        # are averaged for a single dV/dP estimate).
        baseline_voltages = baseline.voltages
        n_buses = len(baseline_voltages)
        if n_buses == 0:
            raise SensitivityAnalysisError("baseline experiment has zero voltages — cannot build sensitivity matrix")

        # Use the baseline voltage vector's positional indices as bus_ids
        # since real bus name metadata is not always carried inside
        # NodeResult. The matrix is square (bus x bus) with row j =
        # voltage at bus j, column i = injection at bus i.
        bus_ids = tuple(f"bus_{i}" for i in range(n_buses))

        # Build columns of S: for each injection bus, take the average
        # ΔV / ΔP across all matching injection experiments.
        # injection bus index → (dV vector, count)
        column_lookup: dict[int, list[tuple[tuple[float, ...], float]]] = {}
        for record in injection_records:
            if record.pv_kw <= 0:
                continue
            try:
                inj_idx = int(str(record.pv_bus))
            except (TypeError, ValueError):
                # Non-integer pv_bus (e.g. "loadbus") — fall back to
                # positional index in bus_ids if it matches a generated
                # name; otherwise skip with a clear error.
                raise SensitivityAnalysisError(
                    f"analyze_voltage_matrix requires integer pv_bus, got {record.pv_bus!r}"
                ) from None
            dV = tuple(v_after - v_before for v_after, v_before in zip(record.voltages, baseline_voltages, strict=True))
            column_lookup.setdefault(inj_idx, []).append((dV, record.pv_kw))

        # Square matrix; default zero where no injection observed.
        # Rows are bus j, columns are injection at bus i.
        matrix_rows: list[list[float]] = [[0.0] * n_buses for _ in range(n_buses)]
        for inj_idx, samples in column_lookup.items():
            if not 0 <= inj_idx < n_buses:
                continue
            # Average dV/dP across samples for this injection bus.
            n = len(samples)
            avg_per_bus: list[float] = [0.0] * n_buses
            for dV, kw in samples:
                for j, dv_j in enumerate(dV):
                    avg_per_bus[j] += dv_j / kw
            for j in range(n_buses):
                avg_per_bus[j] /= n
            # Populate column inj_idx of the matrix.
            for j in range(n_buses):
                matrix_rows[j][inj_idx] = avg_per_bus[j]

        matrix = tuple(tuple(row) for row in matrix_rows)
        max_sv = _largest_singular_value(matrix)
        return VoltageSensitivityMatrix(
            bus_ids=bus_ids,
            matrix=matrix,
            max_singular_value=max_sv,
        )


# ----------------------------------------------------------------- helpers


class _Injection:
    """Lightweight tuple of (pv_bus, pv_kw, voltages) extracted from an experiment."""

    __slots__ = ("pv_bus", "pv_kw", "voltages")

    def __init__(self, pv_bus: object, pv_kw: float, voltages: tuple[float, ...]) -> None:
        self.pv_bus = pv_bus
        self.pv_kw = pv_kw
        self.voltages = voltages


def _extract_injection(exp: ExperimentResult) -> _Injection:
    """Pull pv_bus / pv_kw from ExperimentMetadata.parameters, voltages from node_results."""
    pv_kw_raw = get_param(exp.metadata.parameters, "pv_kw")
    try:
        pv_kw = float(pv_kw_raw) if pv_kw_raw is not None else 0.0  # type: ignore[arg-type]
    except (TypeError, ValueError):
        pv_kw = 0.0
    pv_bus = get_param(exp.metadata.parameters, "pv_bus")
    voltages: tuple[float, ...] = ()
    for nr in exp.node_results:
        voltages = tuple(float(v) for v in nr.voltages)
        break
    return _Injection(pv_bus=pv_bus, pv_kw=pv_kw, voltages=voltages)


def _bootstrap_ci(
    values: list[float],
    *,
    bootstrap_n: int,
    seed: int,
    confidence: float = 0.95,
) -> tuple[float, float]:
    """Percentile bootstrap CI for the mean."""
    rng = random.Random(seed)
    n = len(values)
    means: list[float] = []
    for _ in range(bootstrap_n):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_idx = max(0, int(alpha * bootstrap_n))
    hi_idx = min(bootstrap_n - 1, int((1.0 - alpha) * bootstrap_n))
    return float(means[lo_idx]), float(means[hi_idx])


def _largest_singular_value(matrix: tuple[tuple[float, ...], ...]) -> float:
    """Power-iteration estimate of the largest singular value of ``matrix``.

    Numpy is not in the core dependency closure for this module path,
    but the analyser can be called from environments that don't have
    scipy's ``svd`` available either. Power iteration on Aᵀ A converges
    to the squared largest singular value; we sqrt at the end.

    For square matrices up to ~50x50 (current use case: feeder buses),
    this converges in well under 100 iterations to machine precision.
    """
    n = len(matrix)
    if n == 0:
        return 0.0
    # b = AᵀA → largest eigenvalue is sigma_max ²
    ata = [[0.0] * n for _ in range(n)]
    for i in range(n):
        for j in range(n):
            s = 0.0
            for k in range(n):
                s += matrix[k][i] * matrix[k][j]
            ata[i][j] = s

    # Power iteration on AᵀA.
    x = [1.0] * n
    norm = math.sqrt(sum(v * v for v in x))
    if norm == 0.0:
        return 0.0
    x = [v / norm for v in x]
    for _ in range(200):
        y = [sum(ata[i][j] * x[j] for j in range(n)) for i in range(n)]
        norm = math.sqrt(sum(v * v for v in y))
        if norm == 0.0:
            return 0.0
        new_x = [v / norm for v in y]
        # Convergence check: ||new_x - x|| in L∞.
        delta = max(abs(new_x[i] - x[i]) for i in range(n))
        x = new_x
        if delta < 1e-10:
            break
    # Final Rayleigh quotient on AᵀA = sigma_max ²
    rq = sum(x[i] * sum(ata[i][j] * x[j] for j in range(n)) for i in range(n))
    return math.sqrt(max(0.0, rq))


__all__ = [
    "SensitivityAnalysisError",
    "SensitivityAnalyzer",
]
