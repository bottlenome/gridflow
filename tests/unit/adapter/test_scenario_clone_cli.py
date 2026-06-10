"""Tests for ``gridflow scenario clone`` and baseline YAML fields (AS-5 (1))."""

from __future__ import annotations

from pathlib import Path

import pytest
from typer.testing import CliRunner

from gridflow.adapter.cli.app import app
from gridflow.infra.scenario import load_pack_from_yaml

runner = CliRunner()

_BASELINE_YAML = """
pack:
  name: ieee13-baseline
  version: "1.0.0"
  description: official baseline
  author: gridflow
  connector: opendss
  seed: 42
  baseline: true
  citation: "Doe et al., IEEE PES GM 2025"
"""


@pytest.fixture()
def gridflow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".gridflow"
    monkeypatch.setenv("GRIDFLOW_HOME", str(home))
    return home


def _register_baseline(tmp_path: Path) -> str:
    yaml_path = tmp_path / "pack.yaml"
    yaml_path.write_text(_BASELINE_YAML, encoding="utf-8")
    result = runner.invoke(app, ["scenario", "register", str(yaml_path)])
    assert result.exit_code == 0, result.output
    return "ieee13-baseline@1.0.0"


class TestYamlBaselineFields:
    def test_loader_parses_baseline_and_citation(self, tmp_path: Path) -> None:
        yaml_path = tmp_path / "pack.yaml"
        yaml_path.write_text(_BASELINE_YAML, encoding="utf-8")
        pack = load_pack_from_yaml(yaml_path)
        assert pack.metadata.baseline is True
        assert pack.metadata.citation == "Doe et al., IEEE PES GM 2025"


class TestScenarioClone:
    def test_clone_registers_derivative(self, gridflow_home: Path, tmp_path: Path) -> None:
        pack_id = _register_baseline(tmp_path)
        result = runner.invoke(app, ["scenario", "clone", pack_id, "--id", "my-method@0.1.0"])
        assert result.exit_code == 0, result.output
        assert "my-method@0.1.0" in result.output

        get_result = runner.invoke(app, ["scenario", "get", "my-method@0.1.0"])
        assert get_result.exit_code == 0
        assert f"cloned_from: {pack_id}" in get_result.output  # provenance
        assert "baseline: False" in get_result.output

    def test_clone_round_trips_through_registry(self, gridflow_home: Path, tmp_path: Path) -> None:
        pack_id = _register_baseline(tmp_path)
        runner.invoke(app, ["scenario", "clone", pack_id, "--id", "my-method@0.1.0"])
        # Original keeps its baseline flag and citation after the clone.
        get_original = runner.invoke(app, ["scenario", "get", pack_id])
        assert "baseline: True" in get_original.output
        assert "IEEE PES GM 2025" in get_original.output

    def test_clone_missing_pack_fails(self, gridflow_home: Path) -> None:
        result = runner.invoke(app, ["scenario", "clone", "nope", "--id", "x@1"])
        assert result.exit_code == 1
        assert "not found" in result.output.lower()

    def test_clone_same_id_fails(self, gridflow_home: Path, tmp_path: Path) -> None:
        pack_id = _register_baseline(tmp_path)
        result = runner.invoke(app, ["scenario", "clone", pack_id, "--id", pack_id])
        assert result.exit_code == 1
        assert "differ" in result.output
