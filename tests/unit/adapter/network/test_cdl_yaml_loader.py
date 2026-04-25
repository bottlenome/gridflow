"""Tests for the CDLNetwork YAML loader — §5.1.3."""

from __future__ import annotations

from pathlib import Path

import pytest

from gridflow.adapter.network.cdl_yaml_loader import (
    CDLNetworkLoadError,
    load_cdl_network_from_dict,
    load_cdl_network_from_yaml,
)


class TestLoadFromDict:
    def test_minimal_two_bus_network(self) -> None:
        net = load_cdl_network_from_dict(
            {
                "network": {
                    "base_voltage_kv": 12.47,
                    "source_bus": "sourcebus",
                },
                "nodes": [
                    {"id": "sourcebus", "voltage_kv": 12.47, "node_type": "source"},
                    {"id": "loadbus", "voltage_kv": 12.47, "node_type": "load"},
                ],
                "edges": [
                    {
                        "id": "line_1",
                        "from": "sourcebus",
                        "to": "loadbus",
                        "length_km": 1.0,
                    },
                ],
                "assets": [
                    {
                        "id": "load_1",
                        "asset_type": "load",
                        "node_id": "loadbus",
                        "rated_power_kw": 500.0,
                        "parameters": {"pf": 0.95},
                    },
                ],
            }
        )
        assert net.base_voltage_kv == 12.47
        assert net.topology.source_bus == "sourcebus"
        assert len(net.topology.nodes) == 2
        assert len(net.topology.edges) == 1
        assert len(net.assets) == 1
        assert dict(net.assets[0].parameters) == {"pf": 0.95}

    def test_defaults_source_bus_to_first_node(self) -> None:
        net = load_cdl_network_from_dict(
            {
                "nodes": [
                    {"id": "busA", "voltage_kv": 12.47},
                    {"id": "busB", "voltage_kv": 12.47},
                ],
            }
        )
        assert net.topology.source_bus == "busA"

    def test_edge_properties_preserved(self) -> None:
        net = load_cdl_network_from_dict(
            {
                "nodes": [
                    {"id": "a", "voltage_kv": 12.47},
                    {"id": "b", "voltage_kv": 12.47},
                ],
                "edges": [
                    {
                        "id": "e1",
                        "from": "a",
                        "to": "b",
                        "length_km": 2.0,
                        "properties": {
                            "r1_ohm_per_km": 0.3,
                            "x1_ohm_per_km": 0.5,
                        },
                    },
                ],
            }
        )
        edge = net.topology.edges[0]
        assert dict(edge.properties) == {
            "r1_ohm_per_km": 0.3,
            "x1_ohm_per_km": 0.5,
        }

    def test_missing_nodes_rejected(self) -> None:
        with pytest.raises(CDLNetworkLoadError, match="nodes"):
            load_cdl_network_from_dict({})

    def test_node_missing_voltage_rejected(self) -> None:
        with pytest.raises(CDLNetworkLoadError, match="voltage_kv"):
            load_cdl_network_from_dict({"nodes": [{"id": "x"}]})

    def test_asset_unknown_node_rejected(self) -> None:
        with pytest.raises(CDLNetworkLoadError, match="unknown node"):
            load_cdl_network_from_dict(
                {
                    "nodes": [{"id": "a", "voltage_kv": 12.47}],
                    "assets": [
                        {
                            "id": "l1",
                            "asset_type": "load",
                            "node_id": "b",
                            "rated_power_kw": 100.0,
                        },
                    ],
                }
            )


class TestLoadFromYAMLFile:
    def test_loads_real_file(self, tmp_path: Path) -> None:
        path = tmp_path / "net.yaml"
        path.write_text(
            """
network:
  base_voltage_kv: 12.47
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
    length_km: 1.0
""",
            encoding="utf-8",
        )
        net = load_cdl_network_from_yaml(path)
        assert net.topology.source_bus == "sourcebus"

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(CDLNetworkLoadError, match="not found"):
            load_cdl_network_from_yaml(tmp_path / "nope.yaml")
