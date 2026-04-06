"""OpenDSS smoke test - IEEE 13-node feeder power flow.

This test validates that DSS-Python can execute a power flow calculation
on the IEEE 13-node test feeder and retrieve node voltages.

Prerequisites:
    - OpenDSSDirect.py installed (pip install OpenDSSDirect.py)
    - IEEE 13-node test feeder DSS files in examples/ieee13/

Run with: pytest tests/spike/test_opendss_smoke.py -m spike
"""

from __future__ import annotations

from pathlib import Path

import pytest

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples" / "ieee13"


@pytest.mark.spike
class TestOpenDSSSmoke:
    """Smoke tests for OpenDSS via DSS-Python."""

    def test_import_opendssdirect(self) -> None:
        """Verify OpenDSSDirect.py can be imported."""
        opendssdirect = pytest.importorskip("opendssdirect")
        assert hasattr(opendssdirect, "run_command")

    def test_ieee13_power_flow(self) -> None:
        """Run IEEE 13-node feeder power flow and verify convergence."""
        opendssdirect = pytest.importorskip("opendssdirect")

        master_file = EXAMPLES_DIR / "IEEE13Nodeckt.dss"
        if not master_file.exists():
            pytest.skip(f"IEEE 13-node DSS file not found: {master_file}")

        # Redirect OpenDSS to the example directory
        opendssdirect.run_command(f"Redirect [{master_file}]")

        # Solve power flow
        opendssdirect.run_command("Solve")

        # Check convergence
        converged = opendssdirect.Solution.Converged()
        assert converged, "Power flow did not converge"

        # Retrieve node voltages
        voltages = opendssdirect.Circuit.AllBusVmagPu()
        assert len(voltages) > 0, "No voltage results returned"

        # Verify voltages are within reasonable range (0.8 - 1.2 pu)
        for v in voltages:
            assert 0.8 <= v <= 1.2, f"Voltage {v} pu is out of expected range"

    def test_ieee13_node_count(self) -> None:
        """Verify IEEE 13-node feeder has expected number of buses."""
        opendssdirect = pytest.importorskip("opendssdirect")

        master_file = EXAMPLES_DIR / "IEEE13Nodeckt.dss"
        if not master_file.exists():
            pytest.skip(f"IEEE 13-node DSS file not found: {master_file}")

        opendssdirect.run_command(f"Redirect [{master_file}]")
        opendssdirect.run_command("Solve")

        bus_names = opendssdirect.Circuit.AllBusNames()
        # IEEE 13-node feeder typically has 13+ buses (including source bus)
        assert len(bus_names) >= 13, f"Expected at least 13 buses, got {len(bus_names)}"
