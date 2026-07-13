"""Keep the MVP trial templates valid (issue #25).

The templates under ``test/_template/`` are the blessed starting point for a
trial; if a template stops parsing through the real loaders, a researcher
copying it would fall back to a hand-rolled script — the exact bypass issue #25
exists to prevent. These tests fail loudly the moment a template drifts out of
sync with the loader schema.
"""

from __future__ import annotations

from pathlib import Path

from gridflow.usecase.evaluation_yaml_loader import load_evaluation_plan_from_yaml
from gridflow.usecase.sweep_yaml_loader import load_sweep_plan_bundle_from_yaml

_TEMPLATE_DIR = Path(__file__).resolve().parents[2] / "test" / "_template"


def test_sweep_plan_template_parses() -> None:
    bundle = load_sweep_plan_bundle_from_yaml(_TEMPLATE_DIR / "sweep_plan.yaml")
    # The template must demonstrate replicates (the precondition for the
    # significance test) rather than defaulting to a single run.
    assert bundle.plan.n_replicates >= 2
    assert bundle.plan.axes


def test_eval_plan_template_parses() -> None:
    plan = load_evaluation_plan_from_yaml(_TEMPLATE_DIR / "eval_plan.yaml")
    assert plan.metrics
    # The template should surface the built-in physical/convergence metrics.
    names = {m.name for m in plan.metrics}
    assert "non_convergence_rate" in names


def test_report_and_review_skeletons_exist() -> None:
    assert (_TEMPLATE_DIR / "report.md").is_file()
    review = (_TEMPLATE_DIR / "review_record.md").read_text(encoding="utf-8")
    # The standard-path-usage audit table must be present in the skeleton.
    assert "標準経路の使用状況" in review
