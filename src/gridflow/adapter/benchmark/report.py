"""Serialise benchmark outputs to JSON (and thin human-readable text)."""

from __future__ import annotations

import json
from pathlib import Path

from gridflow.adapter.benchmark.harness import BenchmarkRunSummary, ComparisonReport


class ReportGenerator:
    """Write benchmark summaries / comparisons to disk."""

    def write_summary(self, summary: BenchmarkRunSummary, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def write_comparison(self, report: ComparisonReport, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def render_comparison_text(self, report: ComparisonReport) -> str:
        """Render a human-friendly comparison table (plain text)."""
        lines = [
            f"Comparison: {report.baseline_id} → {report.candidate_id}",
            "-" * 60,
            f"{'metric':<24}{'baseline':>12}{'candidate':>12}{'delta':>12}",
        ]
        for name, base, cand, delta in report.diffs:
            lines.append(f"{name:<24}{base:>12.4f}{cand:>12.4f}{delta:>+12.4f}")
        return "\n".join(lines)
