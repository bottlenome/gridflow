"""Pluggable Volt-VAR control strategies and the control loop (issue #29).

try17 found that the framework's *novelty ceiling* is set primarily by the lack
of a first-class point to plug in a control **method**: it could only compare
parameters/scenarios (hosting-capacity characterisation, whose behaviour is
textbook), never a new controller. Research novelty mostly comes from proposing
a method, so this module makes a Volt-VAR control strategy a first-class,
swappable object that the standard ``benchmark`` path can compare — a
researcher implements one class and pits it against the reference strategies.

Layering (CLAUDE.md §0.1):
    * ``ControlStrategy`` and the loop are pure UseCase — they know nothing
      about OpenDSS/pandapower. The loop drives an abstract :class:`GridModel`
      (apply reactive power, re-solve, read bus voltages), so the same loop
      runs against a live solver *or* a fake grid in tests.
    * Reactive-power sign convention: ``kvar > 0`` injects vars (raises local
      voltage), ``kvar < 0`` absorbs vars (lowers it). A Volt-VAR controller
      absorbs at high voltage and injects at low voltage.
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Protocol, runtime_checkable

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result import NodeResult
from gridflow.domain.util.params import as_params
from gridflow.usecase.result import ExperimentResult, StepResult, StepStatus


@dataclass(frozen=True)
class ControllableDevice:
    """A reactive-power-capable device (e.g. a PV inverter) the loop can steer.

    Attributes:
        device_id: Unique identifier used to key control actions.
        bus: Bus the device is attached to (the voltage it senses locally).
        kvar_limit: Maximum absolute reactive power (kvar) the device can
            source or sink; the strategy's action is clamped to
            ``[-kvar_limit, +kvar_limit]``.
    """

    device_id: str
    bus: str
    kvar_limit: float

    def __post_init__(self) -> None:
        if self.kvar_limit < 0:
            raise ValueError(f"ControllableDevice.kvar_limit must be >= 0, got {self.kvar_limit}")


@dataclass(frozen=True)
class ControlState:
    """What a strategy sees each control iteration: bus voltages + devices."""

    bus_voltages: tuple[tuple[str, float], ...]
    devices: tuple[ControllableDevice, ...]

    def voltage(self, bus: str) -> float:
        for name, value in self.bus_voltages:
            if name == bus:
                return value
        raise KeyError(bus)


@runtime_checkable
class ControlStrategy(Protocol):
    """A Volt-VAR control law: given the grid state, decide each device's kvar.

    Returns a mapping ``device_id -> kvar`` covering every device in the state.
    Pure and side-effect-free — the loop applies the actions to the grid.
    """

    name: str

    def decide(self, state: ControlState) -> dict[str, float]: ...


class NoControl:
    """Baseline: every device holds zero reactive power (unity power factor)."""

    name = "no_control"

    def decide(self, state: ControlState) -> dict[str, float]:
        return {d.device_id: 0.0 for d in state.devices}


class LocalDroop:
    """IEEE 1547-2018 piecewise-linear Volt-VAR droop on each device's *local* bus.

    The Q(V) curve (in the sign convention above) is::

        V <= v1            -> +kvar_limit         (inject, raise V)
        v1 < V < v2        -> linear + -> 0
        v2 <= V <= v3      -> 0                    (deadband)
        v3 < V < v4        -> linear 0 -> -
        V >= v4            -> -kvar_limit          (absorb, lower V)

    Defaults place the deadband at 0.98-1.02 pu with saturation at 0.95/1.05,
    matching a typical IEEE 1547 Category B setting.
    """

    name = "local_droop"

    def __init__(self, *, v1: float = 0.95, v2: float = 0.98, v3: float = 1.02, v4: float = 1.05) -> None:
        if not (v1 < v2 <= v3 < v4):
            raise ValueError(f"LocalDroop requires v1 < v2 <= v3 < v4, got {(v1, v2, v3, v4)}")
        self.v1, self.v2, self.v3, self.v4 = v1, v2, v3, v4

    def _fraction(self, voltage: float) -> float:
        """Signed fraction of kvar_limit in [-1, +1] for a local voltage."""
        if voltage <= self.v1:
            return 1.0
        if voltage < self.v2:
            return (self.v2 - voltage) / (self.v2 - self.v1)
        if voltage <= self.v3:
            return 0.0
        if voltage < self.v4:
            return -(voltage - self.v3) / (self.v4 - self.v3)
        return -1.0

    def decide(self, state: ControlState) -> dict[str, float]:
        return {d.device_id: self._fraction(state.voltage(d.bus)) * d.kvar_limit for d in state.devices}


@runtime_checkable
class GridModel(Protocol):
    """Minimal solver surface the control loop drives (engine-agnostic).

    Implemented by a live connector (OpenDSS/pandapower) or a fake grid in
    tests. ``solve`` returns whether the power flow converged.

    ``bus_voltages`` is the per-bus view the controller *senses* (worst-case
    per bus for OpenDSS); ``node_voltages`` is the finest-grained per-node view
    used to build the experiment result / metrics (all phases). For a
    single-node engine (pandapower) the two coincide.
    """

    def bus_voltages(self) -> tuple[tuple[str, float], ...]: ...

    def node_voltages(self) -> tuple[tuple[str, float], ...]: ...

    def set_reactive(self, device_id: str, kvar: float) -> None: ...

    def solve(self) -> bool: ...


@dataclass(frozen=True)
class ControlResult:
    """Outcome of a Volt-VAR control loop."""

    strategy: str
    iterations: int
    settled: bool
    converged: bool
    final_actions: tuple[tuple[str, float], ...]
    final_bus_voltages: tuple[tuple[str, float], ...]

    def to_dict(self) -> dict[str, object]:
        return {
            "strategy": self.strategy,
            "iterations": self.iterations,
            "settled": self.settled,
            "converged": self.converged,
            "final_actions": [[d, q] for d, q in self.final_actions],
            "final_bus_voltages": [[b, v] for b, v in self.final_bus_voltages],
        }


def run_volt_var(
    grid: GridModel,
    devices: Sequence[ControllableDevice],
    strategy: ControlStrategy,
    *,
    max_iters: int = 20,
    tol_kvar: float = 1e-3,
    relaxation: float = 1.0,
) -> ControlResult:
    """Iterate ``{solve -> sense -> decide -> apply -> re-solve}`` until the
    reactive setpoints settle (change by <= ``tol_kvar``) or ``max_iters``.

    The loop is deterministic and engine-agnostic. ``settled`` reports whether
    the setpoints converged within ``max_iters``; ``converged`` is the power
    flow's convergence at the final solve. Recording the iteration count is the
    honest signal a delay/latency study (issue #29 item 4) will read.

    ``relaxation`` in ``(0, 1]`` damps the update
    (``applied = prev + relaxation * (decided - prev)``). A memoryless droop
    applied at full step (``relaxation=1``) can bang-bang on a stiff feeder;
    ``relaxation < 1`` converges it to the droop's fixed point, the way a real
    inverter's response time damps the loop.
    """
    if not 0.0 < relaxation <= 1.0:
        raise ValueError(f"relaxation must be in (0, 1], got {relaxation}")
    device_tuple = tuple(devices)
    grid.solve()
    prev: dict[str, float] = {d.device_id: 0.0 for d in device_tuple}
    applied: dict[str, float] = dict(prev)
    converged = True
    settled = False
    iterations = 0
    for i in range(1, max_iters + 1):
        iterations = i
        state = ControlState(bus_voltages=grid.bus_voltages(), devices=device_tuple)
        decided = strategy.decide(state)
        applied = {d: prev.get(d, 0.0) + relaxation * (q - prev.get(d, 0.0)) for d, q in decided.items()}
        for device_id, kvar in applied.items():
            grid.set_reactive(device_id, kvar)
        converged = grid.solve()
        max_delta = max((abs(applied[d] - prev.get(d, 0.0)) for d in applied), default=0.0)
        if max_delta <= tol_kvar:
            settled = True
            break
        prev = dict(applied)

    return ControlResult(
        strategy=strategy.name,
        iterations=iterations,
        settled=settled,
        converged=converged,
        final_actions=tuple(sorted(applied.items())),
        final_bus_voltages=tuple(grid.bus_voltages()),
    )


def run_control_experiment(
    grid: GridModel,
    devices: Sequence[ControllableDevice],
    strategy: ControlStrategy,
    *,
    experiment_id: str,
    pack_id: str,
    connector: str,
    parameters: dict[str, object] | None = None,
    max_iters: int = 20,
    tol_kvar: float = 1e-3,
    relaxation: float = 1.0,
) -> ExperimentResult:
    """Run a control strategy and package the result as an :class:`ExperimentResult`.

    This is the bridge that puts a control *method* on the standard path: the
    returned result flows into ``benchmark`` / ``export paper`` exactly like a
    plain run, so a new strategy can be compared statistically against the
    reference strategies (issue #29). The control outcome (strategy, iteration
    count, settled flag, per-device final kvar) is recorded in the metadata
    parameters so it survives to the report.
    """
    control = run_volt_var(grid, devices, strategy, max_iters=max_iters, tol_kvar=tol_kvar, relaxation=relaxation)
    node_voltages = grid.node_voltages()
    voltages = tuple(v for _, v in node_voltages)
    status = StepStatus.SUCCESS if control.converged else StepStatus.ERROR
    step = StepResult(
        step_id=0,
        timestamp=datetime.now(tz=UTC),
        status=status,
        elapsed_ms=0.0,
        node_result=NodeResult(node_id="__network__", voltages=voltages),
        bus_voltages=node_voltages,
        error=None if control.converged else "control-loop final solve did not converge",
    )
    merged: dict[str, object] = dict(parameters or {})
    merged.update(
        {
            "control_strategy": strategy.name,
            "control_iterations": control.iterations,
            "control_settled": control.settled,
        }
    )
    for device_id, kvar in control.final_actions:
        merged[f"control_kvar_{device_id}"] = kvar
    metadata = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime.now(tz=UTC),
        scenario_pack_id=pack_id,
        connector=connector,
        parameters=as_params(merged),
    )
    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=metadata,
        steps=(step,),
        node_results=(NodeResult(node_id="__network__", voltages=voltages),),
    )


__all__ = [
    "ControlResult",
    "ControlState",
    "ControlStrategy",
    "ControllableDevice",
    "GridModel",
    "LocalDroop",
    "NoControl",
    "run_control_experiment",
    "run_volt_var",
]
