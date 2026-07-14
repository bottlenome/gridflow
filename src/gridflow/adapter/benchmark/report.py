"""Serialise benchmark outputs to JSON (and thin human-readable text)."""

from __future__ import annotations

import json
from pathlib import Path

from gridflow.adapter.benchmark.harness import (
    BenchmarkRunSummary,
    ComparisonReport,
    StatisticalComparisonReport,
)


class ReportGenerator:
    """Write benchmark summaries / comparisons to disk."""

    def write_summary(self, summary: BenchmarkRunSummary, path: Path) -> None:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(summary.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    def write_comparison(self, report: ComparisonReport | StatisticalComparisonReport, path: Path) -> None:
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

    def render_statistical_text(self, report: StatisticalComparisonReport) -> str:
        """Render the replicate-aware statistical verdict as plain text."""
        lines = [
            f"Comparison: {report.baseline_id} → {report.candidate_id}",
            f"alpha={report.alpha}  correction={report.correction}",
            "-" * 92,
            f"{'metric':<20}{'baseline':>11}{'candidate':>11}{'delta':>11}"
            f"{'d':>8}{'p_adj':>9}{'verdict':>12}{'  note'}",
        ]
        for m in report.metrics:
            d_str = f"{m.effect_size:>8.2f}" if m.effect_size is not None else f"{'—':>8}"
            p_str = f"{m.p_value_adjusted:>9.4f}" if m.p_value_adjusted is not None else f"{'—':>9}"
            if m.informational:
                verdict = "info"
            elif m.significant:
                verdict = "SIGNIFICANT"
            else:
                verdict = "ns"
            note = ";".join(m.warnings)
            lines.append(
                f"{m.name:<20}{m.baseline_mean:>11.4f}{m.candidate_mean:>11.4f}"
                f"{m.delta:>+11.4f}{d_str}{p_str}{verdict:>12}  {note}"
            )
        if not report.any_significant:
            lines.append("")
            lines.append("No metric reached significance — do not report an improvement.")
        return "\n".join(lines)
