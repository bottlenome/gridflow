"""Tests for :class:`CDLNetwork` — §5.1.3."""

from __future__ import annotations

import pytest

from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology
from gridflow.domain.error import CDLValidationError


def _minimal_topology() -> Topology:
    return Topology(
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
            ),
        ),
        source_bus="sourcebus",
    )


class TestCDLNetwork:
    def test_basic_construction(self) -> None:
        net = CDLNetwork(
            topology=_minimal_topology(),
            assets=(
                Asset(
                    asset_id="load_1",
                    name="load_1",
                    asset_type="load",
                    node_id="loadbus",
                    rated_power_kw=500.0,
                ),
            ),
            base_voltage_kv=12.47,
        )
        assert net.base_voltage_kv == 12.47
        assert len(net.assets) == 1

    def test_is_frozen(self) -> None:
        net = CDLNetwork(topology=_minimal_topology())
        with pytest.raises((AttributeError, Exception)):
            net.base_voltage_kv = 99.0  # type: ignore[misc]

    def test_asset_references_unknown_node_rejected(self) -> None:
        with pytest.raises(CDLValidationError, match="unknown node"):
            CDLNetwork(
                topology=_minimal_topology(),
                assets=(
                    Asset(
                        asset_id="load_1",
                        name="load_1",
                        asset_type="load",
                        node_id="ghost_bus",
                        rated_power_kw=100.0,
                    ),
                ),
            )

    def test_non_positive_base_voltage_rejected(self) -> None:
        with pytest.raises(CDLValidationError, match="base_voltage_kv"):
            CDLNetwork(topology=_minimal_topology(), base_voltage_kv=0.0)

    def test_to_dict_roundtrip_shape(self) -> None:
        net = CDLNetwork(
            topology=_minimal_topology(),
            assets=(
                Asset(
                    asset_id="load_1",
                    name="load_1",
                    asset_type="load",
                    node_id="loadbus",
                    rated_power_kw=500.0,
                ),
            ),
        )
        d = net.to_dict()
        assert d["base_voltage_kv"] == 12.47
        assert isinstance(d["topology"], dict)
        assert isinstance(d["assets"], list)
        assert len(d["assets"]) == 1
