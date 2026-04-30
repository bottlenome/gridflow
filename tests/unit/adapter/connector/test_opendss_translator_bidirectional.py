"""Tests for the OpenDSSTranslator bidirectional surface (M6 / 03b §3.5.4a).

The pre-existing live-driver tests live in
``tests/unit/adapter/test_opendss_connector.py`` and run only with the
``[opendss]`` extra. These tests cover the **driver-free** branches:
``from_canonical`` (CDLNetwork → script string) and the dispatch
logic on ``to_canonical`` / ``topology`` when no driver is bound.
"""

from __future__ import annotations

import pytest

from gridflow.adapter.connector.opendss_translator import OpenDSSTranslator
from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology


def _make_network() -> CDLNetwork:
    topo = Topology(
        topology_id="t",
        name="t",
        nodes=(
            Node(node_id="sourcebus", name="Source", node_type="source", voltage_kv=12.47),
            Node(node_id="loadbus", name="Load", node_type="bus", voltage_kv=12.47),
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
    return CDLNetwork(
        topology=topo,
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


class TestFromCanonical:
    def test_pure_no_driver_required(self) -> None:
        # Pure path — should not raise even without a driver argument.
        script = OpenDSSTranslator.from_canonical(_make_network(), circuit_name="MyCircuit")
        assert "Clear" in script
        assert "New Circuit.MyCircuit" in script
        assert "New Line.line_1" in script
        assert "New Load.load_1" in script

    def test_default_circuit_name_is_cdl(self) -> None:
        script = OpenDSSTranslator.from_canonical(_make_network())
        assert "New Circuit.CDL" in script


class TestNoDriverRejection:
    def test_to_canonical_without_driver_raises(self) -> None:
        translator = OpenDSSTranslator()
        with pytest.raises(RuntimeError, match="requires a live driver"):
            translator.to_canonical()

    def test_topology_without_driver_raises(self) -> None:
        translator = OpenDSSTranslator()
        with pytest.raises(RuntimeError, match="requires a live driver"):
            translator.topology(topology_id="t", name="t", source_bus="x")

    def test_voltages_pu_without_driver_raises(self) -> None:
        translator = OpenDSSTranslator()
        with pytest.raises(RuntimeError, match="requires a live driver"):
            translator.voltages_pu()


class _FakeDriver:
    """Minimal stand-in for OpenDSSDirect — exposes only the surface
    the translator's collectors actually call."""

    class _Bus:
        def __init__(self, kv: float) -> None:
            self._kv = kv

        def kVBase(self) -> float:
            return self._kv

    class _Lines:
        def __init__(self, edges: list[tuple[str, str, str, float]]) -> None:
            self._edges = edges
            self._idx = 0

        def AllNames(self) -> list[str]:
            return [e[0] for e in self._edges]

        def Name(self, n: str) -> None:
            for i, e in enumerate(self._edges):
                if e[0] == n:
                    self._idx = i
                    return

        def Bus1(self) -> str:
            return self._edges[self._idx][1]

        def Bus2(self) -> str:
            return self._edges[self._idx][2]

        def Length(self) -> float:
            return self._edges[self._idx][3]

    class _Circuit:
        def __init__(self, parent: _FakeDriver) -> None:
            self._parent = parent
            self._active_bus: str = ""

        def AllBusNames(self) -> list[str]:
            return list(self._parent._buses.keys())

        def AllBusMagPu(self) -> list[float]:
            return list(self._parent._voltages.values())

        def SetActiveBus(self, name: str) -> None:
            self._active_bus = name
            self._parent.Bus = _FakeDriver._Bus(self._parent._buses[name])

    def __init__(self, buses: dict[str, float], voltages: dict[str, float], edges: list[tuple]) -> None:
        self._buses = buses
        self._voltages = voltages
        self.Lines = _FakeDriver._Lines(edges)
        self.Circuit = _FakeDriver._Circuit(self)
        # ``Bus`` is mutated by SetActiveBus.
        self.Bus = _FakeDriver._Bus(0.0)


class TestToCanonical:
    def test_round_trip_against_fake_driver(self) -> None:
        driver = _FakeDriver(
            buses={"sourcebus": 12.47, "loadbus": 12.47},
            voltages={"sourcebus": 1.0, "loadbus": 0.97},
            edges=[("line_1", "sourcebus", "loadbus", 1.0)],
        )
        translator = OpenDSSTranslator(driver=driver)
        net = translator.to_canonical()
        assert net.base_voltage_kv == 12.47
        assert {n.node_id for n in net.topology.nodes} == {"sourcebus", "loadbus"}
        assert net.topology.source_bus == "sourcebus"
        assert net.topology.edges[0].edge_id == "line_1"

    def test_explicit_source_bus_override(self) -> None:
        driver = _FakeDriver(
            buses={"a": 1.0, "b": 1.0},
            voltages={"a": 1.0, "b": 1.0},
            edges=[],
        )
        translator = OpenDSSTranslator(driver=driver)
        net = translator.to_canonical(source_bus="b")
        assert net.topology.source_bus == "b"
