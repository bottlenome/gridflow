"""Tests for :func:`cdl_to_pandapower` — §5.1.3.

Most tests are gated behind ``pandapower`` importability so the suite
runs in CI environments where the optional extra is not installed. A
single test verifies the ``ConnectorError`` emitted when pandapower is
missing — no skip for that one.
"""

from __future__ import annotations

import pytest

from gridflow.adapter.network.cdl_to_pandapower import cdl_to_pandapower
from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology
from gridflow.domain.error import ConnectorError
from gridflow.domain.util.params import as_params

try:
    import pandapower as pp  # noqa: F401

    _HAVE_PANDAPOWER = True
except ImportError:
    _HAVE_PANDAPOWER = False


def _make_network() -> CDLNetwork:
    topo = Topology(
        topology_id="t",
        name="t",
        nodes=(
            Node(node_id="sourcebus", name="Source", node_type="source", voltage_kv=12.47),
            Node(node_id="loadbus", name="Load", node_type="load", voltage_kv=12.47),
        ),
        edges=(
            Edge(
                edge_id="line_1",
                from_node="sourcebus",
                to_node="loadbus",
                edge_type="line",
                length_km=1.0,
                properties=as_params(
                    {
                        "r1_ohm_per_km": 0.3,
                        "x1_ohm_per_km": 0.5,
                        "max_i_ka": 1.0,
                    }
                ),
            ),
        ),
        source_bus="sourcebus",
    )
    return CDLNetwork(
        topology=topo,
        assets=(
            Asset(
                asset_id="load_1",
                name="load_1",
                asset_type="load",
                node_id="loadbus",
                rated_power_kw=500.0,
                parameters=as_params({"pf": 0.95}),
            ),
            Asset(
                asset_id="pv_1",
                name="pv_1",
                asset_type="pv",
                node_id="loadbus",
                rated_power_kw=100.0,
            ),
        ),
        base_voltage_kv=12.47,
    )


@pytest.mark.skipif(_HAVE_PANDAPOWER, reason="this test only runs when pandapower is NOT installed")
class TestMissingPandapowerRaisesGracefully:
    """When pandapower is not installed, the converter emits a
    ConnectorError (never a raw ImportError). Skipped when the extra is
    present so CI with either configuration covers its own error path."""

    def test_raises_connector_error_without_pandapower(self) -> None:
        with pytest.raises(ConnectorError, match="pandapower"):
            cdl_to_pandapower(_make_network())


@pytest.mark.skipif(not _HAVE_PANDAPOWER, reason="pandapower extra not installed")
class TestWithPandapower:
    def test_builds_network_with_source_and_load(self) -> None:
        net = cdl_to_pandapower(_make_network())
        assert len(net.bus) == 2
        assert len(net.line) == 1
        assert len(net.load) == 1
        assert len(net.sgen) == 1
        assert len(net.ext_grid) == 1

    def test_runpp_converges(self) -> None:
        import pandapower as pp

        net = cdl_to_pandapower(_make_network())
        pp.runpp(net)
        # Single load + small PV → voltages near 1.0 pu, both defined.
        for vm in net.res_bus.vm_pu.tolist():
            assert 0.90 < vm < 1.10

    def test_transformer_handling(self) -> None:
        import pandapower as pp

        topo = Topology(
            topology_id="t",
            name="t",
            nodes=(
                Node(node_id="hv", name="HV", node_type="source", voltage_kv=115.0),
                Node(node_id="lv", name="LV", node_type="bus", voltage_kv=12.47),
            ),
            edges=(
                Edge(
                    edge_id="tx_1",
                    from_node="hv",
                    to_node="lv",
                    edge_type="transformer",
                    properties=as_params({"kva": 10000.0, "xhl_pct": 8.0}),
                ),
            ),
            source_bus="hv",
        )
        net = cdl_to_pandapower(CDLNetwork(topology=topo, base_voltage_kv=115.0))
        assert len(net.trafo) == 1
        pp.runpp(net)
