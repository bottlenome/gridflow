"""Translate OpenDSS circuit state into CDL-flavoured Domain models.

Only the subset needed for MVP reporting is implemented. The translator is
deliberately separate from :class:`OpenDSSConnector` so the raw solver surface
stays thin and the shape-change logic lives in one place.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gridflow.domain.cdl import Edge, Node, Topology

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(frozen=True)
class _BusSnapshot:
    """Minimal capture of a bus name + nominal voltage."""

    name: str
    voltage_kv: float


class OpenDSSTranslator:
    """Pull ``Topology`` / voltage data out of an active OpenDSS instance."""

    def __init__(self, driver: ModuleType | Any) -> None:
        self._driver = driver

    # ----------------------------------------------------------------- snapshots

    def topology(self, *, topology_id: str, name: str, source_bus: str) -> Topology:
        """Build a :class:`Topology` from the current OpenDSS circuit."""
        buses = self._collect_buses()
        nodes = tuple(
            Node(
                node_id=bus.name,
                name=bus.name,
                node_type="bus",
                voltage_kv=bus.voltage_kv,
            )
            for bus in buses
        )
        edges = tuple(self._collect_edges())
        return Topology(
            topology_id=topology_id,
            name=name,
            nodes=nodes,
            edges=edges,
            source_bus=source_bus,
        )

    def voltages_pu(self) -> dict[str, float]:
        """Return the current per-unit bus voltages keyed by bus name."""
        names = list(self._driver.Circuit.AllBusNames())
        mags = list(self._driver.Circuit.AllBusMagPu())
        return dict(zip(names, mags, strict=False))

    # ----------------------------------------------------------------- internals

    def _collect_buses(self) -> list[_BusSnapshot]:
        snapshots: list[_BusSnapshot] = []
        for bus_name in self._driver.Circuit.AllBusNames():
            self._driver.Circuit.SetActiveBus(bus_name)
            kv_base = 0.0
            try:
                kv_base = float(self._driver.Bus.kVBase())
            except Exception:  # pragma: no cover - defensive
                kv_base = 0.0
            snapshots.append(_BusSnapshot(name=bus_name, voltage_kv=kv_base))
        return snapshots

    def _collect_edges(self) -> list[Edge]:
        edges: list[Edge] = []
        try:
            names = list(self._driver.Lines.AllNames())
        except Exception:  # pragma: no cover - older driver shims
            names = []
        for line_name in names:
            self._driver.Lines.Name(line_name)
            from_bus = self._bus_without_phase(self._driver.Lines.Bus1())
            to_bus = self._bus_without_phase(self._driver.Lines.Bus2())
            length = None
            try:
                length = float(self._driver.Lines.Length())
            except Exception:  # pragma: no cover - defensive
                length = None
            edges.append(
                Edge(
                    edge_id=line_name,
                    from_node=from_bus,
                    to_node=to_bus,
                    edge_type="line",
                    length_km=length,
                )
            )
        return edges

    @staticmethod
    def _bus_without_phase(name: str) -> str:
        return name.split(".", 1)[0] if name else name
