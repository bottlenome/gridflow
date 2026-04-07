"""End-to-end run through the CLI against the real OpenDSS IEEE 13 pack.

Gated behind the ``spike`` marker so the regular ``pytest -m "not spike"``
sweep skips it when OpenDSS is unavailable.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

from gridflow.adapter.cli.app import app

runner = CliRunner()

EXAMPLES_DIR = Path(__file__).parent.parent.parent / "examples" / "ieee13"


@pytest.mark.spike
def test_ieee13_e2e_cli(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    pytest.importorskip("opendssdirect")

    monkeypatch.setenv("GRIDFLOW_HOME", str(tmp_path / ".gridflow"))

    yaml_path = EXAMPLES_DIR / "pack.yaml"
    assert yaml_path.exists()

    reg = runner.invoke(app, ["scenario", "register", str(yaml_path)])
    assert reg.exit_code == 0, reg.output

    run = runner.invoke(app, ["run", "ieee13@1.0.0", "--steps", "2", "--format", "json"])
    assert run.exit_code == 0, run.output

    payload = json.loads(run.stdout)
    assert payload["steps"] == 2

    experiment_id = payload["experiment_id"]
    results = runner.invoke(app, ["results", experiment_id, "--format", "json"])
    assert results.exit_code == 0
    data = json.loads(results.stdout)
    assert data["metadata"]["scenario_pack_id"] == "ieee13@1.0.0"
    assert len(data["steps"]) == 2
