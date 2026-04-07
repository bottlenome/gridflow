"""Tests for OpenDSSConnector that don't require the real solver.

Real-solver integration is covered by ``tests/spike/test_opendss_smoke.py``
(gated behind the ``spike`` marker). Here we exercise the fallback/error paths
that are independent of the OpenDSSDirect driver.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from unittest.mock import MagicMock

import pytest

from gridflow.adapter.connector import OpenDSSConnector
from gridflow.domain.error import OpenDSSError
from gridflow.domain.scenario import PackMetadata, ScenarioPack


def _pack(tmp_path: Path, master_file: str | None = None) -> ScenarioPack:
    from gridflow.domain.util.params import as_params

    params = as_params({"master_file": master_file}) if master_file else ()
    meta = PackMetadata(
        name="t",
        version="1.0.0",
        description="d",
        author="a",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
        parameters=params,
    )
    return ScenarioPack(
        pack_id="t@1",
        name="t",
        version="1.0.0",
        metadata=meta,
        network_dir=tmp_path,
        timeseries_dir=tmp_path,
        config_dir=tmp_path,
    )


class TestOpenDSSConnectorErrors:
    def test_missing_master_file_raises(self, tmp_path: Path) -> None:
        connector = OpenDSSConnector()
        with pytest.raises(OpenDSSError, match="Master DSS file not found"):
            connector.initialize(_pack(tmp_path, master_file="nope.dss"))

    def test_step_before_initialize_raises(self) -> None:
        connector = OpenDSSConnector()
        with pytest.raises(OpenDSSError, match="before initialize"):
            connector.step(0)

    def test_initialize_uses_injected_driver(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Use a mock OpenDSS driver so the test runs without the real solver."""
        driver = MagicMock()
        driver.Solution.Converged.return_value = True
        driver.Circuit.AllBusNames.return_value = ["650", "632"]
        driver.Circuit.AllBusMagPu.return_value = [1.0, 0.99]

        connector = OpenDSSConnector()
        monkeypatch.setattr(connector, "_load_driver", lambda: driver)

        (tmp_path / "feeder.dss").write_text("! master", encoding="utf-8")
        connector.initialize(_pack(tmp_path, master_file="feeder.dss"))
        assert connector.bus_names() == ("650", "632")
        assert connector.latest_voltages() == (1.0, 0.99)

        out = connector.step(0)
        assert out.converged
        assert out.node_result is not None
        assert out.node_result.voltages == (1.0, 0.99)

        connector.teardown()
        assert connector.latest_voltages() == ()
