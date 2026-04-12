"""Tests for the typer CLI using typer.testing.CliRunner."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gridflow.adapter.cli.app import app, build_runner_from_env

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


class TestRunnerSelection:
    """Unit 5: ``GRIDFLOW_RUNNER`` env var selects in-process vs container."""

    def test_default_runner_is_inprocess(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from gridflow.infra.orchestrator import InProcessOrchestratorRunner

        monkeypatch.delenv("GRIDFLOW_RUNNER", raising=False)

        def _factory(name: str):
            from tests.unit.usecase.test_orchestrator import FakeConnector

            return FakeConnector()

        chosen = build_runner_from_env(connector="fake", connector_factory=_factory)
        assert isinstance(chosen, InProcessOrchestratorRunner)

    def test_inprocess_selected_explicitly(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from gridflow.infra.orchestrator import InProcessOrchestratorRunner

        monkeypatch.setenv("GRIDFLOW_RUNNER", "inprocess")

        def _factory(name: str):
            from tests.unit.usecase.test_orchestrator import FakeConnector

            return FakeConnector()

        chosen = build_runner_from_env(connector="fake", connector_factory=_factory)
        assert isinstance(chosen, InProcessOrchestratorRunner)

    def test_container_runner_selected_by_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from gridflow.infra.container_manager import NoOpContainerManager
        from gridflow.infra.orchestrator import ContainerOrchestratorRunner

        monkeypatch.setenv("GRIDFLOW_RUNNER", "container")
        monkeypatch.setenv(
            "GRIDFLOW_CONNECTOR_ENDPOINTS",
            "opendss=opendss-connector@http://opendss-connector:8000",
        )

        chosen = build_runner_from_env(
            connector="opendss",
            connector_factory=lambda _: None,  # unused for container mode
        )
        assert isinstance(chosen, ContainerOrchestratorRunner)
        # Inside docker-compose the CLI should use NoOpContainerManager —
        # services are managed externally by depends_on healthchecks.
        assert isinstance(chosen._manager, NoOpContainerManager)  # type: ignore[attr-defined]

    def test_container_runner_requires_endpoints_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from gridflow.domain.error import ConfigError

        monkeypatch.setenv("GRIDFLOW_RUNNER", "container")
        monkeypatch.delenv("GRIDFLOW_CONNECTOR_ENDPOINTS", raising=False)

        with pytest.raises(ConfigError):
            build_runner_from_env(
                connector="opendss",
                connector_factory=lambda _: None,
            )

    def test_unknown_runner_name_raises(self, monkeypatch: pytest.MonkeyPatch) -> None:
        from gridflow.domain.error import ConfigError

        monkeypatch.setenv("GRIDFLOW_RUNNER", "martian")
        with pytest.raises(ConfigError):
            build_runner_from_env(
                connector="opendss",
                connector_factory=lambda _: None,
            )


class TestSweepCommand:
    """Unit A-iii: ``gridflow sweep --plan ...`` end-to-end through CliRunner."""

    def test_sweep_runs_with_yaml_plan(
        self,
        gridflow_home: Path,
        tmp_path: Path,
        monkeypatch: pytest.MonkeyPatch,
    ) -> None:
        from tests.unit.usecase.test_orchestrator import FakeConnector

        # 1. Register the base pack the sweep will derive children from.
        yaml_path = _write_pack_yaml(tmp_path / "pack.yaml")
        reg = runner.invoke(app, ["scenario", "register", str(yaml_path)])
        assert reg.exit_code == 0, reg.output

        # 2. Patch the default factory so the sweep uses an in-memory connector.
        import gridflow.adapter.cli.app as cli_module

        monkeypatch.setattr(cli_module, "_default_connector_factory", lambda _: FakeConnector())

        # 3. Build a sweep plan against the registered pack.
        plan_path = tmp_path / "sweep.yaml"
        plan_path.write_text(
            """
sweep:
  id: cli_smoke
  base_pack_id: demo@1.0.0
  aggregator: statistics
  seed: 42
axes:
  - name: pv_kw
    type: range
    start: 100
    stop: 400
    step: 100
""",
            encoding="utf-8",
        )

        out_path = tmp_path / "sweep_result.json"
        result = runner.invoke(
            app,
            [
                "sweep",
                "--plan",
                str(plan_path),
                "--connector",
                "fake",
                "--output",
                str(out_path),
                "--format",
                "json",
            ],
        )
        assert result.exit_code == 0, result.output
        assert out_path.exists()
        payload = json.loads(out_path.read_text())
        assert payload["sweep_id"] == "cli_smoke"
        assert payload["base_pack_id"] == "demo@1.0.0"
        assert len(payload["experiment_ids"]) == 3  # 100, 200, 300
        assert "voltage_deviation_mean" in payload["aggregated_metrics"]

    def test_sweep_missing_plan_file_fails(
        self,
        gridflow_home: Path,
        tmp_path: Path,
    ) -> None:
        result = runner.invoke(
            app,
            ["sweep", "--plan", str(tmp_path / "nope.yaml"), "--connector", "opendss"],
        )
        # exit_code != 0 (typer Argument with exists=True returns 2 for the
        # missing file).
        assert result.exit_code != 0


# json import for the new test class
import json  # noqa: E402  -- placed here to keep test_cli history-clean for pre-sweep tests
