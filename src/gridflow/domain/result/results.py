"""Simulation result domain models (time-series value objects).

Aggregate container :class:`~gridflow.usecase.result.ExperimentResult` lives
in the Use Case layer (phase0_result §7.2 5.5).
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class NodeResult:
    """Per-node time series simulation result.

    Attributes:
        node_id: Target node ID.
        voltages: Voltage values per step (pu).
    """

    node_id: str
    voltages: tuple[float, ...]

    def voltage_at(self, step: int) -> float:
        """Return voltage at the given step."""
        return self.voltages[step]


@dataclass(frozen=True)
class BranchResult:
    """Per-branch time series simulation result.

    Attributes:
        edge_id: Target edge ID.
        currents: Current values per step (A).
        losses_kw: Loss values per step (kW).
        i_rated: Rated current (A).
    """

    edge_id: str
    currents: tuple[float, ...]
    losses_kw: tuple[float, ...]
    i_rated: float

    def current_at(self, step: int) -> float:
        """Return current at the given step."""
        return self.currents[step]

    def loss_kw_at(self, step: int) -> float:
        """Return loss at the given step."""
        return self.losses_kw[step]


@dataclass(frozen=True)
class LoadResult:
    """Per-load time series simulation result.

    Attributes:
        asset_id: Target load asset ID.
        demands: Demand values per step (kW).
        supplied: Supplied values per step (kW).
    """

    asset_id: str
    demands: tuple[float, ...]
    supplied: tuple[float, ...]

    def demand_at(self, step: int) -> float:
        """Return demand at the given step."""
        return self.demands[step]

    def supplied_at(self, step: int) -> float:
        """Return supplied value at the given step."""
        return self.supplied[step]


@dataclass(frozen=True)
class GeneratorResult:
    """Per-generator time series simulation result.

    Attributes:
        asset_id: Target generator asset ID.
        powers: Power output values per step (kW).
        cost_per_unit: Unit generation cost (USD/kWh).
        emission_factor: CO2 emission factor (tCO2/kWh).
    """

    asset_id: str
    powers: tuple[float, ...]
    cost_per_unit: float
    emission_factor: float

    def power_at(self, step: int) -> float:
        """Return power output at the given step."""
        return self.powers[step]


@dataclass(frozen=True)
class RenewableResult:
    """Per-renewable time series simulation result.

    Attributes:
        asset_id: Target renewable asset ID.
        available: Available output per step (kW).
        dispatched: Dispatched output per step (kW).
    """

    asset_id: str
    available: tuple[float, ...]
    dispatched: tuple[float, ...]

    def available_at(self, step: int) -> float:
        """Return available output at the given step."""
        return self.available[step]

    def dispatched_at(self, step: int) -> float:
        """Return dispatched output at the given step."""
        return self.dispatched[step]


@dataclass(frozen=True)
class Interruption:
    """Outage event for IEEE 1366 reliability metrics.

    Attributes:
        event_id: Outage event ID.
        start_time: Outage start time (seconds).
        end_time: Outage end time (seconds).
        duration_min: Outage duration (minutes).
        customers_affected: Number of affected customers.
        cause: Cause ("fault" | "maintenance" | "overload").
    """

    event_id: str
    start_time: float
    end_time: float
    duration_min: float
    customers_affected: int
    cause: str
