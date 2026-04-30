"""CDLNetwork → pandapower network converter.

Spec: ``docs/phase1_result.md`` §5.1.3.

Returns a live ``pandapower`` ``pandapowerNet`` object. Unlike the DSS
converter (which is string-producing), pandapower is a pure-Python
library where the network is built up via function calls — so this
module imports ``pandapower`` at call time.

Supported CDL subset matches :mod:`cdl_to_dss`:
    * Nodes → ``create_bus``
    * Edges of type ``line`` with impedance properties → ``create_line_from_parameters``
    * Edges of type ``transformer`` → ``create_transformer_from_parameters``
    * Assets: ``load`` → ``create_load``, ``pv``/``generator``/``sgen`` → ``create_sgen``
    * Source bus becomes the ``ext_grid`` reference.

pandapower is optional (``pip install -e .[pandapower]``); callers who
don't have it installed get :class:`ConnectorError` at invocation time
rather than at import time.
"""

from __future__ import annotations

from typing import Any

from gridflow.domain.cdl import CDLNetwork
from gridflow.domain.cdl.asset import Asset
from gridflow.domain.cdl.topology import Edge, Node
from gridflow.domain.error import CDLValidationError, ConnectorError
from gridflow.domain.util.params import get_param


def cdl_to_pandapower(network: CDLNetwork) -> Any:
    """Build and return a live pandapower ``pandapowerNet`` for ``network``."""
    pp = _load_pandapower()
    net = pp.create_empty_network(
        f_hz=network.base_frequency_hz,
        sn_mva=1.0,
    )

    # Map CDL node_id → pandapower bus index. Keep a sorted mapping so
    # the resulting network is deterministic w.r.t. the same CDL input.
    bus_by_node_id: dict[str, int] = {}
    for node in network.topology.nodes:
        bus_by_node_id[node.node_id] = _create_bus(pp, net, node)

    # ext_grid on the source bus — required before runpp resolves the slack.
    source_bus = bus_by_node_id.get(network.topology.source_bus)
    if source_bus is None:  # pragma: no cover — caught by CDLNetwork validation
        raise CDLValidationError(f"source_bus '{network.topology.source_bus}' not found among nodes")
    pp.create_ext_grid(net, bus=source_bus, vm_pu=1.0, name="ext_grid")

    for edge in network.topology.edges:
        _create_edge(pp, net, edge, bus_by_node_id, network)

    for asset in network.assets:
        _create_asset(pp, net, asset, bus_by_node_id)

    return net


# ----------------------------------------------------------------- helpers


def _load_pandapower() -> Any:
    try:
        import pandapower as pp
    except ImportError as exc:
        raise ConnectorError(
            "pandapower is not installed. Install with `pip install pandapower` or `pip install -e .[pandapower]`",
            cause=exc,
        ) from exc
    return pp


def _create_bus(pp: Any, net: Any, node: Node) -> int:
    return int(
        pp.create_bus(
            net,
            vn_kv=node.voltage_kv,
            name=node.name or node.node_id,
        )
    )


def _create_edge(
    pp: Any,
    net: Any,
    edge: Edge,
    bus_by_node_id: dict[str, int],
    network: CDLNetwork,
) -> None:
    if edge.from_node not in bus_by_node_id or edge.to_node not in bus_by_node_id:
        raise CDLValidationError(f"edge '{edge.edge_id}' references an unknown node")
    edge_type = (edge.edge_type or "line").lower()

    from_bus = bus_by_node_id[edge.from_node]
    to_bus = bus_by_node_id[edge.to_node]

    if edge_type == "transformer":
        _create_transformer(pp, net, edge, from_bus, to_bus, network)
        return

    length_km = edge.length_km if edge.length_km is not None else 1.0
    r_ohm_per_km = _float_property(edge, "r1_ohm_per_km", default=0.3)
    x_ohm_per_km = _float_property(edge, "x1_ohm_per_km", default=0.5)
    c_nf_per_km = _float_property(edge, "c_nf_per_km", default=0.0)
    max_i_ka = _float_property(edge, "max_i_ka", default=1.0)
    pp.create_line_from_parameters(
        net,
        from_bus=from_bus,
        to_bus=to_bus,
        length_km=length_km,
        r_ohm_per_km=r_ohm_per_km,
        x_ohm_per_km=x_ohm_per_km,
        c_nf_per_km=c_nf_per_km,
        max_i_ka=max_i_ka,
        name=edge.edge_id,
    )


def _create_transformer(
    pp: Any,
    net: Any,
    edge: Edge,
    from_bus: int,
    to_bus: int,
    network: CDLNetwork,
) -> None:
    from_node = _find_node(network, edge.from_node)
    to_node = _find_node(network, edge.to_node)
    kva = _float_property(edge, "kva", default=1000.0)
    xhl_pct = _float_property(edge, "xhl_pct", default=5.0)
    pp.create_transformer_from_parameters(
        net,
        hv_bus=from_bus,
        lv_bus=to_bus,
        sn_mva=kva / 1000.0,
        vn_hv_kv=(from_node.voltage_kv if from_node else network.base_voltage_kv),
        vn_lv_kv=(to_node.voltage_kv if to_node else network.base_voltage_kv),
        vkr_percent=0.5,
        vk_percent=xhl_pct,
        pfe_kw=0.0,
        i0_percent=0.0,
        name=edge.edge_id,
    )


def _create_asset(
    pp: Any,
    net: Any,
    asset: Asset,
    bus_by_node_id: dict[str, int],
) -> None:
    if asset.node_id not in bus_by_node_id:
        raise CDLValidationError(f"asset '{asset.asset_id}' references unknown node '{asset.node_id}'")
    bus = bus_by_node_id[asset.node_id]
    asset_type = asset.asset_type.lower()
    if asset_type == "load":
        pp.create_load(
            net,
            bus=bus,
            p_mw=asset.rated_power_kw / 1000.0,
            q_mvar=_q_mvar_from_pf(asset),
            name=asset.asset_id,
        )
        return
    if asset_type in {"pv", "generator", "sgen"}:
        pp.create_sgen(
            net,
            bus=bus,
            p_mw=asset.rated_power_kw / 1000.0,
            q_mvar=0.0,
            name=asset.asset_id,
            type="PV" if asset_type == "pv" else "generator",
        )
        return
    # Other asset types are ignored silently at the pandapower layer —
    # they only matter for solvers that support them.


def _find_node(network: CDLNetwork, node_id: str) -> Node | None:
    for node in network.topology.nodes:
        if node.node_id == node_id:
            return node
    return None


def _q_mvar_from_pf(asset: Asset) -> float:
    """Derive reactive power (MVAr) from rated kW and pf, if pf is given."""
    pf = _float_parameter(asset, "pf")
    if pf is None or pf >= 1.0 or pf <= 0:
        return 0.0
    import math

    tan_phi = math.tan(math.acos(pf))
    p_mw = asset.rated_power_kw / 1000.0
    return p_mw * tan_phi


def _float_property(edge: Edge, key: str, *, default: float) -> float:
    value = get_param(edge.properties, key)
    if value is None:
        return default
    return float(value)  # type: ignore[arg-type]


def _float_parameter(asset: Asset, key: str) -> float | None:
    value = get_param(asset.parameters, key)
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]
