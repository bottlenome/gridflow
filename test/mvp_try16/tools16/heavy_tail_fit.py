"""Heavy-tail Pareto fit + M11 hysteresis design rule.

We use Hill's MLE for the tail exponent alpha of a power-law
distribution, applied to inter-drop intervals (preferred over session
durations because the SLA-critical regime is "how long until next drop"
rather than "how long is a session").

Hill estimator [Hill 1975, Annals of Statistics]:
    alpha_hat = k / sum_{i=1..k} log(X_(i) / X_(k+1))
where X_(1) > X_(2) > ... are descending-order values and k is the
top-k sample count (typically n / 4).

Design rule (Theorem 4 corollary, theorems.md §4):
    d_drop  = ceil(1 / alpha_hat)
    dt_up_s = c * median_interval * F^{-1}(P99 quantile)
where c is a safety factor (default 1.5) and F^{-1} is the empirical
quantile of the inter-drop distribution.
"""

from __future__ import annotations

import math
import statistics
from dataclasses import dataclass


@dataclass(frozen=True)
class HeavyTailFit:
    n_samples: int
    alpha_hill: float
    median_interval_s: float
    p99_interval_s: float
    d_drop: int
    dt_up_s: float


def hill_alpha(samples: tuple[float, ...], k_frac: float = 0.25) -> float:
    """Hill MLE for tail exponent.  Returns alpha (Pareto density ~ x^{-alpha-1}).

    For Pareto(alpha, x_min) on x >= x_min:  pdf(x) = alpha * x_min^alpha / x^{alpha+1}
    Smaller alpha = heavier tail.  alpha < 2 -> infinite variance.
    """
    arr = sorted([float(x) for x in samples if x > 0], reverse=True)
    n = len(arr)
    if n < 4:
        return 0.0
    k = max(2, int(n * k_frac))
    x_kp1 = arr[k]  # threshold
    if x_kp1 <= 0:
        return 0.0
    s = sum(math.log(arr[i] / x_kp1) for i in range(k))
    if s <= 0:
        return 0.0
    return k / s


def design_hysteresis(
    intervals_s: tuple[float, ...],
    *,
    safety_c: float = 1.5,
    fallback_alpha: float = 1.7,
) -> HeavyTailFit:
    """Estimate Pareto alpha + emit M11 hysteresis schedule."""
    arr = [x for x in intervals_s if x > 0]
    n = len(arr)
    if n < 8:
        return HeavyTailFit(
            n_samples=n,
            alpha_hill=fallback_alpha,
            median_interval_s=0.0,
            p99_interval_s=0.0,
            d_drop=1,
            dt_up_s=24 * 3600.0,
        )
    alpha = hill_alpha(tuple(arr))
    if alpha <= 0:
        alpha = fallback_alpha
    median_iv = statistics.median(arr)
    arr_sorted = sorted(arr)
    p99 = arr_sorted[max(0, int(0.99 * n) - 1)]
    d_drop = max(1, math.ceil(1.0 / alpha))
    dt_up = safety_c * max(median_iv, 1.0) * (p99 / max(median_iv, 1.0))
    return HeavyTailFit(
        n_samples=n,
        alpha_hill=alpha,
        median_interval_s=median_iv,
        p99_interval_s=p99,
        d_drop=int(d_drop),
        dt_up_s=float(dt_up),
    )
