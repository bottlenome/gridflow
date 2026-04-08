"""Topology, Node, and Edge CDL domain models."""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import Params, params_to_dict


@dataclass(frozen=True)
class Node:
    """Network node.

    Attributes:
        node_id: Unique node identifier.
        name: Node name.
        node_type: Node type (e.g. "bus", "load", "generator").
        voltage_kv: Rated voltage in kV.
        coordinates: Geographic coordinates (lat, lon). None if unknown.
    """

    node_id: str
    name: str
    node_type: str
    voltage_kv: float
    coordinates: tuple[float, float] | None = None

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "node_id": self.node_id,
            "name": self.name,
            "node_type": self.node_type,
            "voltage_kv": self.voltage_kv,
            "coordinates": list(self.coordinates) if self.coordinates else None,
        }

    def validate(self) -> None:
        """Validate node attributes."""
        if not self.node_id:
            raise CDLValidationError("Node.node_id must not be empty")
        if self.voltage_kv < 0:
            raise CDLValidationError(f"Node.voltage_kv must be non-negative, got {self.voltage_kv}")


@dataclass(frozen=True)
class Edge:
    """Network edge (line or transformer).

    Attributes:
        edge_id: Unique edge identifier.
        from_node: Source node ID.
        to_node: Destination node ID.
        edge_type: Edge type (e.g. "line", "transformer").
        length_km: Line length in km. None if not applicable.
        properties: Edge-specific additional properties as a frozen
            tuple-of-tuples (see ``gridflow.domain.util.params``).
    """

    edge_id: str
    from_node: str
    to_node: str
    edge_type: str
    length_km: float | None = None
    properties: Params = ()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "edge_id": self.edge_id,
            "from_node": self.from_node,
            "to_node": self.to_node,
            "edge_type": self.edge_type,
            "length_km": self.length_km,
            "properties": params_to_dict(self.properties),
        }

    def validate(self) -> None:
        """Validate edge attributes."""
        if not self.edge_id:
            raise CDLValidationError("Edge.edge_id must not be empty")
        if not self.from_node:
            raise CDLValidationError("Edge.from_node must not be empty")
        if not self.to_node:
            raise CDLValidationError("Edge.to_node must not be empty")
        if self.length_km is not None and self.length_km < 0:
            raise CDLValidationError(f"Edge.length_km must be non-negative, got {self.length_km}")


@dataclass(frozen=True)
class Topology:
    """Network topology.

    Attributes:
        topology_id: Unique topology identifier.
        name: Topology name.
        nodes: Tuple of network nodes.
        edges: Tuple of network edges.
        source_bus: Source bus node ID.
        metadata: Topology-level metadata as a frozen tuple-of-tuples
            (see ``gridflow.domain.util.params``).
    """

    topology_id: str
    name: str
    nodes: tuple[Node, ...]
    edges: tuple[Edge, ...]
    source_bus: str
    metadata: Params = ()

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "topology_id": self.topology_id,
            "name": self.name,
            "nodes": [n.to_dict() for n in self.nodes],
            "edges": [e.to_dict() for e in self.edges],
            "source_bus": self.source_bus,
            "metadata": params_to_dict(self.metadata),
        }

    def validate(self) -> None:
        """Validate topology attributes and internal consistency."""
        if not self.topology_id:
            raise CDLValidationError("Topology.topology_id must not be empty")
        if not self.nodes:
            raise CDLValidationError("Topology must have at least one node")

        node_ids = {n.node_id for n in self.nodes}
        if self.source_bus not in node_ids:
            raise CDLValidationError(f"source_bus '{self.source_bus}' not found in nodes")

        for node in self.nodes:
            node.validate()
        for edge in self.edges:
            edge.validate()
            if edge.from_node not in node_ids:
                raise CDLValidationError(f"Edge '{edge.edge_id}' from_node '{edge.from_node}' not in nodes")
            if edge.to_node not in node_ids:
                raise CDLValidationError(f"Edge '{edge.edge_id}' to_node '{edge.to_node}' not in nodes")
