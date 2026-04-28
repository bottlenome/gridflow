"""Sensitivity analysis result types — REQ-F-016.

Spec: ``docs/detailed_design/03a_domain_classes.md`` DD-CLS-051 / DD-CLS-052,
``docs/detailed_design/03b_usecase_classes.md`` §3.7.

Two frozen value objects:

* :class:`SensitivityResult` — metric vs parameter curve produced by
  :class:`gridflow.usecase.sensitivity.SensitivityAnalyzer.analyze`.
* :class:`VoltageSensitivityMatrix` — bus x bus dV/dP matrix produced
  by :meth:`SensitivityAnalyzer.analyze_voltage_matrix`.

Both are pure data — the analyser builds them, downstream tools read
them. Frozen + hashable per CLAUDE.md §0.1.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import CDLValidationError


@dataclass(frozen=True)
class SensitivityResult:
    """Metric vs parameter sensitivity curve.

    Attributes:
        feeder_id: Identifier of the network the analysis was run on
            (``ScenarioPack.pack_id`` or any caller-supplied label).
        parameter_name: Name of the swept metric kwarg (e.g.
            ``"voltage_low"``).
        parameter_values: Ordered tuple of parameter values evaluated.
        metric_name: Name of the metric whose values are recorded.
        metric_values: Tuple of mean metric values over the experiment
            set, positionally aligned with :attr:`parameter_values`.
        confidence_lower: Optional lower bootstrap CI bound per
            parameter value (same length as ``parameter_values``);
            empty tuple if bootstrap was not requested.
        confidence_upper: Optional upper bootstrap CI bound (same shape
            convention as ``confidence_lower``).
    """

    feeder_id: str
    parameter_name: str
    parameter_values: tuple[float, ...]
    metric_name: str
    metric_values: tuple[float, ...]
    confidence_lower: tuple[float, ...] = ()
    confidence_upper: tuple[float, ...] = ()

    def __post_init__(self) -> None:
        if not self.parameter_values:
            raise CDLValidationError("SensitivityResult.parameter_values must be non-empty")
        n = len(self.parameter_values)
        if len(self.metric_values) != n:
            raise CDLValidationError(
                f"SensitivityResult: metric_values length ({len(self.metric_values)}) "
                f"must match parameter_values length ({n})"
            )
        # Confidence bounds either both empty (no bootstrap) or both length n.
        if (self.confidence_lower or self.confidence_upper) and (
            len(self.confidence_lower) != n or len(self.confidence_upper) != n
        ):
            raise CDLValidationError(
                "SensitivityResult: confidence_lower / confidence_upper must "
                f"both have length {n}, got "
                f"({len(self.confidence_lower)}, {len(self.confidence_upper)})"
            )

    def to_dict(self) -> dict[str, object]:
        return {
            "feeder_id": self.feeder_id,
            "parameter_name": self.parameter_name,
            "parameter_values": list(self.parameter_values),
            "metric_name": self.metric_name,
            "metric_values": list(self.metric_values),
            "confidence_lower": list(self.confidence_lower),
            "confidence_upper": list(self.confidence_upper),
        }


@dataclass(frozen=True)
class VoltageSensitivityMatrix:
    """Bus-by-bus voltage sensitivity matrix dV_j/dP_i.

    Attributes:
        bus_ids: Ordered tuple of bus identifiers; row / column order
            of :attr:`matrix` matches this tuple.
        matrix: Outer tuple is rows (j-th = sensitivity of bus j),
            inner tuple is columns (i-th = injection at bus i).
            Square shape: ``len(bus_ids) x len(bus_ids)``.
        max_singular_value: Largest singular value of ``matrix`` (a
            scalar headline figure of merit; downstream tools compare
            this across runs to assess overall sensitivity).
    """

    bus_ids: tuple[str, ...]
    matrix: tuple[tuple[float, ...], ...]
    max_singular_value: float

    def __post_init__(self) -> None:
        n = len(self.bus_ids)
        if len(self.matrix) != n:
            raise CDLValidationError(
                f"VoltageSensitivityMatrix: matrix has {len(self.matrix)} rows but bus_ids has {n}"
            )
        for row in self.matrix:
            if len(row) != n:
                raise CDLValidationError(
                    f"VoltageSensitivityMatrix: matrix row length {len(row)} != bus_ids length {n}"
                )

    def to_dict(self) -> dict[str, object]:
        return {
            "bus_ids": list(self.bus_ids),
            "matrix": [list(row) for row in self.matrix],
            "max_singular_value": self.max_singular_value,
        }
