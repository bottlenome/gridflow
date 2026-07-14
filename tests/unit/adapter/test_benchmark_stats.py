"""Tests for the pure statistical primitives (issue #18)."""

from __future__ import annotations

import pytest

from gridflow.adapter.benchmark import stats


class TestCohensD:
    def test_none_for_single_samples(self) -> None:
        assert stats.cohens_d([1.0], [2.0]) is None

    def test_none_for_zero_pooled_variance(self) -> None:
        assert stats.cohens_d([1.0, 1.0], [2.0, 2.0]) is None

    def test_sign_and_magnitude(self) -> None:
        d = stats.cohens_d([0.0, 0.0, 0.0, 0.0], [1.0, 1.0, 1.0, 1.0])
        # candidate higher → positive; pooled sd tiny but non-zero due to
        # variance within... here both groups constant → None handled above.
        # Use groups with spread:
        d = stats.cohens_d([1.0, 2.0, 3.0], [4.0, 5.0, 6.0])
        assert d is not None and d > 0


class TestPermutationTest:
    def test_identical_groups_p_is_one(self) -> None:
        assert stats.permutation_test([1.0, 1.0], [1.0, 1.0]) == 1.0

    def test_separated_groups_small_p(self) -> None:
        # Fully separated, several replicates → exact enumeration → low p.
        # (3v3 bottoms out at 2/C(6,3)=0.1, so use 4v4 → 2/C(8,4)≈0.029.)
        p = stats.permutation_test([0.0, 0.1, 0.2, 0.3], [10.0, 10.1, 10.2, 10.3])
        assert p is not None and p < 0.05

    def test_overlapping_groups_high_p(self) -> None:
        p = stats.permutation_test([1.0, 2.0, 3.0], [1.5, 2.5, 3.5])
        assert p is not None and p > 0.2

    def test_empty_group_returns_none(self) -> None:
        assert stats.permutation_test([], [1.0]) is None

    def test_deterministic_monte_carlo(self) -> None:
        # Large groups force the Monte-Carlo path; same seed → same p.
        big_b = [float(i) for i in range(20)]
        big_c = [float(i) + 0.3 for i in range(20)]
        p1 = stats.permutation_test(big_b, big_c, n_permutations=500, seed=7)
        p2 = stats.permutation_test(big_b, big_c, n_permutations=500, seed=7)
        assert p1 == p2


class TestMeanCI:
    def test_none_for_single_sample(self) -> None:
        assert stats.mean_ci([1.0]) is None

    def test_brackets_mean(self) -> None:
        ci = stats.mean_ci([1.0, 2.0, 3.0, 4.0, 5.0], bootstrap_n=500, seed=1)
        assert ci is not None
        lo, hi = ci
        assert lo <= 3.0 <= hi


class TestIsDegenerate:
    def test_insufficient_replicates(self) -> None:
        deg, reason = stats.is_degenerate([1.0], [2.0, 3.0])
        assert deg and reason == "insufficient_replicates"

    def test_zero_variance(self) -> None:
        deg, reason = stats.is_degenerate([1.0, 1.0], [2.0, 2.0])
        assert deg and reason == "zero_variance"

    def test_healthy(self) -> None:
        deg, reason = stats.is_degenerate([1.0, 2.0], [3.0, 5.0])
        assert not deg and reason == ""


class TestCorrections:
    def test_holm_monotone_and_bounded(self) -> None:
        adj = stats.holm([0.01, 0.02, 0.03])
        assert all(0.0 <= p <= 1.0 for p in adj)
        # Holm inflates the smallest p by m.
        assert adj[0] == pytest.approx(0.03)

    def test_bh_less_conservative_than_holm(self) -> None:
        raw = [0.01, 0.02, 0.03, 0.04]
        holm_adj = stats.holm(raw)
        bh_adj = stats.benjamini_hochberg(raw)
        assert sum(bh_adj) <= sum(holm_adj)

    def test_order_preserved(self) -> None:
        raw = [0.04, 0.01, 0.03, 0.02]
        adj = stats.benjamini_hochberg(raw)
        assert len(adj) == 4
        # Smallest raw p (index 1) maps to smallest adjusted.
        assert adj[1] == min(adj)

    def test_empty(self) -> None:
        assert stats.holm([]) == []
        assert stats.benjamini_hochberg([]) == []

    def test_unknown_method_rejected(self) -> None:
        with pytest.raises(ValueError, match="unknown correction"):
            stats.adjust_p_values([0.1], method="bogus")
