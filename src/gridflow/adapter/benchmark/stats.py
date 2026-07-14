"""Pure-Python statistical primitives for benchmark comparison (issue #18).

No scipy / numpy: the connector containers ship a minimal dependency closure,
and the research-emergence loop must be able to judge a candidate-vs-baseline
difference *inside* that closure. Everything here is stdlib ``math`` /
``statistics`` / ``itertools`` / ``random``.

The design goal is a single honest verdict — "is this difference real, or noise
you are about to publish?" — which past trials repeatedly got wrong:

    * try12 read a CI-boundary, non-significant difference as "progress".
    * try11 reported a 5x reduction whose bootstrap CI was zero-width because
      every seed produced the identical deterministic result — a non-result
      dressed as a tight interval.

So the primitives here always report *why* a difference is or is not
trustworthy: an effect size, a permutation p-value, a bootstrap CI, and
explicit degeneracy flags (too few replicates, zero within-group variance).
"""

from __future__ import annotations

import itertools
import math
import random
import statistics
from collections.abc import Sequence

# Guard: a permutation test with more than this many exact arrangements falls
# back to seeded Monte-Carlo sampling rather than enumerating them all.
_EXACT_PERMUTATION_LIMIT = 20000


def cohens_d(baseline: Sequence[float], candidate: Sequence[float]) -> float | None:
    """Cohen's d effect size (candidate - baseline), pooled SD.

    Returns ``None`` when it is undefined: fewer than two samples on either
    side, or zero pooled variance (both groups constant). A ``None`` here is
    the signal that no *standardised* effect can be quoted — the caller must
    not invent one.
    """
    n_b, n_c = len(baseline), len(candidate)
    if n_b < 2 or n_c < 2:
        return None
    var_b = statistics.variance(baseline)
    var_c = statistics.variance(candidate)
    pooled = ((n_b - 1) * var_b + (n_c - 1) * var_c) / (n_b + n_c - 2)
    if pooled <= 0.0:
        return None
    return (statistics.fmean(candidate) - statistics.fmean(baseline)) / math.sqrt(pooled)


def permutation_test(
    baseline: Sequence[float],
    candidate: Sequence[float],
    *,
    n_permutations: int = 10000,
    seed: int = 0,
) -> float | None:
    """Two-sided permutation p-value for a difference in means.

    The statistic is ``|mean(candidate) - mean(baseline)|``. All group-label
    reassignments (exact when few enough, else seeded Monte-Carlo) give the
    null distribution; the p-value is the fraction at least as extreme as the
    observed statistic.

    Returns ``None`` when the test cannot run (either group empty). Callers
    should treat a too-small sample as underpowered even when a number comes
    back — see :func:`is_degenerate`.
    """
    n_b, n_c = len(baseline), len(candidate)
    if n_b == 0 or n_c == 0:
        return None
    pooled = [*baseline, *candidate]
    observed = abs(statistics.fmean(candidate) - statistics.fmean(baseline))
    total_mean = statistics.fmean(pooled)
    n_total = n_b + n_c

    # If nothing varies, every relabelling yields the same means → the only
    # honest p-value is 1.0 (no evidence of a difference from resampling).
    if all(x == pooled[0] for x in pooled):
        return 1.0

    n_arrangements = math.comb(n_total, n_b)
    if n_arrangements <= _EXACT_PERMUTATION_LIMIT:
        at_least_as_extreme = 0
        indices = range(n_total)
        for combo in itertools.combinations(indices, n_b):
            combo_set = set(combo)
            group_a = [pooled[i] for i in combo_set]
            mean_a = statistics.fmean(group_a)
            # mean_b derivable from the total so we avoid a second pass sum.
            mean_b = (total_mean * n_total - mean_a * n_b) / n_c
            if abs(mean_b - mean_a) >= observed - 1e-12:
                at_least_as_extreme += 1
        return at_least_as_extreme / n_arrangements

    rng = random.Random(seed)
    at_least_as_extreme = 0
    for _ in range(n_permutations):
        shuffled = pooled[:]
        rng.shuffle(shuffled)
        mean_a = statistics.fmean(shuffled[:n_b])
        mean_b = statistics.fmean(shuffled[n_b:])
        if abs(mean_b - mean_a) >= observed - 1e-12:
            at_least_as_extreme += 1
    # +1 smoothing (never report an impossible exact-zero Monte-Carlo p).
    return (at_least_as_extreme + 1) / (n_permutations + 1)


def mean_ci(
    values: Sequence[float],
    *,
    bootstrap_n: int = 2000,
    seed: int = 0,
    confidence: float = 0.95,
) -> tuple[float, float] | None:
    """Percentile bootstrap CI for the mean of ``values`` (None if <2 samples)."""
    n = len(values)
    if n < 2:
        return None
    rng = random.Random(seed)
    means: list[float] = []
    for _ in range(bootstrap_n):
        sample = [values[rng.randrange(n)] for _ in range(n)]
        means.append(statistics.fmean(sample))
    means.sort()
    alpha = (1.0 - confidence) / 2.0
    lo_idx = max(0, int(alpha * bootstrap_n))
    hi_idx = min(bootstrap_n - 1, int((1.0 - alpha) * bootstrap_n))
    return float(means[lo_idx]), float(means[hi_idx])


def is_degenerate(baseline: Sequence[float], candidate: Sequence[float]) -> tuple[bool, str]:
    """Detect inputs on which a significance claim would be an artifact.

    Returns ``(degenerate, reason)``. Reasons:
        * ``"insufficient_replicates"`` — <2 samples on a side, so within-group
          variance is unknown; no significance can be asserted.
        * ``"zero_variance"`` — both groups are internally constant. Any p-value
          then reflects deterministic inputs, not run-to-run robustness (the
          try11 zero-width-CI trap). The difference may be real, but it is not
          a *statistical* result.
    """
    n_b, n_c = len(baseline), len(candidate)
    if n_b < 2 or n_c < 2:
        return True, "insufficient_replicates"
    if statistics.variance(baseline) == 0.0 and statistics.variance(candidate) == 0.0:
        return True, "zero_variance"
    return False, ""


def holm(p_values: Sequence[float]) -> list[float]:
    """Holm-Bonferroni step-down adjusted p-values (controls FWER).

    Order-preserving: the returned list aligns with the input order.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_max = 0.0
    for rank, idx in enumerate(order):
        val = (m - rank) * p_values[idx]
        running_max = max(running_max, min(val, 1.0))
        adjusted[idx] = running_max
    return adjusted


def benjamini_hochberg(p_values: Sequence[float]) -> list[float]:
    """Benjamini-Hochberg step-up adjusted p-values (controls FDR).

    The right correction when the loop screens *many* hypotheses and a bounded
    false-discovery rate matters more than zero false positives. Order-
    preserving relative to the input.
    """
    m = len(p_values)
    if m == 0:
        return []
    order = sorted(range(m), key=lambda i: p_values[i])
    adjusted = [0.0] * m
    running_min = 1.0
    # Walk from largest p to smallest, enforcing monotonicity.
    for rank in range(m - 1, -1, -1):
        idx = order[rank]
        val = p_values[idx] * m / (rank + 1)
        running_min = min(running_min, val, 1.0)
        adjusted[idx] = running_min
    return adjusted


def adjust_p_values(p_values: Sequence[float], *, method: str) -> list[float]:
    """Dispatch to a multiple-comparison correction by name (``holm`` / ``bh``)."""
    if method == "holm":
        return holm(p_values)
    if method in ("bh", "benjamini-hochberg", "fdr"):
        return benjamini_hochberg(p_values)
    raise ValueError(f"unknown correction method {method!r}; expected 'holm' or 'bh'")


__all__ = [
    "adjust_p_values",
    "benjamini_hochberg",
    "cohens_d",
    "holm",
    "is_degenerate",
    "mean_ci",
    "permutation_test",
]
