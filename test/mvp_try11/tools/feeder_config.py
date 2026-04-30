"""Per-feeder VPP configuration — feeder-appropriate SLA and burst sizes.

Spec: F-M2 multi-feeder + multi-scale.

Each feeder has a transformer rating that bounds realistic VPP injection.
We size SLA = 50% of transformer MVA so the VPP standby + active never
saturates the upstream grid. Burst sizes scale with SLA.

The same pool can be reused across feeders, but the *active* set is
sized per feeder (= residential_ev count tied to feeder's load count).
"""

from __future__ import annotations

from dataclasses import dataclass

from .der_pool import DER


@dataclass(frozen=True)
class FeederVppConfig:
    """Per-feeder VPP scenario configuration."""

    feeder_name: str
    sla_kw: float
    burst_kw: tuple[tuple[str, float], ...]
    n_active_ev: int

    def burst_dict(self) -> dict[str, float]:
        return dict(self.burst_kw)


# Feeder transformer MVA (from create_*_network introspection)
FEEDER_TRAFO_MVA: dict[str, float] = {
    "cigre_lv":        0.95,
    "kerber_dorf":     0.40,
    "kerber_landnetz": 0.16,
}


def get_feeder_config(feeder_name: str) -> FeederVppConfig:
    """Return per-feeder VPP scenario sized to transformer capacity."""
    trafo_mva = FEEDER_TRAFO_MVA.get(feeder_name, 0.40)
    sla_kw = round(trafo_mva * 1000 * 0.50)  # 50% transformer rating
    # Burst sizes: commute = full SLA recovery, others ~30% SLA
    burst = (
        ("commute",     float(sla_kw)),
        ("weather",     float(sla_kw * 0.30)),
        ("market",      float(sla_kw * 0.30)),
        ("comm_fault",  float(sla_kw * 0.20)),
    )
    # Active EV count to make EVs ~70% of SLA (= rest from standby)
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))  # 7 kW per EV
    return FeederVppConfig(
        feeder_name=feeder_name,
        sla_kw=float(sla_kw),
        burst_kw=burst,
        n_active_ev=n_active_ev,
    )


def feeder_active_pool(
    pool: tuple[DER, ...],
    config: FeederVppConfig,
) -> frozenset[str]:
    """Pick the first ``n_active_ev`` residential_ev DERs as the active pool."""
    ev_pool = [d for d in pool if d.der_type == "residential_ev"]
    selected = ev_pool[:config.n_active_ev]
    return frozenset(d.der_id for d in selected)
