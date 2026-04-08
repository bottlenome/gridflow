"""Tests for the typer CLI using typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gridflow.adapter.cli.app import app

runner = CliRunner()


def _write_pack_yaml(target: Path) -> Path:
    target.write_text(
        """
pack:
  name: demo
  version: "1.0.0"
  description: demo
  author: tester
  connector: opendss
""",
        encoding="utf-8",
    )
    return target


@pytest.fixture()
def gridflow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".gridflow"
    monkeypatch.setenv("GRIDFLOW_HOME", str(home))
    return home


class TestScenarioCommands:
    def test_register_and_list(self, gridflow_home: Path, tmp_path: Path) -> None:
        yaml_path = _write_pack_yaml(tmp_path / "pack.yaml")
        result = runner.invoke(app, ["scenario", "register", str(yaml_path)])
        assert result.exit_code == 0, result.output
        assert "demo@1.0.0" in result.output

        list_result = runner.invoke(app, ["scenario", "list"])
        assert list_result.exit_code == 0
        assert "demo@1.0.0" in list_result.output

    def test_get_missing_returns_nonzero(self, gridflow_home: Path) -> None:
        result = runner.invoke(app, ["scenario", "get", "nope"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_register_with_custom_id(self, gridflow_home: Path, tmp_path: Path) -> None:
        yaml_path = _write_pack_yaml(tmp_path / "pack.yaml")
        result = runner.invoke(app, ["scenario", "register", str(yaml_path), "--id", "custom-id"])
        assert result.exit_code == 0
        assert "custom-id" in result.output


class TestRunCommand:
    def test_run_uses_injected_connector_factory(
        self, gridflow_home: Path, tmp_path: Path, monkeypatch: pytest.MonkeyPatch
    ) -> None:
        """Patch the default factory so ``run`` exercises end-to-end logic
        without touching OpenDSS."""
        from tests.unit.usecase.test_orchestrator import FakeConnector

        # First register a pack so the orchestrator can find it.
        yaml_path = _write_pack_yaml(tmp_path / "pack.yaml")
        reg_result = runner.invoke(app, ["scenario", "register", str(yaml_path)])
        assert reg_result.exit_code == 0, reg_result.output

        import gridflow.adapter.cli.app as cli_module

        monkeypatch.setattr(cli_module, "_default_connector_factory", lambda name: FakeConnector())

        result = runner.invoke(app, ["run", "demo@1.0.0", "--steps", "2", "--connector", "fake"])
        assert result.exit_code == 0, result.output
        assert "experiment_id" in result.output

    def test_run_missing_pack(self, gridflow_home: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        import gridflow.adapter.cli.app as cli_module
        from tests.unit.usecase.test_orchestrator import FakeConnector

        monkeypatch.setattr(cli_module, "_default_connector_factory", lambda name: FakeConnector())

        result = runner.invoke(app, ["run", "nope", "--connector", "fake"])
        assert result.exit_code == 1
