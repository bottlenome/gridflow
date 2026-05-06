"""1-D advected cloud shadow over a radial feeder.

A cloud of length ``L_cloud`` (m) passes over the feeder at speed
``v_cloud`` (m/s), reducing PV output at covered buses by
``shadow_depth`` (fraction in [0,1]).  The feeder is parameterised in
metres via ``seg_length_m`` so cloud-edge propagation is realistic.

We expose:

  * ``CloudEvent`` — frozen dataclass describing one cloud transit
  * ``simulate_irradiance`` — per-bus PV multiplicative factor over time
  * ``random_event_stream`` — Poisson stream of clouds for a sweep cell
"""

from __future__ import annotations

import math
import random
from dataclasses import dataclass


@dataclass(frozen=True)
class CloudEvent:
    t_start_s: float          # leading edge enters bus 0 at this time
    v_cloud_m_s: float        # advection speed (positive = downstream)
    L_cloud_m: float          # cloud spatial extent
    shadow_depth: float       # PV multiplier reduction in [0,1]


def simulate_irradiance(
    n_bus: int,
    seg_length_m: float,
    events: tuple[CloudEvent, ...],
    duration_s: float,
    dt_s: float,
) -> tuple[tuple[float, ...], ...]:
    """Return tuple of length T_steps, each row is per-bus irradiance multiplier in [0,1].

    Buses are at positions x_i = i * seg_length_m.  A cloud event covers
    bus i during the time window
        [t_start + x_i / v - L/v, t_start + x_i / v]   (if v>0)
    with PV multiplier (1 - shadow_depth).
    """
    n_steps = int(round(duration_s / dt_s))
    irr: list[tuple[float, ...]] = []
    for k in range(n_steps):
        t = k * dt_s
        row = [1.0] * n_bus
        for ev in events:
            if ev.v_cloud_m_s <= 0:
                continue
            for i in range(n_bus):
                x_i = i * seg_length_m
                t_lead = ev.t_start_s + x_i / ev.v_cloud_m_s
                t_trail = t_lead - ev.L_cloud_m / ev.v_cloud_m_s
                if t_trail <= t <= t_lead:
                    row[i] = max(0.0, row[i] * (1.0 - ev.shadow_depth))
        irr.append(tuple(row))
    return tuple(irr)


def random_event_stream(
    seed: int,
    duration_s: float,
    *,
    rate_per_s: float = 0.05,        # ~ 1 cloud every 20 s
    v_cloud_range_m_s: tuple[float, float] = (5.0, 20.0),
    L_cloud_range_m: tuple[float, float] = (200.0, 1500.0),
    shadow_range: tuple[float, float] = (0.4, 0.9),
) -> tuple[CloudEvent, ...]:
    rng = random.Random(seed)
    events: list[CloudEvent] = []
    t = 0.0
    while t < duration_s:
        gap = rng.expovariate(rate_per_s)
        t += gap
        if t >= duration_s:
            break
        events.append(CloudEvent(
            t_start_s=t,
            v_cloud_m_s=rng.uniform(*v_cloud_range_m_s),
            L_cloud_m=rng.uniform(*L_cloud_range_m),
            shadow_depth=rng.uniform(*shadow_range),
        ))
    return tuple(events)
