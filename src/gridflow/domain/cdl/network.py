"""CDL canonical network — solver-agnostic power system description.

Spec: ``docs/phase1_result.md`` §5.1.3 (REQ-F-003 input-side extension).

The :class:`CDLNetwork` bundles a :class:`Topology` with a tuple of
:class:`Asset` objects into a single immutable value that *any* solver
connector can consume. Adapter-layer converters (``cdl_to_dss``,
``cdl_to_pandapower``) translate this canonical form into the
solver-native inputs.

This is the foundation for cross-solver validation (MVP try6 confound):
running the *same* CDLNetwork through OpenDSSConnector *and*
PandaPowerConnector isolates solver effect from topology effect.

Design principles (CLAUDE.md §0.1):
    * Frozen dataclass → hashable, deeply immutable.
    * Topology + Asset are existing Phase 0 types; this module only
      adds the bundle so higher layers do not pass ad-hoc tuples around.
    * Source voltage / base frequency live on the network rather than in
      Topology.metadata so converters have a single canonical site for
      them.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.domain.cdl.asset import Asset
from gridflow.domain.cdl.topology import Topology
from gridflow.domain.error import CDLValidationError


@dataclass(frozen=True)
class CDLNetwork:
    """Solver-agnostic power-system network description.

    Attributes:
        topology: Nodes and edges of the network.
        assets: Loads, generators, PV, batteries etc. attached to nodes.
        base_voltage_kv: System base voltage used by per-unit
            conversions. Must match :attr:`Topology` node voltages
            within the bus hierarchy.
        base_frequency_hz: System frequency (default 60 Hz). Some
            solvers need this explicitly at network-build time.
    """

    topology: Topology
    assets: tuple[Asset, ...] = ()
    base_voltage_kv: float = 12.47
    base_frequency_hz: float = 60.0

    def __post_init__(self) -> None:
        self.topology.validate()
        for asset in self.assets:
            asset.validate()
        if self.base_voltage_kv <= 0:
            raise CDLValidationError(f"CDLNetwork.base_voltage_kv must be positive, got {self.base_voltage_kv}")
        if self.base_frequency_hz <= 0:
            raise CDLValidationError(f"CDLNetwork.base_frequency_hz must be positive, got {self.base_frequency_hz}")
        # Every asset's node must exist in the topology — the converters
        # rely on this invariant so they can skip validation themselves.
        node_ids = {n.node_id for n in self.topology.nodes}
        for asset in self.assets:
            if asset.node_id not in node_ids:
                raise CDLValidationError(f"Asset '{asset.asset_id}' references unknown node '{asset.node_id}'")

    def to_dict(self) -> dict[str, object]:
        return {
            "topology": self.topology.to_dict(),
            "assets": [a.to_dict() for a in self.assets],
            "base_voltage_kv": self.base_voltage_kv,
            "base_frequency_hz": self.base_frequency_hz,
        }


__all__ = ["CDLNetwork"]
