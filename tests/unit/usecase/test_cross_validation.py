"""Tests for :class:`EngineCrossValidator` (issue #20)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import NodeResult
from gridflow.usecase.cross_validation import (
    CrossValidationError,
    EngineCrossValidator,
)
from gridflow.usecase.result import ExperimentResult, StepResult, StepStatus


def _result(
    *,
    nodes: dict[str, tuple[float, ...]],
    step_statuses: tuple[StepStatus, ...] = (StepStatus.SUCCESS,),
) -> ExperimentResult:
    meta = ExperimentMetadata(
        experiment_id="e",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="pack@1.0.0",
        connector="fake",
    )
    steps = tuple(
        StepResult(
            step_id=i,
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            status=status,
            elapsed_ms=1.0,
        )
        for i, status in enumerate(step_statuses)
    )
    node_results = tuple(NodeResult(node_id=nid, voltages=v) for nid, v in nodes.items())
    return ExperimentResult(experiment_id="e", metadata=meta, steps=steps, node_results=node_results)


class TestEngineCrossValidator:
    def test_agree_within_tol(self) -> None:
        a = _result(nodes={"n1": (1.00, 0.99)})
        b = _result(nodes={"n1": (1.0000005, 0.9900004)})
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        assert report.agree is True
        assert report.reference_engine == "opendss"
        assert report.comparisons[0].max_abs_diff < 1e-3
        assert not report.comparisons[0].mismatches

    def test_disagree_beyond_tol(self) -> None:
        a = _result(nodes={"n1": (1.00,)})
        b = _result(nodes={"n1": (1.05,)})  # 0.05 pu apart
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        assert report.agree is False
        mism = report.comparisons[0].mismatches
        assert len(mism) == 1
        assert mism[0].node_id == "n1"
        assert mism[0].step == 0
        assert mism[0].abs_diff == pytest.approx(0.05)

    def test_missing_node_is_structural_mismatch(self) -> None:
        a = _result(nodes={"n1": (1.0,), "n2": (1.0,)})
        b = _result(nodes={"n1": (1.0,)})  # n2 absent
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        assert report.agree is False
        structural = [m for m in report.comparisons[0].mismatches if m.step == -1]
        assert [m.node_id for m in structural] == ["n2"]

    def test_extra_node_on_candidate_is_mismatch(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        b = _result(nodes={"n1": (1.0,), "n_extra": (1.0,)})
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        assert report.agree is False
        assert any(m.node_id == "n_extra" for m in report.comparisons[0].mismatches)

    def test_voltage_length_mismatch_is_structural(self) -> None:
        a = _result(nodes={"n1": (1.0, 1.0)})
        b = _result(nodes={"n1": (1.0,)})
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        assert report.agree is False
        assert report.comparisons[0].mismatches[0].step == -1

    def test_non_convergence_fails_agreement(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        # Same voltages, but candidate did not converge on its step.
        b = _result(nodes={"n1": (1.0,)}, step_statuses=(StepStatus.ERROR,))
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("opendss", a), ("pandapower", b)],
            tol=1e-3,
        )
        # Voltages match, but a non-converged engine must not read as agreement.
        assert report.comparisons[0].agree is True
        assert report.agree is False
        pp = next(cv for cv in report.convergence if cv.engine == "pandapower")
        assert pp.non_converged_steps == (0,)

    def test_three_engines_all_vs_reference(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        b = _result(nodes={"n1": (1.0,)})
        c = _result(nodes={"n1": (2.0,)})
        report = EngineCrossValidator().validate(
            pack_id="p",
            results_by_engine=[("ref", a), ("b", b), ("c", c)],
            tol=1e-3,
        )
        # Two comparisons (b, c) against the reference; c disagrees.
        assert {cmp.engine for cmp in report.comparisons} == {"b", "c"}
        assert report.agree is False

    def test_fewer_than_two_engines_rejected(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        with pytest.raises(CrossValidationError, match="at least 2"):
            EngineCrossValidator().validate(pack_id="p", results_by_engine=[("only", a)], tol=1e-3)

    def test_negative_tol_rejected(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        b = _result(nodes={"n1": (1.0,)})
        with pytest.raises(CrossValidationError, match="non-negative"):
            EngineCrossValidator().validate(pack_id="p", results_by_engine=[("a", a), ("b", b)], tol=-1.0)

    def test_duplicate_engine_names_rejected(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        b = _result(nodes={"n1": (1.0,)})
        with pytest.raises(CrossValidationError, match="unique"):
            EngineCrossValidator().validate(pack_id="p", results_by_engine=[("x", a), ("x", b)], tol=1e-3)

    def test_report_to_dict_roundtrip_shape(self) -> None:
        a = _result(nodes={"n1": (1.0,)})
        b = _result(nodes={"n1": (1.05,)})
        report = EngineCrossValidator().validate(
            pack_id="pk", results_by_engine=[("opendss", a), ("pandapower", b)], tol=1e-3
        )
        d = report.to_dict()
        assert d["pack_id"] == "pk"
        assert d["agree"] is False
        assert d["comparisons"][0]["engine"] == "pandapower"
        assert d["comparisons"][0]["mismatches"][0]["abs_diff"] == pytest.approx(0.05)
        assert d["convergence"][0]["engine"] == "opendss"
