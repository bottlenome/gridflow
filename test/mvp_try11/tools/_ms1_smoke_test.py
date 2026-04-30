"""Quick self-consistency smoke test for MS-1.

Verifies:
  - DER pool generation is deterministic for fixed seed
  - Pool CSV write/read round-trips losslessly
  - C1-C5 traces are generated, total active count drops on trigger events
  - C6 (label noise) actually perturbs exposure
  - project_exposure works for K=2, K=3, K=4, K=5

Not pytest — runnable as ``python -m tools._ms1_smoke_test`` from
``test/mvp_try11/``.
"""

from __future__ import annotations

import shutil
import statistics
import tempfile
from pathlib import Path

from tools.der_pool import (
    DEFAULT_EXPOSURE_K4,
    TRIGGER_BASIS_K2,
    TRIGGER_BASIS_K3,
    TRIGGER_BASIS_K4,
    TRIGGER_BASIS_K5,
    load_pool_csv,
    make_default_pool,
    project_exposure,
    write_pool_csv,
)
from tools.trace_synthesizer import (
    perturb_pool_label_noise,
    synth_c1_single_trigger,
    synth_c2_extreme_burst,
    synth_c3_simultaneous,
    synth_c4_out_of_basis,
    synth_c5_frequency_shift,
)


def main() -> int:
    failures: list[str] = []

    # 1. Pool determinism
    p1 = make_default_pool(seed=42)
    p2 = make_default_pool(seed=42)
    if p1 != p2:
        failures.append("pool not deterministic at seed=42")
    if len(p1) != 200:
        failures.append(f"pool size != 200: got {len(p1)}")

    # 2. Pool CSV round-trip
    tmp = Path(tempfile.mkdtemp())
    try:
        path = tmp / "pool.csv"
        write_pool_csv(p1, path)
        p_loaded = load_pool_csv(path)
        if p_loaded != p1:
            failures.append("pool CSV round-trip changed value")
    finally:
        shutil.rmtree(tmp)

    # 3. project_exposure for all bases
    der = p1[0]
    for basis, expected_len in (
        (TRIGGER_BASIS_K2, 2),
        (TRIGGER_BASIS_K3, 3),
        (TRIGGER_BASIS_K4, 4),
        (TRIGGER_BASIS_K5, 5),
    ):
        proj = project_exposure(der, basis)
        if len(proj) != expected_len:
            failures.append(f"project_exposure({basis}) wrong length: {len(proj)}")
        if not all(isinstance(b, bool) for b in proj):
            failures.append(f"project_exposure({basis}) non-bool entries")
    # K=5 last axis (regulatory) should always be False
    if project_exposure(der, TRIGGER_BASIS_K5)[4] is not False:
        failures.append("regulatory axis should always project to False")

    # 4. Trace generation — each variant runs and produces a non-empty matrix
    pool = make_default_pool(seed=0)
    n_pool = len(pool)
    for synth in (
        synth_c1_single_trigger,
        synth_c2_extreme_burst,
        synth_c3_simultaneous,
        synth_c4_out_of_basis,
        synth_c5_frequency_shift,
    ):
        trace = synth(pool, seed=0)
        if trace.n_steps != trace.horizon_days * 24 * 60 // trace.timestep_min:
            failures.append(f"{synth.__name__}: n_steps mismatch")
        if len(trace.der_active_status) != trace.n_steps:
            failures.append(f"{synth.__name__}: matrix length != n_steps")
        if any(len(row) != n_pool for row in trace.der_active_status):
            failures.append(f"{synth.__name__}: some row length != pool size")
        # At least one timestep must have someone inactive (since events fire)
        any_inactive = any(not all(row) for row in trace.der_active_status)
        if not any_inactive:
            failures.append(f"{synth.__name__}: no inactive period despite events")
        # Average activity should be in (0, 1) — sanity check
        avg_active = statistics.fmean(
            sum(row) / n_pool for row in trace.der_active_status
        )
        if not (0.0 < avg_active < 1.0):
            failures.append(
                f"{synth.__name__}: avg activity {avg_active:.3f} not in (0,1)"
            )

    # 5. C2 must produce a *test-period* burst that drops aggregate more
    #    severely than train-period equivalents
    trace_c2 = synth_c2_extreme_burst(pool, seed=0)
    train_steps = trace_c2.train_days * 24 * 60 // trace_c2.timestep_min
    train_activity = statistics.fmean(
        sum(row) / n_pool for row in trace_c2.der_active_status[:train_steps]
    )
    test_activity = statistics.fmean(
        sum(row) / n_pool for row in trace_c2.der_active_status[train_steps:]
    )
    if test_activity >= train_activity:
        failures.append(
            f"C2 test activity {test_activity:.3f} not lower than train {train_activity:.3f}"
        )

    # 6. C5 must show market-driven activity drop more in test than train
    trace_c5 = synth_c5_frequency_shift(pool, seed=0)
    n_market_train = sum(
        1 for e in trace_c5.events
        if e.trigger == "market" and e.start_min < trace_c5.train_days * 24 * 60
    )
    n_market_test = sum(
        1 for e in trace_c5.events
        if e.trigger == "market" and e.start_min >= trace_c5.train_days * 24 * 60
    )
    if not (n_market_test > n_market_train * 5):
        failures.append(
            f"C5 market events: train={n_market_train}, test={n_market_test} (expected test >> 5*train)"
        )

    # 7. perturb_pool_label_noise actually perturbs
    perturbed = perturb_pool_label_noise(pool, noise_rate=0.5, seed=1)
    n_diff_axes = sum(
        1 for d_orig, d_pert in zip(pool, perturbed)
        for e_o, e_p in zip(d_orig.trigger_exposure, d_pert.trigger_exposure)
        if e_o != e_p
    )
    expected = len(pool) * 4 * 0.5  # ~50% of all axes flipped
    if not (expected * 0.7 < n_diff_axes < expected * 1.3):
        failures.append(
            f"label noise rate=0.5 produced {n_diff_axes} flips, expected ~{expected:.0f}"
        )

    # 8. Default exposure encodes the trigger-orthogonality intuition:
    #    no two DER types share *all* trigger axes → the pool admits
    #    orthogonal subsets at K>=3
    by_axis_set = {tuple(v[:3]) for v in DEFAULT_EXPOSURE_K4.values()}
    if len(by_axis_set) < 3:
        failures.append(
            f"DEFAULT_EXPOSURE_K4 first 3 axes only have {len(by_axis_set)} distinct profiles — too few for orthogonality"
        )

    # ----- report
    if failures:
        print(f"FAIL: {len(failures)} issue(s):")
        for f in failures:
            print(f"  - {f}")
        return 1
    print("OK — MS-1 smoke test passed.")
    print(f"  pool size = {len(p1)}")
    print(f"  C1 train activity = {1 - sum(sum(not b for b in r) for r in trace_c2.der_active_status[:train_steps]) / (train_steps * n_pool):.3f}")
    print(f"  C2 test activity drop vs train = {train_activity - test_activity:.3f}")
    print(f"  C5 market events (train,test) = ({n_market_train}, {n_market_test})")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
