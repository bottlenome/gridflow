"""Tests for ``PandaPowerConnector``.

Spec: ``docs/phase1_result.md`` §7.13.1 (機能 B).

These tests use the real ``pandapower`` package because pandapower's
power flow is fast and deterministic; mocking the whole solver would
duplicate too much logic. Tests are skipped if pandapower is not
installed (so the rest of the suite still runs in a minimal env).

Pack ``parameters`` shape consumed by the connector:

.. code-block:: yaml

    parameters:
      pp_network: simple_mv_open_ring_net    # built-in factory name
      pv_bus: 3                              # bus index for the PV
      pv_kw: 500                             # PV power, kW

If ``pv_kw`` is 0 or absent the connector skips PV creation. If
``pp_network`` is missing the connector raises ``ConnectorError``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

pp = pytest.importorskip("pandapower")

from gridflow.adapter.connector.pandapower import PandaPowerConnector  # noqa: E402
from gridflow.domain.error import ConnectorError  # noqa: E402
from gridflow.domain.scenario import PackMetadata, ScenarioPack  # noqa: E402
from gridflow.domain.util.params import as_params  # noqa: E402


def _pack(parameters: dict[str, object]) -> ScenarioPack:
    meta = PackMetadata(
        name="test",
        version="1.0.0",
        description="t",
        author="t",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="pandapower",
        parameters=as_params(parameters),
    )
    return ScenarioPack(
        pack_id="test@1.0.0",
        name="test",
        version="1.0.0",
        metadata=meta,
        network_dir=Path("/tmp"),
        timeseries_dir=Path("/tmp"),
        config_dir=Path("/tmp"),
    )


class TestPandaPowerConnectorLifecycle:
    def test_initialize_loads_named_network(self) -> None:
        connector = PandaPowerConnector()
        connector.initialize(_pack({"pp_network": "simple_mv_open_ring_net"}))
        try:
            output = connector.step(0)
        finally:
            connector.teardown()
        assert output.converged is True
        assert output.node_result is not None
        assert len(output.node_result.voltages) > 0
        # Range A sanity: bus voltages should be near 1.0 pu for a healthy
        # base test network with no PV.
        assert all(0.9 < v < 1.1 for v in output.node_result.voltages)

    def test_initialize_missing_pp_network_raises(self) -> None:
        connector = PandaPowerConnector()
        with pytest.raises(ConnectorError, match="pp_network"):
            connector.initialize(_pack({}))

    def test_initialize_unknown_factory_raises(self) -> None:
        connector = PandaPowerConnector()
        with pytest.raises(ConnectorError, match="not a known"):
            connector.initialize(_pack({"pp_network": "no_such_factory"}))

    def test_step_before_initialize_raises(self) -> None:
        connector = PandaPowerConnector()
        with pytest.raises(ConnectorError, match="initialize"):
            connector.step(0)

    def test_pv_insertion_changes_voltages(self) -> None:
        """Adding a PV via parameters should not crash and (for a healthy
        feeder) yield a different voltage profile than the baseline."""
        baseline = PandaPowerConnector()
        baseline.initialize(_pack({"pp_network": "simple_mv_open_ring_net"}))
        try:
            v_base = baseline.step(0).node_result.voltages
        finally:
            baseline.teardown()

        with_pv = PandaPowerConnector()
        with_pv.initialize(
            _pack(
                {
                    "pp_network": "simple_mv_open_ring_net",
                    "pv_bus": 3,
                    "pv_kw": 1000.0,
                }
            )
        )
        try:
            v_pv = with_pv.step(0).node_result.voltages
        finally:
            with_pv.teardown()

        assert v_base != v_pv

    def test_pv_bus_out_of_range_raises(self) -> None:
        connector = PandaPowerConnector()
        with pytest.raises(ConnectorError, match="pv_bus"):
            connector.initialize(
                _pack(
                    {
                        "pp_network": "simple_mv_open_ring_net",
                        "pv_bus": 99999,
                        "pv_kw": 100.0,
                    }
                )
            )

    def test_teardown_resets_state(self) -> None:
        connector = PandaPowerConnector()
        connector.initialize(_pack({"pp_network": "simple_mv_open_ring_net"}))
        connector.step(0)
        connector.teardown()
        with pytest.raises(ConnectorError, match="initialize"):
            connector.step(0)

    def test_reproducibility(self) -> None:
        """Same pack run twice yields identical voltages."""
        a = PandaPowerConnector()
        a.initialize(_pack({"pp_network": "simple_mv_open_ring_net", "pv_kw": 200, "pv_bus": 3}))
        v1 = a.step(0).node_result.voltages
        a.teardown()

        b = PandaPowerConnector()
        b.initialize(_pack({"pp_network": "simple_mv_open_ring_net", "pv_kw": 200, "pv_bus": 3}))
        v2 = b.step(0).node_result.voltages
        b.teardown()

        assert v1 == v2
