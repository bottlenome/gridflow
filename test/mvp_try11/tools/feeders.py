"""Feeder selection for try11 multi-feeder validation.

Spec: ``test/mvp_try11/implementation_plan.md`` (F-M2 extension).

Three standard distribution feeders are integrated. Sizes were chosen
so the SDP standby pool (~3 utility batteries + a few smaller DERs)
can be deployed across feeders of varying topology and capacity:

* CIGRE LV (44 buses, 15 loads) — IEEE / CIGRE benchmark, suburban
* Kerber Dorfnetz (116 buses, 57 loads) — large rural German feeder
* Kerber Landnetz Freileitung 1 (15 buses, 13 loads) — small overhead-line
  rural feeder; replaces Dickert (which is only 3-bus, unsuitable)

The DER pool is mapped to feeder buses such that:
  * residential_ev / heat_pump → load buses (residential nodes)
  * commercial_fleet → first half of load buses (commercial-zone proxy)
  * industrial_battery → "deep" buses (longest electrical distance)
  * utility_battery → buses near substation (= feeder bus 0 area)

Bus assignment is *deterministic* given the pool so experiments are
reproducible across runs.
"""

from __future__ import annotations

from dataclasses import dataclass

import pandapower as pp
import pandapower.networks as pn

from .der_pool import DER


FEEDER_NAMES: tuple[str, ...] = ("cigre_lv", "kerber_dorf", "kerber_landnetz")


def make_feeder(name: str):
    """Build a fresh pandapower net for a named feeder."""
    if name == "cigre_lv":
        return pn.create_cigre_network_lv()
    if name == "kerber_dorf":
        return pn.create_kerber_dorfnetz()
    if name == "kerber_landnetz":
        return pn.create_kerber_landnetz_freileitung_1()
    raise ValueError(f"unknown feeder: {name}")


@dataclass(frozen=True)
class DerBusMap:
    """Mapping from DER ID to bus index, plus per-feeder topology stats.

    Attributes:
        feeder_name: One of FEEDER_NAMES.
        bus_of: dict-like mapping ``der_id -> bus_index``.
        n_buses: Total bus count.
        n_loads: Total existing-load count (used as residential proxy).
        substation_bus: The slack/external grid bus.
    """

    feeder_name: str
    bus_of: tuple[tuple[str, int], ...]  # frozen mapping
    n_buses: int
    n_loads: int
    substation_bus: int

    def get(self, der_id: str) -> int:
        for k, v in self.bus_of:
            if k == der_id:
                return v
        raise KeyError(der_id)


def _classify_buses(net) -> tuple[list[int], list[int], int]:
    """Return (load_buses, deep_buses, substation_bus).

    ``load_buses`` are buses that already host a load entry (residential
    proxy). ``deep_buses`` are buses with the highest path-resistance to
    the substation. Substation = slack bus (= external grid).
    """
    # External grid bus = slack
    if "ext_grid" in net and len(net.ext_grid) > 0:
        substation_bus = int(net.ext_grid.bus.iloc[0])
    else:
        substation_bus = 0
    # Load buses (have a load attached)
    load_buses = sorted(set(int(b) for b in net.load.bus.values))
    # Deep buses = buses farthest from substation in terms of path length
    # (graph BFS depth from substation)
    bus_indices = list(net.bus.index)
    line_pairs = [(int(net.line.from_bus.iloc[i]), int(net.line.to_bus.iloc[i]))
                  for i in range(len(net.line))]
    if "trafo" in net and len(net.trafo) > 0:
        for i in range(len(net.trafo)):
            line_pairs.append((int(net.trafo.hv_bus.iloc[i]), int(net.trafo.lv_bus.iloc[i])))
    # BFS
    adj: dict[int, list[int]] = {b: [] for b in bus_indices}
    for u, v in line_pairs:
        if u in adj and v in adj:
            adj[u].append(v)
            adj[v].append(u)
    depth = {substation_bus: 0}
    stack = [substation_bus]
    while stack:
        b = stack.pop()
        for nb in adj.get(b, []):
            if nb not in depth:
                depth[nb] = depth[b] + 1
                stack.append(nb)
    # Sort buses by depth (deepest first)
    sorted_buses = sorted(depth.items(), key=lambda kv: -kv[1])
    deep_buses = [b for b, _ in sorted_buses[:max(3, len(bus_indices) // 6)]]
    return load_buses, deep_buses, substation_bus


def map_pool_to_feeder(
    pool: tuple[DER, ...],
    feeder_name: str,
) -> DerBusMap:
    """Assign each DER to a feeder bus per the rules in this module's docstring."""
    net = make_feeder(feeder_name)
    load_buses, deep_buses, substation_bus = _classify_buses(net)
    # Substation-area buses = neighbours of substation (first 3 in BFS order)
    near_substation = sorted({substation_bus, *load_buses[:3]})
    if not load_buses:
        load_buses = list(net.bus.index)
    if not deep_buses:
        deep_buses = load_buses[-3:] or [substation_bus]

    bus_of: list[tuple[str, int]] = []
    for d in pool:
        if d.der_type == "residential_ev":
            bus = load_buses[hash(d.der_id) % len(load_buses)]
        elif d.der_type == "heat_pump":
            bus = load_buses[hash(d.der_id) % len(load_buses)]
        elif d.der_type == "commercial_fleet":
            half = max(1, len(load_buses) // 2)
            bus = load_buses[hash(d.der_id) % half]
        elif d.der_type == "industrial_battery":
            bus = deep_buses[hash(d.der_id) % len(deep_buses)]
        elif d.der_type == "utility_battery":
            bus = near_substation[hash(d.der_id) % len(near_substation)]
        else:
            bus = load_buses[hash(d.der_id) % len(load_buses)]
        bus_of.append((d.der_id, int(bus)))

    return DerBusMap(
        feeder_name=feeder_name,
        bus_of=tuple(bus_of),
        n_buses=int(len(net.bus)),
        n_loads=int(len(net.load)),
        substation_bus=substation_bus,
    )


def feeder_capacity_summary(name: str) -> dict[str, float]:
    """Quick stats about a feeder for capacity sanity-checking."""
    net = make_feeder(name)
    total_load_kw = float(net.load.p_mw.sum() * 1000)
    return {
        "n_buses": int(len(net.bus)),
        "n_lines": int(len(net.line)),
        "n_loads": int(len(net.load)),
        "total_existing_load_kw": total_load_kw,
    }
