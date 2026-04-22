"""YAML loader for :class:`CDLNetwork` — the canonical network format.

Spec: ``docs/phase1_result.md`` §5.1.3.

YAML schema (``network.yaml``):

.. code-block:: yaml

    network:
      base_voltage_kv: 12.47
      base_frequency_hz: 60.0
      source_bus: sourcebus

    nodes:
      - id: sourcebus
        name: Source
        node_type: source
        voltage_kv: 12.47
      - id: loadbus
        name: Load
        node_type: load
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
          r0_ohm_per_km: 0.5
          x0_ohm_per_km: 0.7

    assets:
      - id: load_1
        name: LoadA
        asset_type: load
        node_id: loadbus
        rated_power_kw: 500.0
        parameters:
          pf: 0.95
      - id: pv_1
        name: RooftopPV
        asset_type: pv
        node_id: loadbus
        rated_power_kw: 100.0

The loader is deliberately permissive about which fields are required
at the CDL layer — solver-specific defaults (e.g. load power factor)
are applied by the converters themselves rather than the loader.
"""

from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from typing import Any

import yaml

from gridflow.domain.cdl import CDLNetwork
from gridflow.domain.cdl.asset import Asset
from gridflow.domain.cdl.topology import Edge, Node, Topology
from gridflow.domain.util.params import as_params


class CDLNetworkLoadError(ValueError):
    """Raised when CDL network YAML / dict input is malformed."""


def load_cdl_network_from_yaml(path: Path) -> CDLNetwork:
    """Parse ``path`` as a CDL network YAML and build a :class:`CDLNetwork`."""
    if not path.exists():
        raise CDLNetworkLoadError(f"CDL network file not found: {path}")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
    except yaml.YAMLError as exc:
        raise CDLNetworkLoadError(f"malformed YAML in {path}: {exc}") from exc
    if not isinstance(raw, dict):
        raise CDLNetworkLoadError(f"{path}: CDL network top-level must be a mapping, got {type(raw).__name__}")
    return load_cdl_network_from_dict(raw, topology_id=path.stem)


def load_cdl_network_from_dict(
    data: Mapping[str, Any],
    *,
    topology_id: str = "cdl_network",
) -> CDLNetwork:
    """Build a :class:`CDLNetwork` from a parsed dict."""
    net_section = data.get("network") or {}
    if not isinstance(net_section, Mapping):
        raise CDLNetworkLoadError(f"'network' must be a mapping, got {type(net_section).__name__}")

    nodes_section = data.get("nodes")
    if not isinstance(nodes_section, list) or not nodes_section:
        raise CDLNetworkLoadError("'nodes' is required and must be a non-empty list")

    edges_section = data.get("edges") or []
    if not isinstance(edges_section, list):
        raise CDLNetworkLoadError(f"'edges' must be a list, got {type(edges_section).__name__}")

    assets_section = data.get("assets") or []
    if not isinstance(assets_section, list):
        raise CDLNetworkLoadError(f"'assets' must be a list, got {type(assets_section).__name__}")

    nodes = tuple(_parse_node(n, idx) for idx, n in enumerate(nodes_section))
    edges = tuple(_parse_edge(e, idx) for idx, e in enumerate(edges_section))
    assets = tuple(_parse_asset(a, idx) for idx, a in enumerate(assets_section))

    source_bus = net_section.get("source_bus")
    if not isinstance(source_bus, str):
        # Default to the first node if unspecified — a permissive choice
        # for minimal pack.yaml files. Explicit is better, but rejecting
        # would make simple examples verbose.
        source_bus = nodes[0].node_id

    base_voltage_kv = float(net_section.get("base_voltage_kv", nodes[0].voltage_kv))
    base_frequency_hz = float(net_section.get("base_frequency_hz", 60.0))

    topology = Topology(
        topology_id=topology_id,
        name=str(net_section.get("name", topology_id)),
        nodes=nodes,
        edges=edges,
        source_bus=source_bus,
    )
    try:
        return CDLNetwork(
            topology=topology,
            assets=assets,
            base_voltage_kv=base_voltage_kv,
            base_frequency_hz=base_frequency_hz,
        )
    except Exception as exc:
        # Wrap any validation error in the loader's error type so
        # callers can catch a single ``CDLNetworkLoadError``.
        raise CDLNetworkLoadError(f"invalid CDLNetwork: {exc}") from exc


# ----------------------------------------------------------------- parsers


def _parse_node(raw: object, index: int) -> Node:
    if not isinstance(raw, Mapping):
        raise CDLNetworkLoadError(f"nodes[{index}] must be a mapping, got {type(raw).__name__}")
    node_id = _require_str(raw, "id", f"nodes[{index}]")
    return Node(
        node_id=node_id,
        name=str(raw.get("name", node_id)),
        node_type=str(raw.get("node_type", "bus")),
        voltage_kv=float(_require_field(raw, "voltage_kv", f"nodes[{index}]")),
    )


def _parse_edge(raw: object, index: int) -> Edge:
    if not isinstance(raw, Mapping):
        raise CDLNetworkLoadError(f"edges[{index}] must be a mapping, got {type(raw).__name__}")
    edge_id = _require_str(raw, "id", f"edges[{index}]")
    from_node = _require_str(raw, "from", f"edges[{index}]")
    to_node = _require_str(raw, "to", f"edges[{index}]")
    properties_raw = raw.get("properties") or {}
    if not isinstance(properties_raw, Mapping):
        raise CDLNetworkLoadError(f"edges[{index}].properties must be a mapping, got {type(properties_raw).__name__}")
    length_km_raw = raw.get("length_km")
    return Edge(
        edge_id=edge_id,
        from_node=from_node,
        to_node=to_node,
        edge_type=str(raw.get("edge_type", "line")),
        length_km=float(length_km_raw) if length_km_raw is not None else None,
        properties=as_params(properties_raw),
    )


def _parse_asset(raw: object, index: int) -> Asset:
    if not isinstance(raw, Mapping):
        raise CDLNetworkLoadError(f"assets[{index}] must be a mapping, got {type(raw).__name__}")
    asset_id = _require_str(raw, "id", f"assets[{index}]")
    parameters_raw = raw.get("parameters") or {}
    if not isinstance(parameters_raw, Mapping):
        raise CDLNetworkLoadError(f"assets[{index}].parameters must be a mapping, got {type(parameters_raw).__name__}")
    return Asset(
        asset_id=asset_id,
        name=str(raw.get("name", asset_id)),
        asset_type=str(_require_field(raw, "asset_type", f"assets[{index}]")),
        node_id=_require_str(raw, "node_id", f"assets[{index}]"),
        rated_power_kw=float(_require_field(raw, "rated_power_kw", f"assets[{index}]")),
        parameters=as_params(parameters_raw),
    )


def _require_field(d: Mapping[str, Any], key: str, ctx: str) -> Any:
    if key not in d:
        raise CDLNetworkLoadError(f"{ctx}: missing required field '{key}'")
    return d[key]


def _require_str(d: Mapping[str, Any], key: str, ctx: str) -> str:
    value = _require_field(d, key, ctx)
    if not isinstance(value, str):
        raise CDLNetworkLoadError(f"{ctx}.{key}: expected str, got {type(value).__name__}")
    if not value:
        raise CDLNetworkLoadError(f"{ctx}.{key}: must not be empty")
    return value
