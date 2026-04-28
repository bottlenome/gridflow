"""pandapower connector — second concrete ``ConnectorInterface`` implementation.

Spec: ``docs/phase1_result.md`` §7.13.1 (機能 B), ``docs/mvp_scenario_v2.md`` §5.

Pack ``parameters`` consumed by this connector:

    pp_network : str   — name of a built-in pandapower network factory
                         exported by ``pandapower.networks`` (e.g.
                         ``simple_mv_open_ring_net`` or ``case_ieee30``).
    pv_bus     : int   — optional, the bus index where a static generator
                         representing a PV is added before the power flow.
    pv_kw      : float — optional, the PV active power in kW. If 0 or
                         absent, no PV is added (baseline).

Why a Python factory rather than a .dss file?
    pandapower 3.4 ships without an OpenDSS converter (``from_dss``) so
    a fully-canonical CDL input would be needed for true cross-solver
    sharing. That is REQ-F-003 expansion territory and explicitly
    Phase 2 scope. For Phase 1 we use pandapower's *built-in* test
    networks: any researcher can copy a sweep over to pandapower simply
    by writing one pack.yaml referring to e.g. ``case_ieee30``. The
    sweep / metric / aggregator pipeline above is unchanged.

The connector is intentionally symmetric to ``OpenDSSConnector``:
    initialize(pack)  → load network + optional PV
    step(step_index)  → run power flow + emit voltages
    teardown()        → drop the network handle

It is *not* a translator from CDL to pandapower (that is Phase 2).
"""

from __future__ import annotations

import contextlib
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from gridflow.domain.error import ConnectorError
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import ScenarioPack
from gridflow.domain.util.params import get_param
from gridflow.usecase.interfaces import ConnectorInterface, ConnectorStepOutput

if TYPE_CHECKING:
    from types import ModuleType


@dataclass
class _SolveState:
    """Mutable per-experiment state owned by the connector."""

    pp: Any
    net: Any
    pp_network_name: str


class PandaPowerConnector(ConnectorInterface):
    """Synchronous pandapower connector for power-flow runs.

    The connector keeps a single :class:`_SolveState` between
    :meth:`initialize` and :meth:`teardown`. Like ``OpenDSSConnector``
    it is *not* thread-safe — instantiate one per experiment.
    """

    name = "pandapower"

    def __init__(self) -> None:
        self._state: _SolveState | None = None

    # ------------------------------------------------------------------ life

    def initialize(self, pack: ScenarioPack) -> None:
        # Phase 2 §5.1.3: prefer CDL canonical input when the pack carries
        # one; fall back to the Phase 1 ``pp_network`` factory otherwise.
        cdl_file = get_param(pack.metadata.parameters, "cdl_network_file")
        pp_network = get_param(pack.metadata.parameters, "pp_network")

        pp = self._load_pandapower()
        if isinstance(cdl_file, str) and cdl_file:
            net = self._build_from_cdl(pack, cdl_file)
            pp_network_label = f"cdl:{cdl_file}"
        elif isinstance(pp_network, str) and pp_network:
            net = self._call_factory(pp, pp_network, pack.pack_id)
            pp_network_label = pp_network
        else:
            raise ConnectorError(
                "pandapower pack requires either a 'cdl_network_file' parameter "
                "(path to a CDL network YAML) or a 'pp_network' parameter "
                "(name of a pandapower.networks factory)",
                context={"pack_id": pack.pack_id},
            )

        # Optional PV insertion via static generator (sgen).
        pv_kw = get_param(pack.metadata.parameters, "pv_kw")
        if pv_kw is not None:
            pv_bus = get_param(pack.metadata.parameters, "pv_bus")
            if pv_bus is None:
                raise ConnectorError(
                    "pv_kw is set but pv_bus is missing — pandapower needs a target bus index to attach the PV",
                    context={"pack_id": pack.pack_id},
                )
            try:
                bus_idx = int(str(pv_bus))
                kw_value = float(str(pv_kw))
            except (TypeError, ValueError) as exc:
                raise ConnectorError(
                    f"invalid pv_bus / pv_kw types: {exc}",
                    context={"pack_id": pack.pack_id, "pv_bus": pv_bus, "pv_kw": pv_kw},
                    cause=exc,
                ) from exc
            if bus_idx not in net.bus.index:
                raise ConnectorError(
                    f"pv_bus {bus_idx} is not in the network bus index "
                    f"(known: {list(net.bus.index)[:10]}{'...' if len(net.bus.index) > 10 else ''})",
                    context={"pack_id": pack.pack_id, "pv_bus": bus_idx},
                )
            if kw_value > 0:
                pp.create_sgen(
                    net,
                    bus=bus_idx,
                    p_mw=kw_value / 1000.0,
                    name=f"pv_{bus_idx}",
                    type="PV",
                )

        self._state = _SolveState(pp=pp, net=net, pp_network_name=pp_network_label)

    def step(self, step_index: int) -> ConnectorStepOutput:
        state = self._require_state()
        pp = state.pp
        try:
            pp.runpp(state.net)
        except Exception as exc:  # pragma: no cover - solver-specific failures
            raise ConnectorError(
                f"pandapower runpp failed at step {step_index}: {exc}",
                context={"step": step_index},
                cause=exc,
            ) from exc

        voltages = tuple(float(v) for v in state.net.res_bus.vm_pu.tolist())
        node_result = NodeResult(node_id="__network__", voltages=voltages)
        return ConnectorStepOutput(
            step=step_index,
            node_result=node_result,
            converged=True,
            metadata=(("pp_network", state.pp_network_name),),
        )

    def teardown(self) -> None:
        if self._state is None:
            return
        with contextlib.suppress(Exception):
            self._state.net = None
        self._state = None

    # ----------------------------------------------------------------- helpers

    def _require_state(self) -> _SolveState:
        if self._state is None:
            raise ConnectorError("PandaPowerConnector.step called before initialize")
        return self._state

    @staticmethod
    def _build_from_cdl(pack: ScenarioPack, cdl_file: str) -> Any:
        """Build a pandapower network from a CDL YAML referenced by the pack.

        Resolves ``cdl_file`` relative to the pack's ``network_dir`` so
        packs stay self-contained (alongside ``.dss`` files used by the
        OpenDSS connector). Delegates to
        :meth:`PandapowerTranslator.from_canonical` (spec-aligned
        bidirectional surface — 03b §3.5.4a).
        """
        from pathlib import Path

        from gridflow.adapter.connector.pandapower_translator import PandapowerTranslator
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
            raise ConnectorError(
                f"failed to load CDL network from {path}: {exc}",
                context={"pack_id": pack.pack_id, "cdl_file": str(path)},
                cause=exc,
            ) from exc
        return PandapowerTranslator.from_canonical(network)

    @staticmethod
    def _load_pandapower() -> Any:
        try:
            import pandapower as pp
        except ImportError as exc:
            raise ConnectorError(
                "pandapower is not installed. Install with `pip install pandapower` or `pip install -e .[pandapower]`",
                cause=exc,
            ) from exc
        return pp

    @staticmethod
    def _call_factory(pp: ModuleType | Any, factory_name: str, pack_id: str) -> Any:
        try:
            import pandapower.networks as pp_nets
        except ImportError as exc:
            raise ConnectorError(
                "pandapower.networks is unavailable",
                context={"pack_id": pack_id},
                cause=exc,
            ) from exc
        factory = getattr(pp_nets, factory_name, None)
        if factory is None:
            raise ConnectorError(
                f"'{factory_name}' is not a known pandapower.networks factory",
                context={"pack_id": pack_id, "factory": factory_name},
            )
        try:
            return factory()
        except Exception as exc:
            raise ConnectorError(
                f"pandapower.networks.{factory_name}() raised: {exc}",
                context={"pack_id": pack_id, "factory": factory_name},
                cause=exc,
            ) from exc
