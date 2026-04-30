"""OpenDSSTranslator — bidirectional CDL ⇔ OpenDSS adapter.

Spec: ``docs/detailed_design/03b_usecase_classes.md`` §3.5.4a.

Two directions, two scopes:

* :meth:`from_canonical` — :class:`CDLNetwork` → OpenDSS command script
  string. Pure (does not touch a live driver) so it can run in any
  environment and be unit-tested without ``opendssdirect``. Used by
  :class:`OpenDSSConnector` to materialise a CDL pack into the engine
  during ``initialize``.
* :meth:`to_canonical` — *live* OpenDSS driver → :class:`CDLNetwork`.
  Requires a live driver bound to the instance. Used by post-solve
  reporting paths and (in the long run) by cross-solver verification
  workflows that round-trip CDL → OpenDSS → CDL.

The pre-existing :meth:`topology` / :meth:`voltages_pu` methods are
kept (they predate the bidirectional design) and are now thin wrappers
over the same internal collectors.

Phase 2 §5.1.3 places this module at
``gridflow.adapter.connector.opendss_translator`` and the spec mirror
``gridflow.adapter.connector.pandapower_translator`` is the
pandapower side.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology

if TYPE_CHECKING:
    from types import ModuleType


@dataclass(frozen=True)
class _BusSnapshot:
    """Minimal capture of a bus name + nominal voltage."""

    name: str
    voltage_kv: float


class OpenDSSTranslator:
    """Bidirectional CDL ⇔ OpenDSS translator.

    Stateful only insofar as the live ``driver`` is required for
    :meth:`to_canonical` / :meth:`topology` / :meth:`voltages_pu`.
    :meth:`from_canonical` is a classmethod-style pure conversion and
    does not need a driver instance.
    """

    def __init__(self, driver: ModuleType | Any | None = None) -> None:
        self._driver = driver

    # ----------------------------------------------------------------- from_canonical (CDL → DSS)

    @staticmethod
    def from_canonical(network: CDLNetwork, *, circuit_name: str = "CDL") -> str:
        """Render ``network`` as a complete OpenDSS command script.

        Pure (no live driver required) — the caller feeds the returned
        string to ``opendssdirect.Command(...)`` line by line, or
        writes it to disk and ``Redirect``s to it.
        """
        from gridflow.adapter.network.cdl_to_dss import cdl_to_dss

        return cdl_to_dss(network, circuit_name=circuit_name)

    # ----------------------------------------------------------------- to_canonical (DSS → CDL)

    def to_canonical(
        self,
        *,
        topology_id: str = "opendss_canonical",
        name: str = "opendss_canonical",
        source_bus: str | None = None,
    ) -> CDLNetwork:
        """Build a :class:`CDLNetwork` from the live OpenDSS circuit.

        Args:
            topology_id: Identifier for the resulting Topology.
            name: Topology name.
            source_bus: Override the source bus. If ``None``, the first
                bus reported by the driver is used (matches OpenDSS's
                own ``Vsource.source`` convention for an unmodified
                circuit).

        Raises:
            RuntimeError: If no driver was bound at construction.
        """
        if self._driver is None:
            raise RuntimeError(
                "OpenDSSTranslator.to_canonical requires a live driver — "
                "construct OpenDSSTranslator(driver=...) before calling."
            )
        buses = self._collect_buses()
        if not buses:
            raise RuntimeError("OpenDSS circuit has no buses; nothing to canonicalise")
        nodes = tuple(
            Node(node_id=bus.name, name=bus.name, node_type="bus", voltage_kv=bus.voltage_kv) for bus in buses
        )
        edges = tuple(self._collect_edges())
        topology = Topology(
            topology_id=topology_id,
            name=name,
            nodes=nodes,
            edges=edges,
            source_bus=source_bus or buses[0].name,
        )
        # Asset extraction is intentionally minimal at the MVP level —
        # OpenDSSDirect surfaces loads / generators via separate APIs
        # and the translator stays focused on the topology + line set.
        # Downstream callers that need explicit asset round-trip should
        # extend this loop with ``driver.Loads`` / ``driver.Generators``.
        assets: tuple[Asset, ...] = ()
        # Pick a sensible default base voltage from the source bus.
        base_voltage_kv = buses[0].voltage_kv if buses[0].voltage_kv > 0 else 1.0
        return CDLNetwork(topology=topology, assets=assets, base_voltage_kv=base_voltage_kv)

    # ----------------------------------------------------------------- live snapshots

    def topology(self, *, topology_id: str, name: str, source_bus: str) -> Topology:
        """Build a :class:`Topology` from the current OpenDSS circuit.

        Kept for backward compatibility with the Phase 1 reporting path;
        :meth:`to_canonical` is the preferred entry point for new code.
        """
        if self._driver is None:
            raise RuntimeError("OpenDSSTranslator.topology requires a live driver")
        buses = self._collect_buses()
        nodes = tuple(
            Node(node_id=bus.name, name=bus.name, node_type="bus", voltage_kv=bus.voltage_kv) for bus in buses
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
        if self._driver is None:
            raise RuntimeError("OpenDSSTranslator.voltages_pu requires a live driver")
        names = list(self._driver.Circuit.AllBusNames())
        mags = list(self._driver.Circuit.AllBusMagPu())
        return dict(zip(names, mags, strict=False))

    # ----------------------------------------------------------------- internals

    def _require_driver(self) -> Any:
        """Type-narrow ``self._driver`` from ``ModuleType | Any | None`` to non-``None``.

        The collectors below all run after a ``to_canonical`` /
        ``topology`` / ``voltages_pu`` entry-point check that already
        rejected ``None``, but mypy --strict can't see across method
        boundaries; this helper keeps the entry-point checks unique
        without sprinkling ``assert`` statements through the
        collectors.
        """
        if self._driver is None:
            raise RuntimeError("OpenDSSTranslator: driver is required for live-state methods")
        return self._driver

    def _collect_buses(self) -> list[_BusSnapshot]:
        driver = self._require_driver()
        snapshots: list[_BusSnapshot] = []
        for bus_name in driver.Circuit.AllBusNames():
            driver.Circuit.SetActiveBus(bus_name)
            kv_base = 0.0
            try:
                kv_base = float(driver.Bus.kVBase())
            except Exception:  # pragma: no cover - defensive
                kv_base = 0.0
            snapshots.append(_BusSnapshot(name=bus_name, voltage_kv=kv_base))
        return snapshots

    def _collect_edges(self) -> list[Edge]:
        driver = self._require_driver()
        edges: list[Edge] = []
        try:
            names = list(driver.Lines.AllNames())
        except Exception:  # pragma: no cover - older driver shims
            names = []
        for line_name in names:
            driver.Lines.Name(line_name)
            from_bus = self._bus_without_phase(driver.Lines.Bus1())
            to_bus = self._bus_without_phase(driver.Lines.Bus2())
            length = None
            try:
                length = float(driver.Lines.Length())
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
