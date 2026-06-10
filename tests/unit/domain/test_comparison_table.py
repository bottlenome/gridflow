"""Tests for the ComparisonTable domain model (paper export input)."""

from __future__ import annotations

import pytest

from gridflow.domain.error import CDLValidationError
from gridflow.domain.result.comparison_table import (
    ComparisonTable,
    MethodRow,
    MetricSpec,
    MetricValue,
)


def _table() -> ComparisonTable:
    return ComparisonTable(
        title="Commit-drop comparison",
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
        conditions=(("datasets", "ACN 4x"), ("n_cells", "480")),
        highlight="M11",
    )


class TestMetricValue:
    def test_ci_must_be_paired(self) -> None:
        with pytest.raises(CDLValidationError):
            MetricValue(mean=1.0, ci_low=0.5)

    def test_ci_must_bracket_mean(self) -> None:
        with pytest.raises(CDLValidationError):
            MetricValue(mean=1.0, ci_low=2.0, ci_high=3.0)

    def test_no_ci_is_valid(self) -> None:
        v = MetricValue(mean=1.0)
        assert v.has_ci is False

    def test_hashable(self) -> None:
        assert len({MetricValue(mean=1.0), MetricValue(mean=1.0)}) == 1


class TestMetricSpec:
    def test_objective_must_be_min_or_max(self) -> None:
        with pytest.raises(CDLValidationError):
            MetricSpec(name="x", unit="", objective="best")


class TestComparisonTable:
    def test_round_trip_dict(self) -> None:
        table = _table()
        assert ComparisonTable.from_dict(table.to_dict()) == table

    def test_hashable(self) -> None:
        assert len({_table(), _table()}) == 1

    def test_row_value_count_must_match_metrics(self) -> None:
        with pytest.raises(CDLValidationError):
            ComparisonTable(
                title="t",
                metrics=(MetricSpec(name="m", unit="", objective="min"),),
                rows=(MethodRow(method="A", n=1, values=()),),
            )

    def test_metrics_must_be_non_empty(self) -> None:
        with pytest.raises(CDLValidationError):
            ComparisonTable(title="t", metrics=(), rows=())

    def test_duplicate_method_names_rejected(self) -> None:
        row = MethodRow(method="A", n=1, values=(MetricValue(mean=1.0),))
        with pytest.raises(CDLValidationError):
            ComparisonTable(
                title="t",
                metrics=(MetricSpec(name="m", unit="", objective="min"),),
                rows=(row, row),
            )

    def test_highlight_must_be_existing_method(self) -> None:
        with pytest.raises(CDLValidationError):
            ComparisonTable(
                title="t",
                metrics=(MetricSpec(name="m", unit="", objective="min"),),
                rows=(MethodRow(method="A", n=1, values=(MetricValue(mean=1.0),)),),
                highlight="missing",
            )

    def test_best_method_min_objective(self) -> None:
        table = _table()
        assert table.best_method(0) == "M11"
        assert table.best_method(1) == "M11"

    def test_best_method_max_objective(self) -> None:
        table = ComparisonTable(
            title="t",
            metrics=(MetricSpec(name="score", unit="", objective="max"),),
            rows=(
                MethodRow(method="A", n=1, values=(MetricValue(mean=1.0),)),
                MethodRow(method="B", n=1, values=(MetricValue(mean=2.0),)),
            ),
        )
        assert table.best_method(0) == "B"
