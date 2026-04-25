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
        # Phase 2 §5.1.3: if the pack references a CDL canonical network,
        # materialise it to a .dss script and use that instead of the
        # Phase 1 master_file. The ``cdl_network_file`` parameter takes
        # precedence because it is the solver-agnostic form every new
        # pack should use.
        cdl_file = get_param(pack.metadata.parameters, "cdl_network_file")
        cdl_script: str | None = None
        if isinstance(cdl_file, str) and cdl_file:
            cdl_script = self._compile_cdl_script(pack, cdl_file)
            master_label = f"cdl:{cdl_file}"
        else:
            # Fallback: the Phase 1 contract — a literal master_file under network_dir.
            master_name = str(get_param(pack.metadata.parameters, "master_file") or "IEEE13Nodeckt.dss")
            master_path = pack.network_dir / master_name
            if not master_path.exists():
                raise OpenDSSError(
                    f"Master DSS file not found: {master_path}",
                    context={"pack_id": pack.pack_id, "master": str(master_path)},
                )
            master_label = str(master_path)

        driver = self._load_driver()

        try:
            driver.Basic.ClearAll()
            if cdl_script is not None:
                # Feed the CDL-derived script line by line so a parse error in
                # one command does not swallow the following context.
                for line in cdl_script.splitlines():
                    stripped = line.strip()
                    if not stripped or stripped.startswith("!"):
                        continue
                    driver.Command(stripped)
            else:
                driver.Command(f"Redirect [{master_label}]")
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
                context={"pack_id": pack.pack_id, "master": master_label},
                cause=exc,
            ) from exc

        bus_names = tuple(driver.Circuit.AllBusNames())
        voltages = tuple(driver.Circuit.AllBusMagPu())
        self._state = _SolveState(
            driver=driver,
            master_file=master_label,
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
        kv_raw = get_param(pack.metadata.parameters, "pv_kv")
        kv = float(str(kv_raw)) if kv_raw is not None else 4.16
        phases_raw = get_param(pack.metadata.parameters, "pv_phases")
        phases = int(str(phases_raw)) if phases_raw is not None else 3
        conn_raw = get_param(pack.metadata.parameters, "pv_conn")
        conn = str(conn_raw) if conn_raw is not None else "Wye"
        cmd = (
            f"New Generator.PV_runtime bus1={bus_str} phases={phases} kv={kv} conn={conn} kW={kw_value} pf=1.0 Model=1"
        )
        driver.Command(cmd)

    @staticmethod
    def _compile_cdl_script(pack: ScenarioPack, cdl_file: str) -> str:
        """Resolve the pack's CDL YAML and render it to an OpenDSS script.

        Kept as a static helper so tests can exercise the CDL → .dss
        rendering path without a live DSS driver.
        """
        from pathlib import Path

        from gridflow.adapter.network.cdl_to_dss import cdl_to_dss
        from gridflow.adapter.network.cdl_yaml_loader import (
            CDLNetworkLoadError,
            load_cdl_network_from_yaml,
        )

        path = Path(cdl_file)
        if not path.is_absolute():
            path = pack.network_dir / cdl_file
        try:
            network = load_cdl_network_from_yaml(path)
        except CDLNetworkLoadError as exc:
            raise OpenDSSError(
                f"failed to load CDL network from {path}: {exc}",
                context={"pack_id": pack.pack_id, "cdl_file": str(path)},
                cause=exc,
            ) from exc
        return cdl_to_dss(network, circuit_name=pack.name)

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
