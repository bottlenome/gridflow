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


@pytest.mark.spike
def test_ieee13_control_cli_strategy_comparison(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    """`gridflow control` runs each strategy on the real feeder and the result
    flows onto the standard path (results/benchmark) — the method-comparison
    loop try17 found the framework could not close.
    """
    pytest.importorskip("opendssdirect")
    monkeypatch.setenv("GRIDFLOW_HOME", str(tmp_path / ".gridflow"))

    reg = runner.invoke(app, ["scenario", "register", str(EXAMPLES_DIR / "pack.yaml")])
    assert reg.exit_code == 0, reg.output

    common = ["--pv-bus", "675.1.2.3", "--pv-kw", "9000", "--kvar-limit", "5000", "--freeze-regulators"]
    none = runner.invoke(app, ["control", "ieee13@1.0.0", "--strategy", "no_control", "--format", "json", *common])
    droop = runner.invoke(
        app,
        [
            "control",
            "ieee13@1.0.0",
            "--strategy",
            "local_droop",
            "--relaxation",
            "0.3",
            "--max-iters",
            "60",
            "--format",
            "json",
            *common,
        ],
    )
    assert none.exit_code == 0, none.output
    assert droop.exit_code == 0, droop.output

    none_out = json.loads(none.stdout)
    droop_out = json.loads(droop.stdout)
    # 9 MW PV over-volts the bus; the pluggable strategy absorbs vars and clears it.
    assert none_out["vmax"] > 1.05
    assert droop_out["vmax"] <= 1.05
    assert droop_out["final_kvar"] < 0.0

    # The saved control results score on the standard benchmark path.
    bench = runner.invoke(
        app,
        [
            "benchmark",
            "--baseline",
            none_out["experiment_id"],
            "--candidate",
            droop_out["experiment_id"],
            "--format",
            "json",
        ],
    )
    assert bench.exit_code == 0, bench.output
    assert "voltage_violation_rate" in bench.stdout
