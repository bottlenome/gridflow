"""DER (distributed energy resource) pool data model.

Spec: ``test/mvp_try11/implementation_plan.md`` §3.1.

Each DER has:
  * ``der_id``               — unique identifier
  * ``der_type``             — one of {residential_ev, commercial_fleet,
                                 industrial_battery, heat_pump, utility_battery}
  * ``capacity_kw``          — active power capacity (kW)
  * ``contract_cost_active`` — monthly cost if recruited into active pool (¥)
  * ``contract_cost_standby``— monthly cost if recruited into standby pool (¥)
  * ``trigger_exposure``     — K-dim binary tuple; entry k=True iff this DER
                               churns when trigger k fires.

Design principles (CLAUDE.md §0.1):
  * frozen dataclass → hashable, deeply immutable
  * trigger_exposure is a tuple, not a list, to preserve immutability
  * the per-type default exposure profile is encoded as module-level
    constants — there is no implicit dict mapping anywhere
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

# Trigger basis enumeration (spec §3.2)
TRIGGER_BASIS_K2: tuple[str, ...] = ("commute", "weather")
TRIGGER_BASIS_K3: tuple[str, ...] = ("commute", "weather", "market")
TRIGGER_BASIS_K4: tuple[str, ...] = ("commute", "weather", "market", "comm_fault")
TRIGGER_BASIS_K5: tuple[str, ...] = TRIGGER_BASIS_K4 + ("regulatory",)

# Per-DER-type default trigger exposure under K=4 basis.
# Each tuple aligns with TRIGGER_BASIS_K4 = (commute, weather, market, comm_fault).
DEFAULT_EXPOSURE_K4: dict[str, tuple[bool, bool, bool, bool]] = {
    "residential_ev":      (True,  False, False, True),
    "commercial_fleet":    (False, False, False, True),
    "industrial_battery":  (False, False, True,  True),
    "heat_pump":           (False, True,  False, True),
    "utility_battery":     (False, False, False, False),
}

# Default capacity and cost per DER type (rounded ballpark figures).
DEFAULT_CAPACITY_KW: dict[str, float] = {
    "residential_ev":     7.0,    # 7 kW home charger
    "commercial_fleet":  22.0,    # 22 kW DC fast
    "industrial_battery": 100.0,  # 100 kW industrial battery
    "heat_pump":          3.0,    # 3 kW heat pump
    "utility_battery":   500.0,   # 500 kW utility-scale battery
}

DEFAULT_COST_ACTIVE: dict[str, float] = {
    "residential_ev":      500.0,   # ¥/month active
    "commercial_fleet":   1500.0,
    "industrial_battery": 5000.0,
    "heat_pump":           300.0,
    "utility_battery":   20000.0,
}

DEFAULT_COST_STANDBY: dict[str, float] = {
    "residential_ev":      150.0,   # ¥/month standby reservation
    "commercial_fleet":    400.0,
    "industrial_battery": 1500.0,
    "heat_pump":           100.0,
    "utility_battery":    6000.0,
}


@dataclass(frozen=True)
class DER:
    """A single distributed energy resource.

    Attributes:
        der_id: Unique identifier within a pool.
        der_type: One of the five DER classes.
        capacity_kw: Active power capacity.
        contract_cost_active: Monthly cost if recruited as active.
        contract_cost_standby: Monthly cost if recruited as standby.
        trigger_exposure: Boolean tuple aligned with the trigger basis;
            entry k=True iff this DER churns when trigger k fires.
    """

    der_id: str
    der_type: str
    capacity_kw: float
    contract_cost_active: float
    contract_cost_standby: float
    trigger_exposure: tuple[bool, ...]


def make_default_pool(
    *,
    n_residential_ev: int = 80,
    n_commercial_fleet: int = 30,
    n_industrial_battery: int = 30,
    n_heat_pump: int = 30,
    n_utility_battery: int = 30,
    seed: int = 0,
) -> tuple[DER, ...]:
    """Generate a deterministic default DER pool (spec §6.1).

    Total ~200 DERs. Each DER's exposure is the type's default with
    independent 5% probability of an extra random trigger flip — this models
    real-world heterogeneity without compromising the per-type exposure
    structure that SDP relies on.
    """
    counts = (
        ("residential_ev", n_residential_ev),
        ("commercial_fleet", n_commercial_fleet),
        ("industrial_battery", n_industrial_battery),
        ("heat_pump", n_heat_pump),
        ("utility_battery", n_utility_battery),
    )
    rng = random.Random(seed)
    pool: list[DER] = []
    for der_type, n in counts:
        exposure = DEFAULT_EXPOSURE_K4[der_type]
        cap = DEFAULT_CAPACITY_KW[der_type]
        cost_a = DEFAULT_COST_ACTIVE[der_type]
        cost_s = DEFAULT_COST_STANDBY[der_type]
        for i in range(n):
            # 5% per-axis flip to add mild heterogeneity within a type
            flipped = tuple(
                (e ^ (rng.random() < 0.05)) for e in exposure
            )
            pool.append(
                DER(
                    der_id=f"{der_type}_{i:03d}",
                    der_type=der_type,
                    capacity_kw=cap,
                    contract_cost_active=cost_a,
                    contract_cost_standby=cost_s,
                    trigger_exposure=flipped,
                )
            )
    return tuple(pool)


def write_pool_csv(pool: tuple[DER, ...], path: Path) -> None:
    """Persist a pool as CSV (spec §3.1)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(
            ["der_id", "der_type", "capacity_kw",
             "contract_cost_active", "contract_cost_standby",
             "exposure_commute", "exposure_weather",
             "exposure_market", "exposure_comm_fault"]
        )
        for d in pool:
            writer.writerow(
                [d.der_id, d.der_type, d.capacity_kw,
                 d.contract_cost_active, d.contract_cost_standby,
                 int(d.trigger_exposure[0]), int(d.trigger_exposure[1]),
                 int(d.trigger_exposure[2]), int(d.trigger_exposure[3])]
            )


def load_pool_csv(path: Path) -> tuple[DER, ...]:
    """Load a pool from CSV. Inverse of :func:`write_pool_csv`."""
    pool: list[DER] = []
    with path.open(encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        for row in reader:
            exposure = (
                bool(int(row["exposure_commute"])),
                bool(int(row["exposure_weather"])),
                bool(int(row["exposure_market"])),
                bool(int(row["exposure_comm_fault"])),
            )
            pool.append(
                DER(
                    der_id=row["der_id"],
                    der_type=row["der_type"],
                    capacity_kw=float(row["capacity_kw"]),
                    contract_cost_active=float(row["contract_cost_active"]),
                    contract_cost_standby=float(row["contract_cost_standby"]),
                    trigger_exposure=exposure,
                )
            )
    return tuple(pool)


def project_exposure(
    der: DER,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
) -> tuple[bool, ...]:
    """Project a DER's K=4 exposure tuple to a smaller / different basis.

    The DER's stored exposure is always w.r.t. ``TRIGGER_BASIS_K4``; this
    helper extracts the components corresponding to ``basis``. For
    ``TRIGGER_BASIS_K5``, the regulatory axis is reported as ``False``
    (DERs in this synthetic pool have no labelled regulatory exposure;
    that is the OOD/C4 setting).
    """
    out: list[bool] = []
    for axis in basis:
        if axis == "commute":
            out.append(der.trigger_exposure[0])
        elif axis == "weather":
            out.append(der.trigger_exposure[1])
        elif axis == "market":
            out.append(der.trigger_exposure[2])
        elif axis == "comm_fault":
            out.append(der.trigger_exposure[3])
        elif axis == "regulatory":
            out.append(False)
        else:
            raise ValueError(f"unknown trigger axis: {axis}")
    return tuple(out)
