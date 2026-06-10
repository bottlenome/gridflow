"""Tests for ``gridflow export paper`` (AS-5 / QA-6: < 3 steps to figures)."""

from __future__ import annotations

import json
from pathlib import Path

from typer.testing import CliRunner

from gridflow.adapter.cli.app import app

runner = CliRunner()

_TABLE = {
    "title": "Demo comparison",
    "metrics": [
        {"name": "commit_drop", "unit": "%", "objective": "min"},
    ],
    "rows": [
        {
            "method": "M1",
            "n": 96,
            "values": [{"mean": 29.3, "ci_low": 26.91, "ci_high": 31.99}],
        },
        {
            "method": "M11",
            "n": 96,
            "values": [{"mean": 19.45, "ci_low": 17.01, "ci_high": 21.91}],
        },
    ],
    "conditions": [["n_cells", "480"]],
    "highlight": "M11",
}


class TestExportPaper:
    def test_export_paper_writes_artifacts(self, tmp_path: Path) -> None:
        src = tmp_path / "table.json"
        src.write_text(json.dumps(_TABLE), encoding="utf-8")
        out_dir = tmp_path / "paper"
        result = runner.invoke(
            app, ["export", "paper", str(src), "--output", str(out_dir)]
        )
        assert result.exit_code == 0, result.output
        assert (out_dir / "table.tex").exists()
        assert (out_dir / "data.csv").exists()
        assert (out_dir / "plot_comparison.py").exists()
        assert (out_dir / "caption.txt").exists()

    def test_export_paper_rejects_bad_schema(self, tmp_path: Path) -> None:
        src = tmp_path / "bad.json"
        src.write_text(json.dumps({"foo": 1}), encoding="utf-8")
        result = runner.invoke(
            app, ["export", "paper", str(src), "--output", str(tmp_path / "o")]
        )
        assert result.exit_code == 1
        assert "E-30008" in result.output
