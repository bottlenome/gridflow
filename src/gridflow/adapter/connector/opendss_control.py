"""Live-OpenDSS :class:`GridModel` for the Volt-VAR control loop (issue #29).

Wires the pure control loop (:mod:`gridflow.usecase.control`) to a real
OpenDSS circuit: controllable PV inverters are injected as ``Generator``
elements whose reactive power the loop sets each iteration, and the loop reads
back per-bus voltages after each re-solve. This is what turns a *control
strategy* from an abstract object into something that runs on a feeder — the
capability try17 found missing (`test/mvp_try17/novelty_attempt.md`).

Kept in the adapter layer: it implements the UseCase-layer ``GridModel``
Protocol structurally, so ``run_volt_var`` drives it exactly like the fake grid
used in unit tests.
"""

from __future__ import annotations

import importlib
from dataclasses import dataclass, field
from typing import Any

from gridflow.domain.error import OpenDSSError


@dataclass(frozen=True)
class PVDeviceSpec:
    """A controllable PV inverter injected into the circuit.

    Attributes:
        device_id: OpenDSS ``Generator`` name and control key.
        sense_bus: Base bus name (as ``AllBusNames`` reports it, e.g. ``"675"``)
            whose voltage the local controller reads.
        inject_bus: Bus terminal the generator attaches to, with phases
            (e.g. ``"675.1.2.3"``).
        kw: Active power output (kW), held fixed by the loop.
        kv: Line-to-line nominal voltage (kV).
        phases: Phase count.
    """

    device_id: str
    sense_bus: str
    inject_bus: str
    kw: float
    kv: float = 4.16
    phases: int = 3


@dataclass
class OpenDSSGridModel:
    """A live OpenDSS circuit exposed as a control-loop :class:`GridModel`.

    Instantiate with a master ``.dss`` path and the PV devices to control; the
    constructor loads the circuit, injects the generators (starting at zero
    reactive power) and performs the first solve.
    """

    master_path: str
    devices: tuple[PVDeviceSpec, ...]
    _driver: Any = field(default=None, init=False, repr=False)

    def __post_init__(self) -> None:
        try:
            self._driver = importlib.import_module("opendssdirect")
        except ImportError as exc:  # pragma: no cover - env-specific
            raise OpenDSSError(
                "OpenDSSDirect.py is not installed. Install with `uv sync --extra opendss`.",
            ) from exc
        driver = self._driver
        driver.Basic.ClearAll()
        driver.Command(f"Redirect [{self.master_path}]")
        for d in self.devices:
            driver.Command(
                f"New Generator.{d.device_id} bus1={d.inject_bus} phases={d.phases} "
                f"kv={d.kv} conn=Wye kW={d.kw} kvar=0 Model=1"
            )
        driver.Command("Solve")

    # ------------------------------------------------------------- GridModel

    def bus_voltages(self) -> tuple[tuple[str, float], ...]:
        # AllBusMagPu() is per-node (bus.phase), aligned with AllNodeNames().
        # Aggregate to per-bus by taking the worst-case (max) magnitude across
        # a bus's phases — that is the quantity a Volt-VAR controller regulates.
        node_names = self._driver.Circuit.AllNodeNames()
        mags = self._driver.Circuit.AllBusMagPu()
        per_bus: dict[str, float] = {}
        for node, mag in zip(node_names, mags, strict=False):
            bus = str(node).split(".", 1)[0]
            per_bus[bus] = max(per_bus.get(bus, 0.0), float(mag))
        return tuple(sorted(per_bus.items()))

    def set_reactive(self, device_id: str, kvar: float) -> None:
        # Editing kvar overrides the pf=1.0 the generator was created with;
        # it takes effect on the next solve.
        self._driver.Command(f"Edit Generator.{device_id} kvar={kvar}")

    def solve(self) -> bool:
        self._driver.Command("Solve")
        return bool(self._driver.Solution.Converged())


__all__ = ["OpenDSSGridModel", "PVDeviceSpec"]
