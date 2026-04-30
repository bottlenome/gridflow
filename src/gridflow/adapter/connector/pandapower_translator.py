"""PandapowerTranslator — bidirectional CDL ⇔ pandapower adapter.

Spec: ``docs/detailed_design/03b_usecase_classes.md`` §3.5.4a /
DD-CLS-059.

Two directions:

* :meth:`from_canonical` — :class:`CDLNetwork` → live ``pandapowerNet``.
  Used by :class:`PandaPowerConnector` to build a network from a CDL
  pack. Lazy-imports ``pandapower`` so callers without the
  ``[pandapower]`` extra get a :class:`ConnectorError` rather than an
  ``ImportError`` at module import time.
* :meth:`to_canonical` — live ``pandapowerNet`` → :class:`CDLNetwork`.
  Lets cross-solver round-trip workflows (CDL → pandapower → CDL → ...)
  verify that the canonical form is the source of truth.

The pre-Phase-2 standalone function ``cdl_to_pandapower`` lives in
``gridflow.adapter.network.cdl_to_pandapower`` and is now a thin
wrapper around :meth:`PandapowerTranslator.from_canonical` for
backward compatibility.
"""

from __future__ import annotations

import math
from typing import Any

from gridflow.domain.cdl import Asset, CDLNetwork, Edge, Node, Topology
from gridflow.domain.error import ConnectorError
from gridflow.domain.util.params import as_params


class PandapowerTranslator:
    """Bidirectional CDL ⇔ pandapower translator.

    Stateless: every call returns a fresh artefact. The class shape is
    chosen over plain functions so future extensions (custom asset type
    handlers, options dicts) have an obvious extension point without
    breaking the public API.
    """

    @staticmethod
    def from_canonical(network: CDLNetwork) -> Any:
        """Build a live pandapower ``pandapowerNet`` for ``network``."""
        # Delegate to the existing implementation so we keep one source
        # of truth for the conversion semantics. The function form
        # remains the runtime workhorse; this class is the spec-aligned
        # surface.
        from gridflow.adapter.network.cdl_to_pandapower import cdl_to_pandapower

        return cdl_to_pandapower(network)

    @staticmethod
    def to_canonical(
        net: Any,
        *,
        topology_id: str = "pandapower_canonical",
        name: str = "pandapower_canonical",
        source_bus_index: int | None = None,
    ) -> CDLNetwork:
        """Build a :class:`CDLNetwork` from a live ``pandapowerNet``.

        Args:
            net: A live pandapower network with ``bus``, ``line``,
                ``trafo``, ``load``, ``sgen``, ``ext_grid`` DataFrames.
            topology_id: Identifier for the resulting Topology.
            name: Topology name.
            source_bus_index: Override the ext_grid bus selection. If
                ``None``, the first row of ``net.ext_grid`` is used.

        The CDL is the **lossy** projection — pandapower-specific
        controllers, switches, and DC line representations have no
        canonical equivalent and are dropped. Callers needing full
        round-trip identity should keep the raw network alongside.
        """
        pp = _load_pandapower_strict()  # noqa: F841 — imported for error parity even if unused below.

        nodes = _nodes_from_pp(net)
        if not nodes:
            raise ConnectorError("pandapower network has no buses; nothing to canonicalise")
        if source_bus_index is None:
            source_bus_index = _resolve_source_bus_index(net)
        source_node_id = f"bus_{source_bus_index}"

        edges = _edges_from_pp(net)
        topology = Topology(
            topology_id=topology_id,
            name=name,
            nodes=tuple(nodes),
            edges=tuple(edges),
            source_bus=source_node_id,
        )
        assets = _assets_from_pp(net)
        base_kv = _resolve_base_voltage_kv(net, source_bus_index)
        base_hz = float(getattr(net, "f_hz", 60.0))
        return CDLNetwork(
            topology=topology,
            assets=tuple(assets),
            base_voltage_kv=base_kv,
            base_frequency_hz=base_hz,
        )


# ----------------------------------------------------------------- helpers


def _load_pandapower_strict() -> Any:
    """Same import-error handling as cdl_to_pandapower; ensures parity."""
    try:
        import pandapower as pp
    except ImportError as exc:
        raise ConnectorError(
            "pandapower is not installed. Install with `pip install pandapower` or `pip install -e .[pandapower]`",
            cause=exc,
        ) from exc
    return pp


def _nodes_from_pp(net: Any) -> list[Node]:
    nodes: list[Node] = []
    for idx, row in net.bus.iterrows():
        nodes.append(
            Node(
                node_id=f"bus_{idx}",
                name=str(row.get("name") or f"bus_{idx}"),
                node_type="bus",
                voltage_kv=float(row["vn_kv"]),
            )
        )
    return nodes


def _edges_from_pp(net: Any) -> list[Edge]:
    edges: list[Edge] = []
    for idx, row in net.line.iterrows():
        properties = {
            "r1_ohm_per_km": float(row["r_ohm_per_km"]),
            "x1_ohm_per_km": float(row["x_ohm_per_km"]),
            "c_nf_per_km": float(row.get("c_nf_per_km", 0.0)),
            "max_i_ka": float(row.get("max_i_ka", 1.0)),
        }
        edges.append(
            Edge(
                edge_id=str(row.get("name") or f"line_{idx}"),
                from_node=f"bus_{int(row['from_bus'])}",
                to_node=f"bus_{int(row['to_bus'])}",
                edge_type="line",
                length_km=float(row["length_km"]),
                properties=as_params(properties),
            )
        )
    if hasattr(net, "trafo") and len(net.trafo) > 0:
        for idx, row in net.trafo.iterrows():
            properties = {
                "kva": float(row["sn_mva"]) * 1000.0,
                "xhl_pct": float(row["vk_percent"]),
            }
            edges.append(
                Edge(
                    edge_id=str(row.get("name") or f"trafo_{idx}"),
                    from_node=f"bus_{int(row['hv_bus'])}",
                    to_node=f"bus_{int(row['lv_bus'])}",
                    edge_type="transformer",
                    length_km=None,
                    properties=as_params(properties),
                )
            )
    return edges


def _assets_from_pp(net: Any) -> list[Asset]:
    assets: list[Asset] = []
    if hasattr(net, "load"):
        for idx, row in net.load.iterrows():
            kw = float(row["p_mw"]) * 1000.0
            params: dict[str, object] = {}
            q_mvar = float(row.get("q_mvar", 0.0))
            if kw > 0 and abs(q_mvar) > 1e-9:
                pf = kw / 1000.0 / math.hypot(kw / 1000.0, q_mvar)
                params["pf"] = round(pf, 6)
            assets.append(
                Asset(
                    asset_id=str(row.get("name") or f"load_{idx}"),
                    name=str(row.get("name") or f"load_{idx}"),
                    asset_type="load",
                    node_id=f"bus_{int(row['bus'])}",
                    rated_power_kw=kw,
                    parameters=as_params(params),
                )
            )
    if hasattr(net, "sgen"):
        for idx, row in net.sgen.iterrows():
            kw = float(row["p_mw"]) * 1000.0
            sgen_type = str(row.get("type") or "")
            asset_type = "pv" if sgen_type.upper() == "PV" else "generator"
            assets.append(
                Asset(
                    asset_id=str(row.get("name") or f"sgen_{idx}"),
                    name=str(row.get("name") or f"sgen_{idx}"),
                    asset_type=asset_type,
                    node_id=f"bus_{int(row['bus'])}",
                    rated_power_kw=kw,
                )
            )
    return assets


def _resolve_source_bus_index(net: Any) -> int:
    """Pick the ext_grid bus, falling back to bus index 0."""
    if hasattr(net, "ext_grid") and len(net.ext_grid) > 0:
        return int(net.ext_grid.iloc[0]["bus"])
    if len(net.bus) > 0:
        return int(net.bus.index[0])
    raise ConnectorError("pandapower network has neither ext_grid nor any bus")


def _resolve_base_voltage_kv(net: Any, source_bus_index: int) -> float:
    """Read vn_kv at the source bus; fall back to maximum vn_kv."""
    try:
        return float(net.bus.loc[source_bus_index, "vn_kv"])
    except Exception:
        # In rare cases the bus index is not aligned with the iloc
        # position (e.g. after a row deletion); take the max vn_kv as
        # a conservative fallback.
        return float(net.bus["vn_kv"].max())
