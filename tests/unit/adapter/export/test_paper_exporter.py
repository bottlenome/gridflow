"""Tests for the paper export strategies (AS-5: publication productivity)."""

from __future__ import annotations

import csv
import json
from pathlib import Path

import pytest

from gridflow.adapter.export.loaders import (
    comparison_table_from_benchmark_report,
    load_comparison_table_json,
)
from gridflow.adapter.export.paper import (
    CaptionRenderer,
    CsvDataRenderer,
    LatexTableRenderer,
    MatplotlibScriptRenderer,
    PaperExporter,
)
from gridflow.domain.error import ExportError
from gridflow.domain.result.comparison_table import (
    ComparisonTable,
    MethodRow,
    MetricSpec,
    MetricValue,
)


def _table() -> ComparisonTable:
    return ComparisonTable(
        title="Commit-drop comparison on ACN-Data",
        metrics=(
            MetricSpec(name="commit_drop", unit="%", objective="min"),
            MetricSpec(name="p99_unmet", unit="kW", objective="min"),
        ),
        rows=(
            MethodRow(
                method="M1",
                n=96,
                values=(
                    MetricValue(mean=29.30, ci_low=26.91, ci_high=31.99),
                    MetricValue(mean=3.57, ci_low=2.20, ci_high=5.10),
                ),
            ),
            MethodRow(
                method="M11",
                n=96,
                values=(
                    MetricValue(mean=19.45, ci_low=17.01, ci_high=21.91),
                    MetricValue(mean=3.39, ci_low=2.07, ci_high=4.88),
                ),
            ),
        ),
        conditions=(("datasets", "ACN Caltech+JPL 2019"), ("n_cells", "480")),
        highlight="M11",
    )


class TestLatexTableRenderer:
    def test_renders_booktabs_table(self) -> None:
        tex = LatexTableRenderer().render(_table())
        assert "\\toprule" in tex
        assert "\\midrule" in tex
        assert "\\bottomrule" in tex
        assert "\\begin{tabular}" in tex

    def test_best_value_is_bold(self) -> None:
        tex = LatexTableRenderer().render(_table())
        # M11 is best (min objective) on both metrics.
        assert "\\textbf{19.45}" in tex
        assert "\\textbf{3.39}" in tex
        assert "\\textbf{29.30}" not in tex

    def test_ci_brackets_present(self) -> None:
        tex = LatexTableRenderer().render(_table())
        assert "[26.91, 31.99]" in tex

    def test_special_chars_escaped(self) -> None:
        tex = LatexTableRenderer().render(_table())
        assert "commit\\_drop" in tex
        assert "[\\%]" in tex


class TestCsvDataRenderer:
    def test_csv_round_trip(self) -> None:
        text = CsvDataRenderer().render(_table())
        rows = list(csv.DictReader(text.splitlines()))
        assert len(rows) == 2
        assert rows[0]["method"] == "M1"
        assert float(rows[1]["commit_drop_mean"]) == pytest.approx(19.45)
        assert float(rows[1]["p99_unmet_ci_high"]) == pytest.approx(4.88)


class TestMatplotlibScriptRenderer:
    def test_script_is_valid_python(self) -> None:
        script = MatplotlibScriptRenderer().render(_table())
        compile(script, "plot_comparison.py", "exec")
        assert "matplotlib" in script
        assert "data.csv" in script


class TestCaptionRenderer:
    def test_caption_describes_conditions(self) -> None:
        caption = CaptionRenderer().render(_table())
        assert "Commit-drop comparison on ACN-Data" in caption
        assert "datasets: ACN Caltech+JPL 2019" in caption
        assert "n_cells: 480" in caption
        assert "95%" in caption


class TestPaperExporter:
    def test_exports_all_default_artifacts(self, tmp_path: Path) -> None:
        written = PaperExporter().export(_table(), tmp_path)
        names = sorted(p.name for p in written)
        assert names == ["caption.txt", "data.csv", "plot_comparison.py", "table.tex"]
        for p in written:
            assert p.exists()
            assert p.read_text(encoding="utf-8").strip()


class TestLoaders:
    def test_load_canonical_comparison_json(self, tmp_path: Path) -> None:
        path = tmp_path / "table.json"
        path.write_text(json.dumps(_table().to_dict()), encoding="utf-8")
        assert load_comparison_table_json(path) == _table()

    def test_load_benchmark_comparison_report_json(self, tmp_path: Path) -> None:
        report = {
            "baseline": "exp-001",
            "candidate": "exp-002",
            "metrics": [
                {"name": "runtime", "baseline": 1.0, "candidate": 0.5, "delta": -0.5},
                {"name": "voltage_deviation", "baseline": 0.2, "candidate": 0.1, "delta": -0.1},
            ],
        }
        path = tmp_path / "report.json"
        path.write_text(json.dumps(report), encoding="utf-8")
        table = load_comparison_table_json(path)
        assert tuple(r.method for r in table.rows) == ("exp-001", "exp-002")
        assert tuple(m.name for m in table.metrics) == ("runtime", "voltage_deviation")
        assert table.rows[1].values[0].mean == pytest.approx(0.5)

    def test_benchmark_report_builder_rejects_bad_payload(self) -> None:
        with pytest.raises(ExportError):
            comparison_table_from_benchmark_report({"nope": True})

    def test_unrecognised_schema_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "x.json"
        path.write_text(json.dumps({"foo": "bar"}), encoding="utf-8")
        with pytest.raises(ExportError):
            load_comparison_table_json(path)

    def test_invalid_json_raises(self, tmp_path: Path) -> None:
        path = tmp_path / "x.json"
        path.write_text("not json", encoding="utf-8")
        with pytest.raises(ExportError):
            load_comparison_table_json(path)
