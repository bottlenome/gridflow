"""Tests for simulation result domain models (time-series value objects)."""

from gridflow.domain.result import (
    BranchResult,
    GeneratorResult,
    Interruption,
    LoadResult,
    NodeResult,
    RenewableResult,
)


class TestNodeResult:
    def test_voltage_at(self) -> None:
        nr = NodeResult(node_id="650", voltages=(1.0, 0.98, 1.02))
        assert nr.voltage_at(0) == 1.0
        assert nr.voltage_at(1) == 0.98


class TestBranchResult:
    def test_current_and_loss(self) -> None:
        br = BranchResult(edge_id="650-632", currents=(100.0, 110.0), losses_kw=(1.5, 1.8), i_rated=200.0)
        assert br.current_at(0) == 100.0
        assert br.loss_kw_at(1) == 1.8


class TestLoadResult:
    def test_demand_and_supplied(self) -> None:
        lr = LoadResult(asset_id="load-1", demands=(50.0, 60.0), supplied=(50.0, 55.0))
        assert lr.demand_at(0) == 50.0
        assert lr.supplied_at(1) == 55.0


class TestGeneratorResult:
    def test_power_at(self) -> None:
        gr = GeneratorResult(asset_id="gen-1", powers=(500.0, 520.0), cost_per_unit=0.05, emission_factor=0.4)
        assert gr.power_at(1) == 520.0


class TestRenewableResult:
    def test_available_and_dispatched(self) -> None:
        rr = RenewableResult(asset_id="pv-1", available=(100.0, 110.0), dispatched=(90.0, 100.0))
        assert rr.available_at(0) == 100.0
        assert rr.dispatched_at(1) == 100.0


class TestInterruption:
    def test_create(self) -> None:
        intr = Interruption(
            event_id="int-1", start_time=0.0, end_time=3600.0, duration_min=60.0, customers_affected=100, cause="fault"
        )
        assert intr.duration_min == 60.0
        assert intr.customers_affected == 100
