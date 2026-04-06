"""Tests for Topology, Node, and Edge CDL models."""

import pytest

from gridflow.domain.cdl import Edge, Node, Topology
from gridflow.domain.error import CDLValidationError


class TestNode:
    def test_create_node(self) -> None:
        node = Node(node_id="650", name="Bus 650", node_type="bus", voltage_kv=4.16)
        assert node.node_id == "650"
        assert node.coordinates is None

    def test_node_with_coordinates(self) -> None:
        node = Node(node_id="650", name="Bus 650", node_type="bus", voltage_kv=4.16, coordinates=(35.0, -80.0))
        assert node.coordinates == (35.0, -80.0)

    def test_node_to_dict(self) -> None:
        node = Node(node_id="650", name="Bus 650", node_type="bus", voltage_kv=4.16)
        d = node.to_dict()
        assert d["node_id"] == "650"
        assert d["voltage_kv"] == 4.16

    def test_node_validate_empty_id(self) -> None:
        node = Node(node_id="", name="Bus", node_type="bus", voltage_kv=4.16)
        with pytest.raises(CDLValidationError, match="node_id"):
            node.validate()

    def test_node_validate_negative_voltage(self) -> None:
        node = Node(node_id="650", name="Bus", node_type="bus", voltage_kv=-1.0)
        with pytest.raises(CDLValidationError, match="voltage_kv"):
            node.validate()


class TestEdge:
    def test_create_edge(self) -> None:
        edge = Edge(edge_id="650-632", from_node="650", to_node="632", edge_type="line", length_km=0.6)
        assert edge.length_km == 0.6

    def test_edge_validate_negative_length(self) -> None:
        edge = Edge(edge_id="650-632", from_node="650", to_node="632", edge_type="line", length_km=-1.0)
        with pytest.raises(CDLValidationError, match="length_km"):
            edge.validate()


class TestTopology:
    def _make_topology(self) -> Topology:
        nodes = (
            Node(node_id="650", name="Bus 650", node_type="bus", voltage_kv=4.16),
            Node(node_id="632", name="Bus 632", node_type="bus", voltage_kv=4.16),
        )
        edges = (Edge(edge_id="650-632", from_node="650", to_node="632", edge_type="line", length_km=0.6),)
        return Topology(topology_id="topo-1", name="Test", nodes=nodes, edges=edges, source_bus="650")

    def test_create_topology(self) -> None:
        topo = self._make_topology()
        assert topo.topology_id == "topo-1"
        assert len(topo.nodes) == 2
        assert len(topo.edges) == 1

    def test_topology_validate_success(self) -> None:
        topo = self._make_topology()
        topo.validate()

    def test_topology_validate_missing_source_bus(self) -> None:
        nodes = (Node(node_id="650", name="Bus 650", node_type="bus", voltage_kv=4.16),)
        topo = Topology(topology_id="t", name="T", nodes=nodes, edges=(), source_bus="999")
        with pytest.raises(CDLValidationError, match="source_bus"):
            topo.validate()

    def test_topology_to_dict(self) -> None:
        topo = self._make_topology()
        d = topo.to_dict()
        assert d["topology_id"] == "topo-1"
        assert len(d["nodes"]) == 2  # type: ignore[arg-type]
