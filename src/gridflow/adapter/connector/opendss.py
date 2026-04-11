"""OpenDSS connector built on ``OpenDSSDirect.py``.

The heavy-weight ``opendssdirect`` module is imported lazily inside
:meth:`OpenDSSConnector.initialize` so the package can be imported — and unit
tests can run — in environments where OpenDSS is not available.

The connector drives a *single* master ``.dss`` file found at
``pack.network_dir / metadata.parameters["master_file"]`` (falling back to
``IEEE13Nodeckt.dss`` for MVP packs that omit that hint).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gridflow.domain.error import OpenDSSError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import ScenarioPack
from gridflow.domain.util.params import get_param, params_to_dict
from gridflow.usecase.interfaces import ConnectorInterface, ConnectorStepOutput

if TYPE_CHECKING:
    from types import ModuleType


@dataclass
class _SolveState:
    """Mutable per-experiment state owned by the connector."""

    driver: ModuleType | Any
    master_file: str
    bus_names: tuple[str, ...]
    last_voltages: tuple[float, ...]


class OpenDSSConnector(ConnectorInterface):
    """Synchronous OpenDSS connector for power-flow runs.

    The connector keeps a single :class:`_SolveState` between ``initialize``
    and ``teardown``. It is *not* thread-safe — one instance per experiment.
    """

    name = "opendss"

    def __init__(self) -> None:
        self._state: _SolveState | None = None

    # ------------------------------------------------------------------ life

    def initialize(self, pack: ScenarioPack) -> None:
        # Resolve the master file first so missing-file errors don't require
        # ``opendssdirect`` to be installed (simplifies unit testing).
        master_name = str(get_param(pack.metadata.parameters, "master_file") or "IEEE13Nodeckt.dss")
        master_path = pack.network_dir / master_name
        if not master_path.exists():
            raise OpenDSSError(
                f"Master DSS file not found: {master_path}",
                context={"pack_id": pack.pack_id, "master": str(master_path)},
            )

        driver = self._load_driver()

        try:
            driver.Basic.ClearAll()
            driver.Command(f"Redirect [{master_path}]")
            self._inject_runtime_pv(driver, pack)
            driver.Command("Solve")
            if not driver.Solution.Converged():
                raise OpenDSSError(
                    "OpenDSS power flow did not converge during initialization",
                    context={"pack_id": pack.pack_id},
                )
        except OpenDSSError:
            raise
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise OpenDSSError(
                f"OpenDSS initialization failed: {exc}",
                context={"pack_id": pack.pack_id, "master": str(master_path)},
                cause=exc,
            ) from exc

        bus_names = tuple(driver.Circuit.AllBusNames())
        voltages = tuple(driver.Circuit.AllBusMagPu())
        self._state = _SolveState(
            driver=driver,
            master_file=str(master_path),
            bus_names=bus_names,
            last_voltages=voltages,
        )

    def step(self, step_index: int) -> ConnectorStepOutput:
        state = self._require_state()
        driver = state.driver
        try:
            driver.Command("Solve")
            converged = bool(driver.Solution.Converged())
            voltages = tuple(driver.Circuit.AllBusMagPu())
        except Exception as exc:  # pragma: no cover - driver-specific failures
            raise OpenDSSError(
                f"OpenDSS solve failed at step {step_index}: {exc}",
                context={"step": step_index},
                cause=exc,
            ) from exc

        state.last_voltages = voltages
        # Aggregate into a single "network" NodeResult — callers can reach
        # individual bus voltages through ``metadata``.
        meta = {"bus_names": state.bus_names}
        node_result = NodeResult(node_id="__network__", voltages=voltages)
        return ConnectorStepOutput(
            step=step_index,
            node_result=node_result,
            converged=converged,
            metadata=tuple(sorted(meta.items())),
        )

    def teardown(self) -> None:
        if self._state is None:
            return
        with contextlib.suppress(Exception):  # pragma: no cover - best-effort cleanup
            self._state.driver.Basic.ClearAll()
        self._state = None

    # ----------------------------------------------------------------- helpers

    def latest_voltages(self) -> tuple[float, ...]:
        """Return the most recent voltage vector, or empty if uninitialised."""
        return self._state.last_voltages if self._state else ()

    def bus_names(self) -> tuple[str, ...]:
        return self._state.bus_names if self._state else ()

    def pack_parameters(self, pack: ScenarioPack) -> dict[str, object]:
        return params_to_dict(pack.metadata.parameters)

    def _require_state(self) -> _SolveState:
        if self._state is None:
            raise OpenDSSError("OpenDSSConnector.step called before initialize")
        return self._state

    @staticmethod
    def _inject_runtime_pv(driver: ModuleType | Any, pack: ScenarioPack) -> None:
        """If the pack carries ``pv_bus`` + ``pv_kw`` parameters, attach a
        runtime ``Generator.PV_runtime`` element to the loaded circuit.

        This is the OpenDSS analogue of pandapower's ``create_sgen`` and
        lets stochastic HCA sweeps reuse a single base ``.dss`` file
        while varying placement / capacity through pack parameters.

        Parameters consumed:
            pv_bus : str   — bus name (OpenDSS uses string identifiers)
            pv_kw  : float — PV active power, kW
            pv_kv  : float — line-to-line nominal voltage, kV (default 4.16)
            pv_phases : int — phase count (default 3)
            pv_conn : str  — "Wye" | "Delta" (default Wye)

        If ``pv_kw`` is missing or 0, no element is created.
        """
        pv_kw_raw = get_param(pack.metadata.parameters, "pv_kw")
        if pv_kw_raw is None:
            return
        try:
            kw_value = float(pv_kw_raw)  # type: ignore[arg-type]
        except (TypeError, ValueError):
            return
        if kw_value <= 0:
            return

        pv_bus = get_param(pack.metadata.parameters, "pv_bus")
        if pv_bus is None:
            raise OpenDSSError(
                "pv_kw is set but pv_bus is missing — OpenDSS needs a target bus name to attach the runtime PV",
                context={"pack_id": pack.pack_id},
            )
        bus_str = str(pv_bus)
        kv = float(get_param(pack.metadata.parameters, "pv_kv") or 4.16)  # type: ignore[arg-type]
        phases = int(get_param(pack.metadata.parameters, "pv_phases") or 3)  # type: ignore[arg-type]
        conn = str(get_param(pack.metadata.parameters, "pv_conn") or "Wye")
        cmd = (
            f"New Generator.PV_runtime bus1={bus_str} phases={phases} kv={kv} conn={conn} kW={kw_value} pf=1.0 Model=1"
        )
        driver.Command(cmd)

    def _load_driver(self) -> ModuleType | Any:
        try:
            import opendssdirect
        except ImportError as exc:
            raise OpenDSSError(
                "OpenDSSDirect.py is not installed. "
                "Install with `pip install OpenDSSDirect.py` or `uv sync --extra opendss`.",
                cause=exc,
            ) from exc
        return opendssdirect
