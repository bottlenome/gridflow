"""Radial PV-rich distribution feeder (analytical linearised DistFlow).

We use a single-phase, balanced, radial feeder with N buses indexed
0..N-1.  Bus 0 = substation (slack, fixed at V0_pu).  Each bus i has a
PV inverter with rated capacity ``pv_cap_kw[i]`` (which doubles as
the Q range +/- pv_cap_kw[i]) and a passive load ``load_kw[i]``.

Linearised DistFlow (LinDistFlow) relation:

    V_i(t) = V0 + sum_{k <= i} (R_k * P_down_k(t) + X_k * Q_down_k(t)) / Sbase

where P_down_k / Q_down_k are downstream net injections through segment
k.  Positive p_inj at downstream buses (PV exporting > load) raises V;
positive Q injection raises V (capacitive); negative Q absorbs (inductive).

where ``below_k`` aggregates buses with electrical depth >= k along
the radial path.  Voltage is reported in pu against V0_pu.

The model intentionally omits transformer impedance, line shunt, and
3-phase imbalance: the contribution of try16 is *control* logic for
delay-robust Volt-VAR, not feeder modelling.  See theorems.md for the
analytic Bode bound that motivates this simplification.
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class RadialFeeder:
    name: str
    n_bus: int
    r_per_seg_pu: tuple[float, ...]   # length n_bus-1
    x_per_seg_pu: tuple[float, ...]   # length n_bus-1
    pv_cap_kw: tuple[float, ...]      # length n_bus, includes bus 0=0
    load_kw: tuple[float, ...]        # length n_bus
    sbase_kw: float
    v0_pu: float
    v_upper_pu: float
    v_lower_pu: float

    @property
    def depth_pu(self) -> tuple[float, ...]:
        """Cumulative R from substation to each bus (pu).  d_pu[0]=0."""
        d = [0.0]
        for r in self.r_per_seg_pu:
            d.append(d[-1] + r)
        return tuple(d)

    @property
    def x_cum_pu(self) -> tuple[float, ...]:
        d = [0.0]
        for x in self.x_per_seg_pu:
            d.append(d[-1] + x)
        return tuple(d)


def make_feeder(
    name: str = "rad32",
    n_bus: int = 32,
    *,
    r_seg_pu: float = 0.012,
    x_seg_pu: float = 0.008,
    pv_cap_each_kw: float = 25.0,
    load_each_kw: float = 6.0,
    sbase_kw: float = 1000.0,
    v0_pu: float = 1.00,
    v_upper_pu: float = 1.05,
    v_lower_pu: float = 0.95,
) -> RadialFeeder:
    """Build a homogeneous radial feeder with N buses (bus 0 = substation, no PV)."""
    if n_bus < 4:
        raise ValueError("n_bus must be >= 4")
    pv = [0.0] + [pv_cap_each_kw] * (n_bus - 1)
    load = [0.0] + [load_each_kw] * (n_bus - 1)
    return RadialFeeder(
        name=name,
        n_bus=n_bus,
        r_per_seg_pu=tuple([r_seg_pu] * (n_bus - 1)),
        x_per_seg_pu=tuple([x_seg_pu] * (n_bus - 1)),
        pv_cap_kw=tuple(pv),
        load_kw=tuple(load),
        sbase_kw=sbase_kw,
        v0_pu=v0_pu,
        v_upper_pu=v_upper_pu,
        v_lower_pu=v_lower_pu,
    )


def lindistflow_voltage(
    feeder: RadialFeeder,
    p_inj_kw: tuple[float, ...],   # net P injection at each bus (PV - load), length n_bus
    q_inj_kw: tuple[float, ...],   # net Q injection at each bus (PV inverter Q), length n_bus
) -> tuple[float, ...]:
    """Compute bus voltages in pu via linearised DistFlow (radial)."""
    n = feeder.n_bus
    if len(p_inj_kw) != n or len(q_inj_kw) != n:
        raise ValueError("p_inj_kw / q_inj_kw length mismatch with feeder.n_bus")
    # P_below_k = sum of injections at buses k..n-1 (downstream of segment k-1)
    # Voltage at bus i: V_i = V_0 + sum_{k=1..i} (R_k * P_below_k - X_k * Q_below_k) / Sbase
    # but with sign: positive injection raises V upstream, so
    # ΔV(seg k) = (R_k * P_downstream_through_k - X_k * Q_downstream_through_k) / Sbase
    sbase = feeder.sbase_kw
    p_down = [0.0] * n
    q_down = [0.0] * n
    p_down[n - 1] = p_inj_kw[n - 1]
    q_down[n - 1] = q_inj_kw[n - 1]
    for i in range(n - 2, 0, -1):
        p_down[i] = p_down[i + 1] + p_inj_kw[i]
        q_down[i] = q_down[i + 1] + q_inj_kw[i]
    # Voltage cumulative along segments
    v = [feeder.v0_pu]
    for k in range(1, n):
        # segment between bus k-1 and bus k carries p_down[k] / q_down[k]
        dv = (feeder.r_per_seg_pu[k - 1] * p_down[k]
              + feeder.x_per_seg_pu[k - 1] * q_down[k]) / sbase
        v.append(v[-1] + dv)
    return tuple(v)
