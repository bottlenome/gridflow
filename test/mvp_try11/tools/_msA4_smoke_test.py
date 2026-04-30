"""MS-A4 smoke test — C7 correlation reversal + C8 scarce orthogonal."""

from __future__ import annotations

import statistics

from tools.der_pool import make_default_pool
from tools.trace_synthesizer import (
    make_scarce_orthogonal_pool,
    synth_c7_correlation_reversal,
    synth_c8_scarce_orthogonal,
)


def main() -> int:
    failures: list[str] = []
    pool = make_default_pool(seed=0)

    # 1. C7 has commute and weather events
    trace_c7 = synth_c7_correlation_reversal(pool, seed=0, sla_kw=400.0)
    commute_events = [e for e in trace_c7.events if e.trigger == "commute"]
    weather_events = [e for e in trace_c7.events if e.trigger == "weather"]
    if not commute_events or not weather_events:
        failures.append("C7 missing commute or weather events")

    # 2. C7 train period: commute and weather close in time (within 30 min)
    train_min = trace_c7.train_days * 24 * 60
    train_commute = [e.start_min for e in commute_events if e.start_min < train_min]
    train_weather = [e.start_min for e in weather_events if e.start_min < train_min]
    test_commute = [e.start_min for e in commute_events if e.start_min >= train_min]
    test_weather = [e.start_min for e in weather_events if e.start_min >= train_min]
    if not (len(train_commute) == len(train_weather)):
        failures.append(f"C7 train: commute={len(train_commute)}, weather={len(train_weather)} unbalanced")
    # Train: same-day pairs within 30 min
    if train_commute and train_weather:
        diffs_train = [abs(c - w) for c, w in zip(sorted(train_commute), sorted(train_weather))]
        max_diff_train = max(diffs_train) if diffs_train else 0
        if max_diff_train > 60:
            failures.append(f"C7 train: max same-day commute-weather diff {max_diff_train}min > 60")

    # Test: same-day pairs FAR apart (~16 hours)
    if test_commute and test_weather:
        # Each day has one of each
        n_pairs = min(len(test_commute), len(test_weather))
        # Daily within-pair distance: weather ~ commute + 16 hr (= 960 min)
        diffs_test = []
        for i in range(n_pairs):
            same_day_c = sorted(test_commute)[i]
            same_day_w = sorted(test_weather)[i]
            diffs_test.append(abs(same_day_c - same_day_w))
        mean_diff_test = statistics.fmean(diffs_test)
        if mean_diff_test < 600:
            failures.append(f"C7 test: mean commute-weather diff {mean_diff_test}min < 600 (= 10 hours)")

    # 3. C8 trace_id = "C8" but structure = C1
    trace_c8 = synth_c8_scarce_orthogonal(pool, seed=0, sla_kw=400.0)
    if trace_c8.trace_id != "C8":
        failures.append(f"C8 trace_id={trace_c8.trace_id}")
    if trace_c8.n_steps == 0:
        failures.append("C8 has zero steps")

    # 4. make_scarce_orthogonal_pool reduces utility_battery count
    scarce = make_scarce_orthogonal_pool(pool, n_utility_keep=5)
    n_util_orig = sum(1 for d in pool if d.der_type == "utility_battery")
    n_util_scarce = sum(1 for d in scarce if d.der_type == "utility_battery")
    if n_util_orig != 30:
        failures.append(f"original pool utility count {n_util_orig} != 30")
    if n_util_scarce != 5:
        failures.append(f"scarce pool utility count {n_util_scarce} != 5")
    # Other types preserved
    n_other_orig = len(pool) - n_util_orig
    n_other_scarce = len(scarce) - n_util_scarce
    if n_other_orig != n_other_scarce:
        failures.append(f"non-utility count changed: {n_other_orig} vs {n_other_scarce}")

    # 5. cost_multiplier inflates utility cost
    inflated = make_scarce_orthogonal_pool(pool, n_utility_keep=5, cost_multiplier=3.0)
    util_orig_cost = next(d for d in pool if d.der_type == "utility_battery").contract_cost_standby
    util_inflated_cost = next(d for d in inflated if d.der_type == "utility_battery").contract_cost_standby
    if abs(util_inflated_cost - util_orig_cost * 3) > 1e-6:
        failures.append(f"cost_multiplier=3 not applied: {util_inflated_cost} vs {util_orig_cost*3}")

    print(f"  C7: train events {len(train_commute)} c + {len(train_weather)} w, "
          f"test events {len(test_commute)} c + {len(test_weather)} w")
    print(f"  C8: trace_id={trace_c8.trace_id}, n_steps={trace_c8.n_steps}")
    print(f"  scarce pool: orig util={n_util_orig}, scarce util={n_util_scarce}, "
          f"orig cost={util_orig_cost}, inflated cost={util_inflated_cost}")

    if failures:
        print(f"\nFAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("\nOK — MS-A4 smoke test passed.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
