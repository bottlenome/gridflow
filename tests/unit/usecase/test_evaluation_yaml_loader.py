"""Tests for evaluation plan YAML loader — §5.1.1 Option B."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from gridflow.usecase.evaluation_yaml_loader import (
    EvaluationPlanLoadError,
    load_evaluation_plan_from_dict,
    load_evaluation_plan_from_yaml,
)


class TestLoadFromDict:
    def test_minimal_results_list(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        (tmp_path / "b.json").write_text("{}", encoding="utf-8")
        plan = load_evaluation_plan_from_dict(
            {
                "evaluation": {
                    "id": "e1",
                    "results": ["a.json", "b.json"],
                },
                "metrics": [{"name": "voltage_deviation"}],
            },
            base_dir=tmp_path,
        )
        assert plan.evaluation_id == "e1"
        assert len(plan.results) == 2
        assert plan.metrics[0].name == "voltage_deviation"
        assert plan.metrics[0].plugin is None

    def test_results_dir(self, tmp_path: Path) -> None:
        results_dir = tmp_path / "results"
        results_dir.mkdir()
        (results_dir / "exp-1.json").write_text("{}", encoding="utf-8")
        (results_dir / "exp-2.json").write_text("{}", encoding="utf-8")
        (results_dir / "notes.txt").write_text("ignore me", encoding="utf-8")
        plan = load_evaluation_plan_from_dict(
            {
                "evaluation": {"id": "e2", "results_dir": "results"},
                "metrics": [{"name": "voltage_deviation"}],
            },
            base_dir=tmp_path,
        )
        # Only .json files are picked up, deterministic sort order.
        assert [p.name for p in plan.results] == ["exp-1.json", "exp-2.json"]

    def test_sweep_result_source(self, tmp_path: Path) -> None:
        # By convention the CLI writes SweepResult JSON alongside the
        # child ExperimentResult JSON files (both inside GRIDFLOW_HOME/results).
        (tmp_path / "child-1.json").write_text("{}", encoding="utf-8")
        (tmp_path / "child-2.json").write_text("{}", encoding="utf-8")
        sweep_path = tmp_path / "sweep.json"
        sweep_path.write_text(
            json.dumps({"experiment_ids": ["child-1", "child-2"]}),
            encoding="utf-8",
        )
        plan = load_evaluation_plan_from_dict(
            {
                "evaluation": {"id": "e3", "sweep_result": "sweep.json"},
                "metrics": [{"name": "voltage_deviation"}],
            },
            base_dir=tmp_path,
        )
        assert {p.name for p in plan.results} == {"child-1.json", "child-2.json"}

    def test_exclusive_source_enforced(self, tmp_path: Path) -> None:
        with pytest.raises(EvaluationPlanLoadError, match="exactly one"):
            load_evaluation_plan_from_dict(
                {
                    "evaluation": {
                        "id": "e1",
                        "results": ["a.json"],
                        "results_dir": "results",
                    },
                    "metrics": [{"name": "voltage_deviation"}],
                },
                base_dir=tmp_path,
            )

    def test_missing_source_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(EvaluationPlanLoadError, match="exactly one"):
            load_evaluation_plan_from_dict(
                {
                    "evaluation": {"id": "e1"},
                    "metrics": [{"name": "voltage_deviation"}],
                },
                base_dir=tmp_path,
            )

    def test_multi_metric_spec(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        plan = load_evaluation_plan_from_dict(
            {
                "evaluation": {"id": "e4", "results": ["a.json"]},
                "metrics": [
                    {"name": "voltage_deviation"},
                    {
                        "name": "hc_090",
                        "plugin": "mod:Cls",
                        "kwargs": {"voltage_low": 0.90},
                    },
                    {
                        "name": "hc_095",
                        "plugin": "mod:Cls",
                        "kwargs": {"voltage_low": 0.95},
                    },
                ],
            },
            base_dir=tmp_path,
        )
        assert [m.name for m in plan.metrics] == [
            "voltage_deviation",
            "hc_090",
            "hc_095",
        ]
        assert plan.metrics[1].plugin == "mod:Cls"
        assert dict(plan.metrics[1].kwargs) == {"voltage_low": 0.90}


class TestLoadFromYAMLFile:
    def test_loads_real_file(self, tmp_path: Path) -> None:
        (tmp_path / "a.json").write_text("{}", encoding="utf-8")
        yaml_path = tmp_path / "eval.yaml"
        yaml_path.write_text(
            """
evaluation:
  id: demo
  results:
    - a.json

metrics:
  - name: voltage_deviation
""",
            encoding="utf-8",
        )
        plan = load_evaluation_plan_from_yaml(yaml_path)
        assert plan.evaluation_id == "demo"
        assert len(plan.results) == 1

    def test_missing_file_rejected(self, tmp_path: Path) -> None:
        with pytest.raises(EvaluationPlanLoadError, match="not found"):
            load_evaluation_plan_from_yaml(tmp_path / "nope.yaml")

    def test_malformed_yaml_rejected(self, tmp_path: Path) -> None:
        p = tmp_path / "bad.yaml"
        p.write_text("evaluation: {id: e1\n", encoding="utf-8")  # missing }
        with pytest.raises(EvaluationPlanLoadError, match="malformed"):
            load_evaluation_plan_from_yaml(p)
