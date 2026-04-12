"""Tests for UseCase-layer orchestration types (ExecutionPlan, StepConfig, HealthStatus).

Spec: docs/detailed_design/03b_usecase_classes.md §3.3.4 / §3.3.5 / §3.5.5.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.scenario import PackMetadata, ScenarioPack
from gridflow.usecase.execution_plan import ExecutionPlan, StepConfig
from gridflow.usecase.interfaces import HealthStatus


def _pack() -> ScenarioPack:
    meta = PackMetadata(
        name="t",
        version="1.0.0",
        description="d",
        author="a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
    )
    return ScenarioPack(
        pack_id="t@1.0.0",
        name="t",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/tmp"),
        timeseries_dir=Path("/tmp"),
        config_dir=Path("/tmp"),
    )


class TestStepConfig:
    def test_is_frozen_dataclass(self) -> None:
        step = StepConfig(step_id=0)
        with pytest.raises((AttributeError, Exception)):
            step.step_id = 1  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        assert {StepConfig(step_id=0), StepConfig(step_id=0)} == {StepConfig(step_id=0)}


class TestHealthStatus:
    def test_schema(self) -> None:
        """Spec 03b §3.5.5: ``HealthStatus`` has ``healthy: bool`` and ``message: str``."""
        status = HealthStatus(healthy=True, message="ok")
        assert status.healthy is True
        assert status.message == "ok"

    def test_is_frozen(self) -> None:
        status = HealthStatus(healthy=True, message="ok")
        with pytest.raises((AttributeError, Exception)):
            status.healthy = False  # type: ignore[misc]

    def test_is_hashable(self) -> None:
        assert hash(HealthStatus(healthy=True, message="ok")) == hash(HealthStatus(healthy=True, message="ok"))


class TestExecutionPlan:
    def test_basic_construction(self) -> None:
        plan = ExecutionPlan(
            experiment_id="exp-001",
            pack=_pack(),
            steps=(StepConfig(step_id=0), StepConfig(step_id=1)),
            connectors=("opendss",),
        )
        assert plan.experiment_id == "exp-001"
        assert plan.pack.pack_id == "t@1.0.0"
        assert len(plan.steps) == 2
        assert plan.connectors == ("opendss",)
        assert plan.parameters == ()

    def test_is_frozen(self) -> None:
        plan = ExecutionPlan(
            experiment_id="exp-001",
            pack=_pack(),
            steps=(),
            connectors=("opendss",),
        )
        with pytest.raises((AttributeError, Exception)):
            plan.experiment_id = "other"  # type: ignore[misc]

    def test_parameters_must_be_params_tuple(self) -> None:
        """CLAUDE.md §0.1: parameters is always a sorted tuple of pairs, never a dict."""
        plan = ExecutionPlan(
            experiment_id="exp-001",
            pack=_pack(),
            steps=(),
            connectors=("opendss",),
            parameters=(("foo", 1), ("bar", 2)),
        )
        assert isinstance(plan.parameters, tuple)

    def test_is_hashable(self) -> None:
        plan = ExecutionPlan(
            experiment_id="exp-001",
            pack=_pack(),
            steps=(StepConfig(step_id=0),),
            connectors=("opendss",),
        )
        hash(plan)  # must not raise
