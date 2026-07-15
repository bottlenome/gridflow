"""Live-OpenDSS spike: a Volt-VAR strategy runs on a real feeder (issue #29).

Skipped when OpenDSS is absent (the unit-CI job); exercised by the
smoke-opendss job. Proves the capability try17 found missing: a pluggable
control *method* runs on a real circuit and changes the physical outcome.
"""

from __future__ import annotations

from pathlib import Path

import pytest

_MASTER = Path(__file__).resolve().parents[2] / "examples" / "ieee13" / "IEEE13Nodeckt.dss"


def _vmax(bus_voltages: tuple[tuple[str, float], ...]) -> float:
    return max(v for _, v in bus_voltages)


@pytest.mark.spike
class TestVoltVarOnRealFeeder:
    def _grid(self):  # type: ignore[no-untyped-def]
        pytest.importorskip("opendssdirect")
        if not _MASTER.exists():
            pytest.skip(f"IEEE13 master not found: {_MASTER}")
        from gridflow.adapter.connector.opendss_control import OpenDSSGridModel, PVDeviceSpec

        spec = PVDeviceSpec(device_id="PV675", sense_bus="675", inject_bus="675.1.2.3", kw=9000.0)
        grid = OpenDSSGridModel(master_path=str(_MASTER), devices=(spec,))
        grid._driver.Command("Set ControlMode=OFF")  # isolate Volt-VAR from regulator taps
        return grid

    def test_node_voltage_mapping_is_aligned(self) -> None:
        # #30 correctness: per-bus keys must be real bus names, and 675 (the
        # 9 MW PV bus) must be near the over-voltage, not mis-keyed noise.
        grid = self._grid()
        grid.solve()
        bv = dict(grid.bus_voltages())
        assert "675" in bv
        assert bv["675"] == pytest.approx(_vmax(grid.bus_voltages()), abs=1e-6)

    def test_no_control_leaves_over_voltage(self) -> None:
        from gridflow.usecase.control import ControllableDevice, NoControl, run_volt_var

        grid = self._grid()
        device = ControllableDevice(device_id="PV675", bus="675", kvar_limit=5000.0)
        res = run_volt_var(grid, (device,), NoControl(), max_iters=5)
        assert _vmax(res.final_bus_voltages) > 1.05  # violation stands
        assert dict(res.final_actions)["PV675"] == 0.0

    def test_local_droop_eliminates_over_voltage(self) -> None:
        from gridflow.usecase.control import ControllableDevice, LocalDroop, run_volt_var

        grid = self._grid()
        device = ControllableDevice(device_id="PV675", bus="675", kvar_limit=5000.0)
        res = run_volt_var(grid, (device,), LocalDroop(), max_iters=60, tol_kvar=2.0, relaxation=0.3)
        # The pluggable strategy absorbs reactive power and clears the violation.
        assert res.settled is True
        assert dict(res.final_actions)["PV675"] < 0.0  # absorbing
        assert _vmax(res.final_bus_voltages) <= 1.05  # over-voltage gone
