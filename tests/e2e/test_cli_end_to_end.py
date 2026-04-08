"""End-to-end CLI test: register → run → results → benchmark.

Uses a :class:`DeterministicFakeConnector` so the test runs in CI without
OpenDSS. The real OpenDSS path is exercised by ``tests/spike/test_opendss_smoke.py``
and the opt-in ``test_opendss_e2e.py`` in this directory.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest
from typer.testing import CliRunner

import gridflow.adapter.cli.app as cli_module
from gridflow.adapter.cli.app import app
from gridflow.domain.result import NodeResult
from gridflow.domain.scenario import ScenarioPack
from gridflow.usecase.interfaces import ConnectorStepOutput

runner = CliRunner()


class DeterministicFakeConnector:
    """Connector whose output depends solely on the seed — perfect for repro tests."""

    name = "determ"

    def __init__(self, seed: int = 0) -> None:
        self._seed = seed

    def initialize(self, pack: ScenarioPack) -> None:
        self._seed = pack.metadata.seed if pack.metadata.seed is not None else self._seed

    def step(self, step_index: int) -> ConnectorStepOutput:
        base = 1.0 + (self._seed % 10) * 0.001
        voltages = tuple(base + 0.005 * step_index + 0.001 * i for i in range(3))
        return ConnectorStepOutput(
            step=step_index,
            node_result=NodeResult(node_id="__network__", voltages=voltages),
            converged=True,
        )

    def teardown(self) -> None:
        pass


@pytest.fixture()
def gridflow_home(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    home = tmp_path / ".gridflow"
    monkeypatch.setenv("GRIDFLOW_HOME", str(home))
    monkeypatch.setattr(
        cli_module,
        "_default_connector_factory",
        lambda _name: DeterministicFakeConnector(),
    )
    return home


def _write_pack(target: Path, name: str = "e2e-pack", version: str = "1.0.0") -> Path:
    target.write_text(
        f"""
pack:
  name: {name}
  version: "{version}"
  description: end-to-end pack
  author: tester
  connector: determ
  seed: 42
""",
        encoding="utf-8",
    )
    return target


def test_full_cli_pipeline(gridflow_home: Path, tmp_path: Path) -> None:
    yaml_path = _write_pack(tmp_path / "pack.yaml")

    # register
    reg = runner.invoke(app, ["scenario", "register", str(yaml_path)])
    assert reg.exit_code == 0, reg.output

    # list
    ls = runner.invoke(app, ["scenario", "list"])
    assert reg.exit_code == 0
    assert "e2e-pack@1.0.0" in ls.output

    # run
    run = runner.invoke(
        app,
        [
            "run",
            "e2e-pack@1.0.0",
            "--steps",
            "3",
            "--connector",
            "determ",
            "--format",
            "json",
        ],
    )
    assert run.exit_code == 0, run.output
    payload = json.loads(run.stdout)
    experiment_id = payload["experiment_id"]

    # results
    results = runner.invoke(app, ["results", experiment_id, "--format", "json"])
    assert results.exit_code == 0, results.output
    data = json.loads(results.stdout)
    assert data["experiment_id"] == experiment_id
    assert len(data["steps"]) == 3


def test_reproducibility_three_runs(gridflow_home: Path, tmp_path: Path) -> None:
    """Same seed + same pack → identical per-step voltages across 3 runs."""
    yaml_path = _write_pack(tmp_path / "pack.yaml")
    reg = runner.invoke(app, ["scenario", "register", str(yaml_path)])
    assert reg.exit_code == 0, reg.output

    snapshots: list[list[list[float]]] = []
    for _ in range(3):
        run = runner.invoke(
            app,
            ["run", "e2e-pack@1.0.0", "--steps", "2", "--connector", "determ", "--format", "json"],
        )
        assert run.exit_code == 0, run.output
        experiment_id = json.loads(run.stdout)["experiment_id"]
        result = runner.invoke(app, ["results", experiment_id, "--format", "json"])
        data = json.loads(result.stdout)
        voltages_per_step = [step["node_result"]["voltages"] for step in data["steps"]]
        snapshots.append(voltages_per_step)

    assert snapshots[0] == snapshots[1] == snapshots[2], (
        "Deterministic connector produced different outputs across runs"
    )


def test_benchmark_compare_two_experiments(gridflow_home: Path, tmp_path: Path) -> None:
    yaml_path = _write_pack(tmp_path / "pack.yaml")
    runner.invoke(app, ["scenario", "register", str(yaml_path)])

    ids: list[str] = []
    for _ in range(2):
        run = runner.invoke(
            app,
            ["run", "e2e-pack@1.0.0", "--steps", "2", "--connector", "determ", "--format", "json"],
        )
        ids.append(json.loads(run.stdout)["experiment_id"])

    out_path = tmp_path / "cmp.json"
    bench = runner.invoke(
        app,
        [
            "benchmark",
            "--baseline",
            ids[0],
            "--candidate",
            ids[1],
            "--output",
            str(out_path),
            "--format",
            "json",
        ],
    )
    assert bench.exit_code == 0, bench.output
    assert out_path.exists()
    report = json.loads(out_path.read_text(encoding="utf-8"))
    assert report["baseline"] == ids[0]
    assert report["candidate"] == ids[1]
    metric_names = {entry["name"] for entry in report["metrics"]}
    assert {"voltage_deviation", "runtime"}.issubset(metric_names)
