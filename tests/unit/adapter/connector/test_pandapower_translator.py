"""Tests for :class:`PandapowerTranslator` (M6 / DD-CLS-059 / 03b §3.5.4a).

Most tests are gated on pandapower availability.
"""

from __future__ import annotations

import pytest

from gridflow.adapter.connector.pandapower_translator import PandapowerTranslator
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
                properties=as_params({"r1_ohm_per_km": 0.3, "x1_ohm_per_km": 0.5, "max_i_ka": 1.0}),
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
class TestMissingPandapower:
    def test_to_canonical_raises_connector_error(self) -> None:
        # Build a fake "net" — to_canonical must reject before touching it.
        with pytest.raises(ConnectorError, match="pandapower"):
            PandapowerTranslator.to_canonical(net=object())


@pytest.mark.skipif(not _HAVE_PANDAPOWER, reason="pandapower extra not installed")
class TestRoundTripWithPandapower:
    def test_from_canonical_to_canonical_round_trip(self) -> None:
        original = _make_network()
        net = PandapowerTranslator.from_canonical(original)
        canon = PandapowerTranslator.to_canonical(net)

        # Topology size matches the original (same number of buses / edges).
        assert len(canon.topology.nodes) == len(original.topology.nodes)
        assert len(canon.topology.edges) == len(original.topology.edges)
        # Source bus index is canonicalised to "bus_<idx>" — verify it
        # points at a valid node, not the original string id.
        assert canon.topology.source_bus.startswith("bus_")
        assert canon.topology.source_bus in {n.node_id for n in canon.topology.nodes}
        # Edge length / impedance survives the round trip.
        edge = canon.topology.edges[0]
        assert edge.length_km == pytest.approx(1.0)
        edge_props = dict(edge.properties)
        assert edge_props["r1_ohm_per_km"] == pytest.approx(0.3)
        assert edge_props["x1_ohm_per_km"] == pytest.approx(0.5)
        # Asset survives — load and sgen present.
        asset_types = {a.asset_type for a in canon.assets}
        assert "load" in asset_types
        # PV may be canonicalised as "pv" (matching the from_canonical's
        # ``type="PV"`` write-back).
        assert "pv" in asset_types or "generator" in asset_types

    def test_load_pf_recovered_from_q_mvar(self) -> None:
        net = PandapowerTranslator.from_canonical(_make_network())
        canon = PandapowerTranslator.to_canonical(net)
        load = next(a for a in canon.assets if a.asset_type == "load")
        # pf should be near the 0.95 we asked for (small rounding error from
        # the kw / q_mvar derivation is expected).
        params = dict(load.parameters)
        assert "pf" in params
        assert float(params["pf"]) == pytest.approx(0.95, abs=0.01)

    def test_explicit_source_bus_index_override(self) -> None:
        net = PandapowerTranslator.from_canonical(_make_network())
        # The default ext_grid is on bus 0; flipping to bus 1 must update
        # source_bus while leaving the topology shape untouched.
        canon = PandapowerTranslator.to_canonical(net, source_bus_index=1)
        assert canon.topology.source_bus == "bus_1"
