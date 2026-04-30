"""Tests for :func:`cdl_to_dss` — §5.1.3."""

from __future__ import annotations

import pytest

from gridflow.adapter.network.cdl_to_dss import cdl_to_dss
from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology
from gridflow.domain.util.params import as_params


def _make_network(*, with_impedance: bool = False) -> CDLNetwork:
    edge_props: dict[str, object] = {}
    if with_impedance:
        edge_props = {
            "r1_ohm_per_km": 0.3,
            "x1_ohm_per_km": 0.5,
            "r0_ohm_per_km": 0.5,
            "x0_ohm_per_km": 0.7,
        }
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
                properties=as_params(edge_props),
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


class TestCDLToDSS:
    def test_emits_circuit_preamble(self) -> None:
        net = _make_network()
        script = cdl_to_dss(net)
        assert script.startswith("Clear\n")
        assert "New Circuit.CDL bus1=sourcebus" in script
        assert "basekv=12.47" in script

    def test_emits_lines_with_default_linecode_when_no_impedance(self) -> None:
        net = _make_network(with_impedance=False)
        script = cdl_to_dss(net)
        assert "New Linecode.cdl_default" in script
        # Line falls back to the default linecode when explicit r1/x1 not given.
        assert "linecode=cdl_default" in script

    def test_emits_inline_impedance_when_provided(self) -> None:
        net = _make_network(with_impedance=True)
        script = cdl_to_dss(net)
        line_cmd = next(line for line in script.splitlines() if line.startswith("New Line.line_1"))
        assert "r1=0.3" in line_cmd
        assert "x1=0.5" in line_cmd
        assert "r0=0.5" in line_cmd
        assert "x0=0.7" in line_cmd

    def test_emits_load(self) -> None:
        net = _make_network()
        script = cdl_to_dss(net)
        load_cmd = next(line for line in script.splitlines() if "New Load" in line)
        assert "bus1=loadbus" in load_cmd
        assert "kw=500.0" in load_cmd
        assert "pf=0.95" in load_cmd

    def test_emits_pv_as_generator(self) -> None:
        net = _make_network()
        script = cdl_to_dss(net)
        gen_cmd = next(line for line in script.splitlines() if "New Generator" in line)
        assert "bus1=loadbus" in gen_cmd
        assert "kw=100.0" in gen_cmd

    def test_emits_set_voltagebases_and_calcv(self) -> None:
        net = _make_network()
        script = cdl_to_dss(net)
        assert "Set voltagebases=" in script
        assert script.strip().endswith("Calcv")


class TestCDLToDSSTransformer:
    def test_transformer_when_voltage_changes(self) -> None:
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
                    properties=as_params({"kva": 5000.0, "xhl_pct": 8.0}),
                ),
            ),
            source_bus="hv",
        )
        net = CDLNetwork(topology=topo, base_voltage_kv=115.0)
        script = cdl_to_dss(net)
        tx_cmd = next(line for line in script.splitlines() if line.startswith("New Transformer.tx_1"))
        assert "kvs=[115.0 12.47]" in tx_cmd
        assert "kvas=[5000.0 5000.0]" in tx_cmd
        assert "xhl=8.0" in tx_cmd

    def test_unsupported_asset_type_becomes_comment(self) -> None:
        topo = Topology(
            topology_id="t",
            name="t",
            nodes=(Node(node_id="a", name="a", node_type="bus", voltage_kv=12.47),),
            edges=(),
            source_bus="a",
        )
        net = CDLNetwork(
            topology=topo,
            assets=(
                Asset(
                    asset_id="weird_1",
                    name="weird_1",
                    asset_type="weird_device",
                    node_id="a",
                    rated_power_kw=1.0,
                ),
            ),
        )
        script = cdl_to_dss(net)
        assert "! CDL asset 'weird_1'" in script
        assert "weird_device" in script


class TestSanitizeID:
    def test_spaces_and_dots_replaced(self) -> None:
        topo = Topology(
            topology_id="t",
            name="t",
            nodes=(
                Node(node_id="a", name="a", node_type="bus", voltage_kv=12.47),
                Node(node_id="b", name="b", node_type="bus", voltage_kv=12.47),
            ),
            edges=(
                Edge(
                    edge_id="line 1.A",
                    from_node="a",
                    to_node="b",
                    edge_type="line",
                    length_km=1.0,
                ),
            ),
            source_bus="a",
        )
        net = CDLNetwork(topology=topo)
        script = cdl_to_dss(net)
        assert "New Line.line_1_A" in script


if __name__ == "__main__":  # pragma: no cover
    pytest.main([__file__, "-v"])
