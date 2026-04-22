"""CDLNetwork → OpenDSS script converter.

Spec: ``docs/phase1_result.md`` §5.1.3.

Produces a string containing a complete OpenDSS command block that
rebuilds the CDL network — equivalent to what a human author would put
in a ``master.dss`` file. The output is self-contained: the caller
feeds it to ``opendssdirect.Command(...)`` (or writes it to disk and
``Redirect`` s to it) without any further DSS setup.

Supported CDL subset:
    * Topology.nodes with voltage_kv
    * Topology.edges of type ``line`` with properties r1/x1/r0/x0
      (ohm/km) and length_km; ``transformer`` type emits ``New
      Transformer`` primitives when the two end nodes have different
      voltage_kv.
    * Asset types: ``load`` (emits ``New Load``) and ``pv`` or
      ``generator`` (emits ``New Generator`` with ``Model=1`` — constant
      current, i.e. the same shape the existing OpenDSSConnector PV
      injection uses).

The converter is intentionally *string-producing* (no opendssdirect
imports here) so it can run in any environment and be unit-tested
without a live DSS engine.
"""

from __future__ import annotations

from io import StringIO

from gridflow.domain.cdl import CDLNetwork
from gridflow.domain.cdl.asset import Asset
from gridflow.domain.cdl.topology import Edge
from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import get_param


def cdl_to_dss(network: CDLNetwork, *, circuit_name: str = "CDL") -> str:
    """Render ``network`` as a complete OpenDSS command script.

    Args:
        network: The canonical network to convert.
        circuit_name: Name passed to ``New Circuit`` — cosmetic, but
            must be a valid DSS identifier.
    """
    buf = StringIO()
    _emit_preamble(buf, network, circuit_name)
    _emit_linecode(buf, network)
    _emit_edges(buf, network)
    _emit_assets(buf, network)
    _emit_postamble(buf, network)
    return buf.getvalue()


# ----------------------------------------------------------------- sections


def _emit_preamble(buf: StringIO, network: CDLNetwork, circuit_name: str) -> None:
    topo = network.topology
    source_node = _find_node(network, topo.source_bus)
    if source_node is None:
        raise CDLValidationError(f"source_bus '{topo.source_bus}' not found among topology nodes")
    buf.write("Clear\n")
    buf.write(
        f"New Circuit.{circuit_name} bus1={topo.source_bus} "
        f"basekv={source_node.voltage_kv} phases=3 pu=1.0 frequency={network.base_frequency_hz}\n"
    )


def _emit_linecode(buf: StringIO, network: CDLNetwork) -> None:
    """Emit a conservative default linecode so lines without one still resolve.

    Real per-edge impedance lives on ``Edge.properties`` (see
    :func:`_emit_edges`), but we still declare a default linecode as a
    fallback for edges that omit impedance — the DSS parser requires
    that a referenced linecode exists even if we intend to override
    parameters inline.
    """
    buf.write("New Linecode.cdl_default nphases=3 r1=0.3 x1=0.5 r0=0.5 x0=0.7 c1=0.0 c0=0.0 units=km\n")


def _emit_edges(buf: StringIO, network: CDLNetwork) -> None:
    topo = network.topology
    for edge in topo.edges:
        from_node = _find_node(network, edge.from_node)
        to_node = _find_node(network, edge.to_node)
        if from_node is None or to_node is None:  # pragma: no cover
            # Caught by CDLNetwork.__post_init__ validation, but guard
            # against direct caller misuse.
            raise CDLValidationError(f"edge '{edge.edge_id}' references an unknown node")
        edge_type = (edge.edge_type or "line").lower()
        if edge_type == "transformer" and from_node.voltage_kv != to_node.voltage_kv:
            buf.write(_format_transformer(edge, from_node.voltage_kv, to_node.voltage_kv))
            continue
        buf.write(_format_line(edge))


def _format_line(edge: Edge) -> str:
    """Render one Edge as a ``New Line.`` command.

    The per-km impedance fields come from ``Edge.properties`` if
    present (keys ``r1_ohm_per_km`` / ``x1_ohm_per_km`` / ``r0_ohm_per_km``
    / ``x0_ohm_per_km``); otherwise the default linecode supplies them.
    """
    length_km = edge.length_km if edge.length_km is not None else 1.0
    r1 = _float_property(edge, "r1_ohm_per_km")
    x1 = _float_property(edge, "x1_ohm_per_km")
    r0 = _float_property(edge, "r0_ohm_per_km")
    x0 = _float_property(edge, "x0_ohm_per_km")
    parts: list[str] = [
        f"New Line.{_sanitize_id(edge.edge_id)}",
        f"bus1={edge.from_node}",
        f"bus2={edge.to_node}",
        f"length={length_km}",
        "units=km",
    ]
    if all(v is not None for v in (r1, x1, r0, x0)):
        parts.extend([f"r1={r1}", f"x1={x1}", f"r0={r0}", f"x0={x0}"])
    else:
        parts.append("linecode=cdl_default")
    return " ".join(parts) + "\n"


def _format_transformer(edge: Edge, kv_from: float, kv_to: float) -> str:
    """Render a voltage-changing edge as a 2-winding ``New Transformer``.

    Expects ``kva`` and optional ``%xhl`` on ``Edge.properties``; falls
    back to 1 MVA / 5% reactance as a safe default.
    """
    kva = _float_property(edge, "kva") or 1000.0
    xhl = _float_property(edge, "xhl_pct") or 5.0
    return (
        f"New Transformer.{_sanitize_id(edge.edge_id)} phases=3 windings=2 "
        f"buses=[{edge.from_node} {edge.to_node}] conns=[wye wye] "
        f"kvs=[{kv_from} {kv_to}] kvas=[{kva} {kva}] xhl={xhl}\n"
    )


def _emit_assets(buf: StringIO, network: CDLNetwork) -> None:
    for asset in network.assets:
        asset_type = asset.asset_type.lower()
        if asset_type == "load":
            buf.write(_format_load(asset, network))
        elif asset_type in {"pv", "generator", "sgen"}:
            buf.write(_format_generator(asset, network))
        else:
            # Unknown asset types are emitted as comments so the DSS
            # compiles but the omission is visible to the operator.
            buf.write(f"! CDL asset '{asset.asset_id}' ({asset.asset_type}) not mapped\n")


def _format_load(asset: Asset, network: CDLNetwork) -> str:
    node = _find_node(network, asset.node_id)
    kv = node.voltage_kv if node is not None else network.base_voltage_kv
    pf = _float_parameter(asset, "pf") or 0.95
    model_raw = _float_parameter(asset, "model")
    model = int(model_raw) if model_raw is not None else 1
    phases = int(_float_parameter(asset, "phases") or 3)
    return (
        f"New Load.{_sanitize_id(asset.asset_id)} "
        f"bus1={asset.node_id} kv={kv} kw={asset.rated_power_kw} "
        f"pf={pf} model={model} phases={phases}\n"
    )


def _format_generator(asset: Asset, network: CDLNetwork) -> str:
    node = _find_node(network, asset.node_id)
    kv = node.voltage_kv if node is not None else network.base_voltage_kv
    # Match the inline-PV convention used by OpenDSSConnector._inject_runtime_pv:
    # constant-current injection, unity pf, Model=1.
    pf = _float_parameter(asset, "pf") or 1.0
    model_raw = _float_parameter(asset, "model")
    model = int(model_raw) if model_raw is not None else 1
    phases = int(_float_parameter(asset, "phases") or 3)
    return (
        f"New Generator.{_sanitize_id(asset.asset_id)} "
        f"bus1={asset.node_id} kv={kv} kw={asset.rated_power_kw} "
        f"pf={pf} model={model} phases={phases}\n"
    )


def _emit_postamble(buf: StringIO, network: CDLNetwork) -> None:
    voltage_bases = sorted({n.voltage_kv for n in network.topology.nodes})
    buf.write(f"Set voltagebases={voltage_bases!r}\n".replace("'", ""))
    buf.write("Calcv\n")


# ----------------------------------------------------------------- helpers


def _find_node(network: CDLNetwork, node_id: str):  # type: ignore[no-untyped-def]
    """Linear-scan helper — networks are small enough that O(n) is fine."""
    for node in network.topology.nodes:
        if node.node_id == node_id:
            return node
    return None


def _float_property(edge: Edge, key: str) -> float | None:
    value = get_param(edge.properties, key)
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]


def _float_parameter(asset: Asset, key: str) -> float | None:
    value = get_param(asset.parameters, key)
    if value is None:
        return None
    return float(value)  # type: ignore[arg-type]


def _sanitize_id(raw: str) -> str:
    """DSS identifiers disallow whitespace / periods; replace them."""
    cleaned = "".join(c if c.isalnum() or c == "_" else "_" for c in raw)
    return cleaned or "unnamed"
