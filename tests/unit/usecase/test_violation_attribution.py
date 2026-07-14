"""Tests for :class:`ViolationAttributor` (issue #24)."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import NodeResult
from gridflow.usecase.result import ExperimentResult
from gridflow.usecase.violation_attribution import (
    ViolationAttributionError,
    ViolationAttributor,
)


def _result(nodes: dict[str, tuple[float, ...]]) -> ExperimentResult:
    meta = ExperimentMetadata(
        experiment_id="e",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="p",
        connector="fake",
    )
    node_results = tuple(NodeResult(node_id=nid, voltages=v) for nid, v in nodes.items())
    return ExperimentResult(experiment_id="e", metadata=meta, node_results=node_results)


class TestViolationAttributor:
    def test_pre_existing_violations_are_baseline_only(self) -> None:
        # Both baseline and candidate breach the low bound at the same bus →
        # the controller is not charged for it.
        base = _result({"n1": (0.90, 0.90)})
        cand = _result({"n1": (0.90, 0.90)})
        attr = ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
        assert attr.total_rate == pytest.approx(1.0)
        assert attr.baseline_only_rate == pytest.approx(1.0)
        assert attr.dispatch_induced_rate == pytest.approx(0.0)

    def test_controller_induced_violations_counted(self) -> None:
        # Baseline in band, candidate out of band → the controller's doing.
        base = _result({"n1": (1.00, 1.00)})
        cand = _result({"n1": (1.10, 1.00)})  # 1 of 2 induced
        attr = ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
        assert attr.total_rate == pytest.approx(0.5)
        assert attr.dispatch_induced_rate == pytest.approx(0.5)
        assert attr.baseline_only_rate == pytest.approx(0.0)

    def test_total_equals_sum_of_causes(self) -> None:
        base = _result({"n1": (0.90, 1.00, 1.00)})  # sample0 pre-existing
        cand = _result({"n1": (0.90, 1.10, 1.00)})  # sample0 baseline_only, sample1 induced
        attr = ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
        assert attr.total_rate == pytest.approx(attr.baseline_only_rate + attr.dispatch_induced_rate)
        assert attr.baseline_only_rate == pytest.approx(1 / 3)
        assert attr.dispatch_induced_rate == pytest.approx(1 / 3)

    def test_no_violations(self) -> None:
        base = _result({"n1": (1.00,)})
        cand = _result({"n1": (1.00,)})
        attr = ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
        assert attr.total_rate == 0.0

    def test_envelope_stamped_in_to_dict(self) -> None:
        base = _result({"n1": (1.0,)})
        cand = _result({"n1": (1.0,)})
        attr = ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
        d = attr.to_dict()
        assert d["envelope"] == {"v_min": 0.95, "v_max": 1.05}

    def test_bad_envelope_rejected(self) -> None:
        base = _result({"n1": (1.0,)})
        cand = _result({"n1": (1.0,)})
        with pytest.raises(ViolationAttributionError, match="v_min"):
            ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=1.05, v_max=0.95)

    def test_mismatched_node_sets_rejected(self) -> None:
        base = _result({"n1": (1.0,)})
        cand = _result({"n2": (1.0,)})
        with pytest.raises(ViolationAttributionError, match="different node sets"):
            ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)

    def test_mismatched_sample_lengths_rejected(self) -> None:
        base = _result({"n1": (1.0, 1.0)})
        cand = _result({"n1": (1.0,)})
        with pytest.raises(ViolationAttributionError, match="cannot align"):
            ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)

    def test_empty_results_rejected(self) -> None:
        base = _result({})
        cand = _result({})
        with pytest.raises(ViolationAttributionError, match="no voltage samples"):
            ViolationAttributor().attribute(baseline=base, candidate=cand, v_min=0.95, v_max=1.05)
