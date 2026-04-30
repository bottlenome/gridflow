"""Cross-solver integration test — same CDL network, two connectors.

§5.1.3 DoD: a pack referencing a CDL YAML via ``cdl_network_file`` is
initialisable by both the OpenDSS and pandapower connectors. We test
the pandapower path (skipped when pandapower is unavailable) and the
non-driver portion of the OpenDSS path (CDL script compilation) — the
opendssdirect-backed solver is covered by the existing spike / E2E
suites.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.adapter.connector.opendss import OpenDSSConnector
from gridflow.adapter.connector.pandapower import PandaPowerConnector
from gridflow.domain.scenario import PackMetadata, ScenarioPack
from gridflow.domain.util.params import as_params

try:
    import pandapower  # noqa: F401

    _HAVE_PANDAPOWER = True
except ImportError:
    _HAVE_PANDAPOWER = False


_CDL_YAML_TEXT = """
network:
  base_voltage_kv: 12.47
  base_frequency_hz: 60.0
  source_bus: sourcebus

nodes:
  - id: sourcebus
    voltage_kv: 12.47
  - id: loadbus
    voltage_kv: 12.47

edges:
  - id: line_1
    from: sourcebus
    to: loadbus
    edge_type: line
    length_km: 1.0
    properties:
      r1_ohm_per_km: 0.3
      x1_ohm_per_km: 0.5
      max_i_ka: 1.0

assets:
  - id: load_1
    asset_type: load
    node_id: loadbus
    rated_power_kw: 500.0
    parameters:
      pf: 0.95
"""


def _make_cdl_pack(tmp_path: Path) -> ScenarioPack:
    """Build a ScenarioPack whose network_dir contains a CDL YAML."""
    network_dir = tmp_path / "network"
    network_dir.mkdir()
    (network_dir / "net.yaml").write_text(_CDL_YAML_TEXT, encoding="utf-8")
    meta = PackMetadata(
        name="cdl_cross_solver",
        version="1.0.0",
        description="cross-solver smoke",
        author="test",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
        parameters=as_params({"cdl_network_file": "net.yaml"}),
    )
    return ScenarioPack(
        pack_id="cdl_cross_solver@1.0.0",
        name="cdl_cross_solver",
        version="1.0.0",
        metadata=meta,
        network_dir=network_dir,
        timeseries_dir=tmp_path,
        config_dir=tmp_path,
    )


class TestOpenDSSCDLCompilation:
    """OpenDSS CDL path without opendssdirect — drive the pure compile step."""

    def test_compile_cdl_script_produces_dss_lines(self, tmp_path: Path) -> None:
        pack = _make_cdl_pack(tmp_path)
        script = OpenDSSConnector._compile_cdl_script(pack, "net.yaml")
        # Sanity: the produced script has the canonical DSS backbone.
        assert "Clear" in script
        assert "New Circuit." in script
        assert "bus1=sourcebus" in script
        assert "New Line.line_1" in script
        assert "New Load.load_1" in script
        assert "Calcv" in script

    def test_compile_cdl_script_resolves_absolute_paths(self, tmp_path: Path) -> None:
        pack = _make_cdl_pack(tmp_path)
        # Absolute path should bypass the network_dir prefix.
        abs_path = pack.network_dir / "net.yaml"
        script = OpenDSSConnector._compile_cdl_script(pack, str(abs_path))
        assert "New Circuit." in script


@pytest.mark.skipif(not _HAVE_PANDAPOWER, reason="pandapower extra not installed")
class TestPandaPowerCDLInitialize:
    """End-to-end initialize() + step() via CDL input (pandapower branch)."""

    def test_initialize_and_step_produce_voltages(self, tmp_path: Path) -> None:
        pack = _make_cdl_pack(tmp_path)
        connector = PandaPowerConnector()
        connector.initialize(pack)
        out = connector.step(step_index=0)
        # Two buses → two voltages. Both should be near 1.0 pu.
        assert len(out.node_result.voltages) == 2
        for v in out.node_result.voltages:
            assert 0.85 < v < 1.10
        connector.teardown()
