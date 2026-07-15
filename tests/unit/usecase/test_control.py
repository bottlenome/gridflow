"""Tests for the pluggable Volt-VAR control core (issue #29)."""

from __future__ import annotations

import pytest

from gridflow.usecase.control import (
    ControllableDevice,
    ControlState,
    LocalDroop,
    NoControl,
    run_volt_var,
)


class _LinearGrid:
    """Fake grid: each bus voltage responds linearly to its device's kvar.

    ``V_bus = V0_bus + sensitivity * kvar`` (sensitivity < 0 means absorbing
    vars lowers voltage — the physical case). Enough to exercise the loop and
    show droop reduces an over-voltage.
    """

    def __init__(self, v0: dict[str, float], device_bus: dict[str, str], sensitivity: float) -> None:
        # sensitivity > 0: injecting vars (kvar>0) raises voltage — matches the
        # module's stated sign convention. Absorbing (kvar<0) lowers voltage.
        self._v0 = dict(v0)
        self._device_bus = dict(device_bus)
        self._sens = sensitivity
        self._kvar: dict[str, float] = {d: 0.0 for d in device_bus}
        self.solve_calls = 0

    def bus_voltages(self) -> tuple[tuple[str, float], ...]:
        v = dict(self._v0)
        for device_id, kvar in self._kvar.items():
            bus = self._device_bus[device_id]
            v[bus] = self._v0[bus] + self._sens * kvar
        return tuple(sorted(v.items()))

    def set_reactive(self, device_id: str, kvar: float) -> None:
        self._kvar[device_id] = kvar

    def solve(self) -> bool:
        self.solve_calls += 1
        return True


class TestNoControl:
    def test_all_zero(self) -> None:
        state = ControlState(
            bus_voltages=(("b", 1.06),),
            devices=(ControllableDevice("pv", "b", 500.0),),
        )
        assert NoControl().decide(state) == {"pv": 0.0}


class TestLocalDroop:
    def test_deadband_gives_zero(self) -> None:
        d = LocalDroop()
        state = ControlState(bus_voltages=(("b", 1.00),), devices=(ControllableDevice("pv", "b", 500.0),))
        assert d.decide(state)["pv"] == 0.0

    def test_high_voltage_absorbs(self) -> None:
        d = LocalDroop()
        state = ControlState(bus_voltages=(("b", 1.05),), devices=(ControllableDevice("pv", "b", 500.0),))
        # At/above v4 -> full absorption (negative kvar).
        assert d.decide(state)["pv"] == pytest.approx(-500.0)

    def test_low_voltage_injects(self) -> None:
        d = LocalDroop()
        state = ControlState(bus_voltages=(("b", 0.95),), devices=(ControllableDevice("pv", "b", 500.0),))
        assert d.decide(state)["pv"] == pytest.approx(+500.0)

    def test_partial_droop_is_linear(self) -> None:
        d = LocalDroop(v1=0.95, v2=0.98, v3=1.02, v4=1.05)
        # Halfway through the upper ramp (1.035) -> -0.5 * limit.
        state = ControlState(bus_voltages=(("b", 1.035),), devices=(ControllableDevice("pv", "b", 400.0),))
        assert d.decide(state)["pv"] == pytest.approx(-200.0)

    def test_bad_breakpoints_rejected(self) -> None:
        with pytest.raises(ValueError, match="v1 < v2"):
            LocalDroop(v1=1.0, v2=0.9, v3=1.02, v4=1.05)


class TestRunVoltVar:
    def _devices(self) -> tuple[ControllableDevice, ...]:
        return (ControllableDevice("pv", "b", 500.0),)

    def test_no_control_leaves_voltage_unchanged(self) -> None:
        grid = _LinearGrid(v0={"b": 1.06}, device_bus={"pv": "b"}, sensitivity=2e-5)
        res = run_volt_var(grid, self._devices(), NoControl())
        assert dict(res.final_bus_voltages)["b"] == pytest.approx(1.06)
        assert dict(res.final_actions)["pv"] == 0.0

    def test_droop_reduces_over_voltage(self) -> None:
        # V starts at 1.08 (over-voltage). Droop absorbs vars (kvar<0); with a
        # positive V/Q sensitivity that lowers the voltage. Stable gain -> damps.
        grid = _LinearGrid(v0={"b": 1.08}, device_bus={"pv": "b"}, sensitivity=2e-5)
        res = run_volt_var(grid, self._devices(), LocalDroop(), max_iters=50)
        final_v = dict(res.final_bus_voltages)["b"]
        assert final_v < 1.08  # droop pulled it down
        assert dict(res.final_actions)["pv"] < 0.0  # absorbing
        assert res.iterations >= 1

    def test_loop_settles_and_reports_iterations(self) -> None:
        grid = _LinearGrid(v0={"b": 1.08}, device_bus={"pv": "b"}, sensitivity=2e-5)
        res = run_volt_var(grid, self._devices(), LocalDroop(), max_iters=50, tol_kvar=1e-2)
        assert res.settled is True
        assert res.iterations < 50
        assert res.converged is True

    def test_max_iters_bound_when_not_settling(self) -> None:
        # Large sensitivity makes the loop gain unstable: the setpoint swings
        # between full inject/absorb and never settles -> stop at max_iters.
        grid = _LinearGrid(v0={"b": 1.04}, device_bus={"pv": "b"}, sensitivity=1e-3)
        res = run_volt_var(grid, self._devices(), LocalDroop(), max_iters=5, tol_kvar=1e-6)
        assert res.iterations == 5
        assert res.settled is False

    def test_to_dict_shape(self) -> None:
        grid = _LinearGrid(v0={"b": 1.06}, device_bus={"pv": "b"}, sensitivity=-1e-4)
        res = run_volt_var(grid, self._devices(), LocalDroop())
        d = res.to_dict()
        assert d["strategy"] == "local_droop"
        assert "iterations" in d and "final_actions" in d and "final_bus_voltages" in d
