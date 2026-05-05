"""DER pool with response time constants τ_j (try15 contribution).

try15 M10 (Time-Constant Diversified VPP Pool) requires each DER j to
carry a response time constant τ_j (sec) representing **the physical
delay** between a trigger event firing and the DER actually leaving
the VPP. Default τ values per type are listed in DEFAULT_TAU_DROP_S
below — they are physically justified order-of-magnitude estimates,
not measured.

We do NOT modify try11's der_pool module (= frozen). Instead this
module wraps try11's `make_default_pool` and attaches τ values via a
side-table keyed by der_id. Callers that ignore τ continue to see the
try11-compatible DER objects. Callers that consume τ use
``tau_for(der_id)`` or the ``with_tau`` decorator.

Physical justification (order-of-magnitude):
  utility_battery     τ ≈   5 s   (BMS / inverter command latency)
  industrial_battery  τ ≈  30 s   (operation-override interlock)
  commercial_fleet    τ ≈ 180 s   (fleet manager human latency)
  residential_ev      τ ≈ 300 s   (owner decision lead-time)
  heat_pump           τ ≈  60 s   (weather sensor + thermostat lag)
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

_TRY11 = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

from tools.der_pool import DER, make_default_pool  # noqa: E402

DEFAULT_TAU_DROP_S: dict[str, float] = {
    "utility_battery": 5.0,
    "industrial_battery": 30.0,
    "commercial_fleet": 180.0,
    "residential_ev": 300.0,
    "heat_pump": 60.0,
}


@dataclass(frozen=True)
class TauPool:
    """try11 pool plus τ side-table keyed by der_id.

    ``pool`` is the original DER tuple (try11 format, immutable).
    ``tau_drop_s`` maps each der_id to its drop time constant in seconds.
    """

    pool: tuple[DER, ...]
    tau_drop_s: tuple[tuple[str, float], ...]  # frozen mapping

    def tau_for(self, der_id: str) -> float:
        for k, v in self.tau_drop_s:
            if k == der_id:
                return v
        raise KeyError(der_id)

    def tau_dict(self) -> dict[str, float]:
        return dict(self.tau_drop_s)


def make_tau_pool(
    seed: int = 0,
    *,
    tau_by_type: dict[str, float] | None = None,
    intra_type_jitter_frac: float = 0.0,
) -> TauPool:
    """Build a TauPool reusing try11's make_default_pool.

    Args:
        seed: passed through to make_default_pool.
        tau_by_type: optional override for the per-type τ (default uses
            ``DEFAULT_TAU_DROP_S``).
        intra_type_jitter_frac: if > 0, multiply each DER's τ by
            (1 + uniform(-frac, +frac)) using a deterministic RNG seeded
            on der_id. Allows within-type diversity without needing
            type-level new categories.

    Returns:
        TauPool whose ``pool`` is byte-compatible with try11 callers.
    """
    import random as _random

    pool = make_default_pool(seed=seed)
    base = dict(tau_by_type or DEFAULT_TAU_DROP_S)
    rng = _random.Random(seed)
    rows: list[tuple[str, float]] = []
    for d in pool:
        tau = base.get(d.der_type, 60.0)
        if intra_type_jitter_frac > 0:
            jitter = 1.0 + rng.uniform(-intra_type_jitter_frac, intra_type_jitter_frac)
            tau = max(0.1, tau * jitter)
        rows.append((d.der_id, float(tau)))
    return TauPool(pool=pool, tau_drop_s=tuple(rows))


def tau_diversity(pool: TauPool, der_ids: tuple[str, ...]) -> float:
    """Return the standard deviation of log(τ_j) over a subset of DERs.

    log-scale because τ values span ~5-300 s = 60×; linear stdev would
    be dominated by the few large-τ DERs while ignoring small-τ
    diversity that matters for the time-domain smearing.
    """
    import math
    if not der_ids:
        return 0.0
    log_taus = [math.log(pool.tau_for(d)) for d in der_ids]
    if len(log_taus) <= 1:
        return 0.0
    mean = sum(log_taus) / len(log_taus)
    var = sum((x - mean) ** 2 for x in log_taus) / len(log_taus)
    return math.sqrt(var)


__all__ = ("DEFAULT_TAU_DROP_S", "TauPool", "make_tau_pool", "tau_diversity")
