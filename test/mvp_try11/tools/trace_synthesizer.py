"""Churn-trace synthesis for the SDP experiments.

Spec: ``test/mvp_try11/implementation_plan.md`` §3.3 + §6.

A :class:`ChurnTrace` is a deterministic sequence of timestep-aligned
DER active/standby states plus the underlying trigger events. For each
timestep, ``der_active_status[t][j]`` is True iff DER ``j`` is currently
contributing to the VPP's aggregate output. A trigger event at time
``t_start`` causes every DER whose ``trigger_exposure`` includes that
trigger to become inactive for the trigger's duration.

Six trace classes (C1-C6) are defined in §6.2:

* C1 — single known trigger, one trigger axis at a time
* C2 — same as C1 but the test-period burst magnitude is 1.5x larger
* C3 — two known triggers fire simultaneously (at times)
* C4 — out-of-basis trigger (regulatory) appears only in test period
* C5 — frequency shift: market trigger rare in train, frequent in test
* C6 — label noise applied during DER pool synthesis (handled in der_pool)

C6 is *not* a trace-synthesis concern; it is realised by perturbing
``DER.trigger_exposure`` before the trace is consumed. So the
synthesiser produces only C1-C5 here.

Design (CLAUDE.md §0.1): Trace is fully frozen, all randomness driven
by an explicit seed; the trace value object encodes its full provenance
in :attr:`ChurnTrace.metadata`.
"""

from __future__ import annotations

import csv
import random
from dataclasses import dataclass
from pathlib import Path

from .der_pool import DER, TRIGGER_BASIS_K4, TRIGGER_BASIS_K5

# Default simulation horizon (spec §6.1)
DEFAULT_TIMESTEP_MIN: int = 5             # 5-minute steps
DEFAULT_TRAIN_DAYS: int = 14
DEFAULT_TEST_DAYS: int = 16
DEFAULT_HORIZON_DAYS: int = DEFAULT_TRAIN_DAYS + DEFAULT_TEST_DAYS
DEFAULT_SLA_TARGET_KW: float = 5_000.0   # 5 MW ancillary contract


@dataclass(frozen=True)
class TriggerEvent:
    """A single trigger firing.

    Attributes:
        trigger: Name of the trigger axis (must be in the basis).
        start_min: Minutes since trace start.
        duration_min: Minutes of activity.
        magnitude: Fraction of exposed DERs that actually churn (0..1).
            With magnitude<1 not every exposed DER drops; this models
            real-world stochasticity within a trigger event.
    """

    trigger: str
    start_min: float
    duration_min: float
    magnitude: float


@dataclass(frozen=True)
class ChurnTrace:
    """Full synthetic trace value object."""

    trace_id: str
    timestep_min: int
    horizon_days: int
    train_days: int
    test_days: int
    der_ids: tuple[str, ...]
    trigger_basis: tuple[str, ...]
    events: tuple[TriggerEvent, ...]
    der_active_status: tuple[tuple[bool, ...], ...]
    sla_target_kw: float
    seed: int

    @property
    def n_steps(self) -> int:
        """Total number of timesteps in the horizon."""
        return self.horizon_days * 24 * 60 // self.timestep_min

    @property
    def steps_per_day(self) -> int:
        return 24 * 60 // self.timestep_min


# ----------------------------------------------------------------- helpers


def _is_test_period(t_min: float, train_days: int) -> bool:
    return t_min >= train_days * 24 * 60


def _build_active_matrix(
    pool: tuple[DER, ...],
    events: tuple[TriggerEvent, ...],
    n_steps: int,
    timestep_min: int,
    basis: tuple[str, ...],
    seed: int,
) -> tuple[tuple[bool, ...], ...]:
    """Walk the trace step by step, applying trigger events to exposed DERs.

    Each DER starts active. When a trigger event fires, every exposed DER
    has probability ``event.magnitude`` of becoming inactive for the
    event's duration. The same RNG stream is reused for reproducibility.
    """
    rng = random.Random(seed)
    n_d = len(pool)
    # Project each DER's exposure to the experiment basis once
    from .der_pool import project_exposure
    exposure = tuple(project_exposure(d, basis) for d in pool)
    # Per-DER inactive-until timestep (exclusive)
    inactive_until = [0] * n_d
    matrix: list[tuple[bool, ...]] = []
    # Pre-sort events by start_min for efficiency
    events_sorted = sorted(events, key=lambda e: e.start_min)
    next_ev_i = 0
    for step in range(n_steps):
        t_min = step * timestep_min
        # Activate any new events at this step
        while next_ev_i < len(events_sorted) and events_sorted[next_ev_i].start_min <= t_min:
            ev = events_sorted[next_ev_i]
            if ev.trigger not in basis:
                # Out-of-basis (e.g., regulatory in K=4 trace) — DERs are not labelled
                # for it, so we randomly knock out 'magnitude' fraction of the entire
                # pool to model the unobserved exposure (realistic OOD behaviour).
                end_step = step + max(1, int(ev.duration_min // timestep_min))
                for j in range(n_d):
                    if rng.random() < ev.magnitude:
                        inactive_until[j] = max(inactive_until[j], end_step)
            else:
                axis_idx = basis.index(ev.trigger)
                end_step = step + max(1, int(ev.duration_min // timestep_min))
                for j in range(n_d):
                    if exposure[j][axis_idx] and rng.random() < ev.magnitude:
                        inactive_until[j] = max(inactive_until[j], end_step)
            next_ev_i += 1
        row = tuple(step >= inactive_until[j] for j in range(n_d))
        matrix.append(row)
    return tuple(matrix)


# ----------------------------------------------------------------- C1


def synth_c1_single_trigger(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    triggers: tuple[str, ...] = ("commute", "weather", "market"),
    events_per_day_per_trigger: int = 1,
    duration_min: float = 60.0,
    magnitude: float = 0.7,
) -> ChurnTrace:
    """C1 — one trigger axis at a time, regular daily occurrence.

    Each trigger fires ``events_per_day_per_trigger`` times per day at
    pseudo-random times. Magnitude (= fraction of exposed DERs that
    actually drop) is constant.
    """
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    for day in range(horizon_days):
        for trig in triggers:
            for _ in range(events_per_day_per_trigger):
                start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
                events.append(TriggerEvent(trig, start, duration_min, magnitude))
    events_t = tuple(events)
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C1",
        timestep_min=timestep_min,
        horizon_days=horizon_days,
        train_days=train_days,
        test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4,
        events=events_t,
        der_active_status=matrix,
        sla_target_kw=sla_kw,
        seed=seed,
    )


# ----------------------------------------------------------------- C2


def synth_c2_extreme_burst(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    train_magnitude: float = 0.5,
    test_burst_magnitude: float = 0.95,  # 1.9x train magnitude
    test_burst_count: int = 3,
    duration_min: float = 90.0,
) -> ChurnTrace:
    """C2 — same as C1 in train period, but test period contains
    significantly more extreme bursts on a known axis (weather)."""
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    # Train period: regular daily commute + weather, mild magnitude
    for day in range(train_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, train_magnitude))
    # Test period: same regular events plus a few extreme weather bursts
    for day in range(train_days, horizon_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, train_magnitude))
    for _ in range(test_burst_count):
        day = rng.randrange(train_days, horizon_days)
        start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
        events.append(TriggerEvent("weather", start, duration_min, test_burst_magnitude))
    events_t = tuple(events)
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C2", timestep_min=timestep_min, horizon_days=horizon_days,
        train_days=train_days, test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4, events=events_t,
        der_active_status=matrix, sla_target_kw=sla_kw, seed=seed,
    )


# ----------------------------------------------------------------- C3


def synth_c3_simultaneous(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    duration_min: float = 60.0,
    magnitude: float = 0.7,
) -> ChurnTrace:
    """C3 — pairs of triggers fire simultaneously (commute+weather,
    commute+market, weather+market) every other day in the test period."""
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    pairs = (("commute", "weather"), ("commute", "market"), ("weather", "market"))
    # Train: independent triggers (like C1)
    for day in range(train_days):
        for trig in ("commute", "weather", "market"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, magnitude))
    # Test: simultaneous pairs
    pair_idx = 0
    for day in range(train_days, horizon_days):
        if day % 2 == 0:
            pair = pairs[pair_idx % len(pairs)]
            pair_idx += 1
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            for trig in pair:
                events.append(TriggerEvent(trig, start, duration_min, magnitude))
        else:
            for trig in ("commute", "weather", "market"):
                start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
                events.append(TriggerEvent(trig, start, duration_min, magnitude))
    events_t = tuple(events)
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C3", timestep_min=timestep_min, horizon_days=horizon_days,
        train_days=train_days, test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4, events=events_t,
        der_active_status=matrix, sla_target_kw=sla_kw, seed=seed,
    )


# ----------------------------------------------------------------- C4


def synth_c4_out_of_basis(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    duration_min: float = 120.0,
    magnitude: float = 0.5,
    test_event_count: int = 4,
) -> ChurnTrace:
    """C4 — train period has only known triggers (commute, weather);
    test period introduces a new ``regulatory`` axis that is not in the
    K=4 basis. Method-side experiment must be told the basis is K=4 so
    the new trigger looks unlabelled (= classic OOD).
    """
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    # Train: known triggers
    for day in range(train_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, magnitude))
    # Test: known triggers continue + a few regulatory bursts
    for day in range(train_days, horizon_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, magnitude))
    for _ in range(test_event_count):
        day = rng.randrange(train_days, horizon_days)
        start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
        events.append(TriggerEvent("regulatory", start, duration_min, magnitude))
    events_t = tuple(events)
    # NOTE: we still tell the matrix builder to use K=4 basis so the
    # regulatory trigger falls into the "not-in-basis" branch and knocks
    # out random DERs — that is the OOD condition we want to study.
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C4", timestep_min=timestep_min, horizon_days=horizon_days,
        train_days=train_days, test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4, events=events_t,
        der_active_status=matrix, sla_target_kw=sla_kw, seed=seed,
    )


# ----------------------------------------------------------------- C5


def synth_c5_frequency_shift(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    duration_min: float = 60.0,
    magnitude: float = 0.7,
    train_market_per_week: int = 1,
    test_market_per_day: int = 2,
) -> ChurnTrace:
    """C5 — market trigger rare in train (weekly), frequent in test (twice/day).
    Other triggers behave normally."""
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    # Train: regular commute + weather; market only weekly
    for day in range(train_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, magnitude))
        # market: only on day-0 of each week (= roughly weekly)
        if day % 7 == 0:
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent("market", start, duration_min, magnitude))
    # Test: market becomes frequent
    for day in range(train_days, horizon_days):
        for trig in ("commute", "weather"):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent(trig, start, duration_min, magnitude))
        for _ in range(test_market_per_day):
            start = day * 24 * 60 + rng.uniform(0, 24 * 60 - duration_min)
            events.append(TriggerEvent("market", start, duration_min, magnitude))
    events_t = tuple(events)
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C5", timestep_min=timestep_min, horizon_days=horizon_days,
        train_days=train_days, test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4, events=events_t,
        der_active_status=matrix, sla_target_kw=sla_kw, seed=seed,
    )


# ----------------------------------------------------------------- C6 (label noise)


# ----------------------------------------------------------------- C7 (correlation reversal)


def synth_c7_correlation_reversal(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
    duration_min: float = 60.0,
    magnitude: float = 0.7,
) -> ChurnTrace:
    """C7 — correlation reversal between train and test periods.

    In the **train** period, ``commute`` and ``weather`` triggers always
    fire at *the same time of day* (~7 a.m.) — a strong positive
    correlation that data-driven methods (Markowitz, NN) learn from.

    In the **test** period, ``commute`` fires at 7 a.m. as before, but
    ``weather`` shifts to 11 p.m. — the correlation breaks. Methods that
    relied on the train-period correlation (= they reserved standby
    based on "weather and commute fire together") will fail in the test
    period: a 7 a.m. commute event consumes their orthogonal capacity,
    leaving nothing for the unexpected 11 p.m. weather event.

    SDP, by contrast, labels DERs by *physical exposure axis* and
    reserves orthogonal-to-each-axis capacity independently — its
    structural guarantee is correlation-invariant.
    """
    rng = random.Random(seed)
    horizon_days = train_days + test_days
    n_steps = horizon_days * 24 * 60 // timestep_min
    events: list[TriggerEvent] = []
    # Train: commute and weather both at ~7 a.m. each day (correlated)
    for day in range(train_days):
        morning_start = day * 24 * 60 + 7 * 60 + rng.uniform(-15, 15)
        events.append(TriggerEvent("commute", morning_start, duration_min, magnitude))
        events.append(TriggerEvent("weather", morning_start, duration_min, magnitude))
    # Test: commute at 7 a.m., weather shifted to 11 p.m. (decorrelated)
    for day in range(train_days, horizon_days):
        morning = day * 24 * 60 + 7 * 60 + rng.uniform(-15, 15)
        evening = day * 24 * 60 + 23 * 60 + rng.uniform(-15, 15)
        events.append(TriggerEvent("commute", morning, duration_min, magnitude))
        events.append(TriggerEvent("weather", evening, duration_min, magnitude))
    events_t = tuple(events)
    matrix = _build_active_matrix(
        pool, events_t, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id="C7", timestep_min=timestep_min, horizon_days=horizon_days,
        train_days=train_days, test_days=test_days,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4, events=events_t,
        der_active_status=matrix, sla_target_kw=sla_kw, seed=seed,
    )


# ----------------------------------------------------------------- C8 (scarce orthogonal)


def make_scarce_orthogonal_pool(
    pool: tuple[DER, ...],
    *,
    n_utility_keep: int = 5,
    cost_multiplier: float = 1.0,
) -> tuple[DER, ...]:
    """Modify a pool so that fully-orthogonal type (utility_battery) is
    scarce: only ``n_utility_keep`` utility batteries survive.

    Used to realise C8 trace condition: under scarcity, methods cannot
    converge to the trivial "buy 3 utility batteries" solution and the
    structural difference between SDP and baselines is forced into the
    open. ``cost_multiplier`` optionally inflates standby cost too.
    """
    out: list[DER] = []
    n_util_seen = 0
    for d in pool:
        if d.der_type == "utility_battery":
            n_util_seen += 1
            if n_util_seen > n_utility_keep:
                continue
            # Optionally bump cost
            if cost_multiplier != 1.0:
                d = DER(
                    der_id=d.der_id, der_type=d.der_type,
                    capacity_kw=d.capacity_kw,
                    contract_cost_active=d.contract_cost_active * cost_multiplier,
                    contract_cost_standby=d.contract_cost_standby * cost_multiplier,
                    trigger_exposure=d.trigger_exposure,
                )
        out.append(d)
    return tuple(out)


def synth_c8_scarce_orthogonal(
    pool: tuple[DER, ...],
    *,
    seed: int = 0,
    train_days: int = DEFAULT_TRAIN_DAYS,
    test_days: int = DEFAULT_TEST_DAYS,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    sla_kw: float = DEFAULT_SLA_TARGET_KW,
) -> ChurnTrace:
    """C8 trace = same content as C1 single-trigger.

    The C8 *condition* is realised by **modifying the pool** with
    :func:`make_scarce_orthogonal_pool` before solving. The trace itself
    is C1-shaped; what changes is the candidate-pool composition.
    """
    base = synth_c1_single_trigger(
        pool, seed=seed, train_days=train_days, test_days=test_days,
        timestep_min=timestep_min, sla_kw=sla_kw,
    )
    # Re-tag trace_id without mutating the frozen instance
    return ChurnTrace(
        trace_id="C8", timestep_min=base.timestep_min,
        horizon_days=base.horizon_days,
        train_days=base.train_days, test_days=base.test_days,
        der_ids=base.der_ids, trigger_basis=base.trigger_basis,
        events=base.events, der_active_status=base.der_active_status,
        sla_target_kw=base.sla_target_kw, seed=base.seed,
    )


# ----------------------------------------------------------------- C6 (label noise)


def perturb_pool_label_noise(
    pool: tuple[DER, ...],
    noise_rate: float,
    seed: int = 0,
) -> tuple[DER, ...]:
    """Flip each DER's exposure bit with probability ``noise_rate`` per axis.

    Used to realise C6 (DER pool label noise) — the trace is unchanged
    but the *labels visible to the optimiser* are perturbed.
    """
    if not (0.0 <= noise_rate <= 1.0):
        raise ValueError(f"noise_rate must be in [0,1], got {noise_rate}")
    rng = random.Random(seed)
    out: list[DER] = []
    for d in pool:
        flipped = tuple(
            (e ^ (rng.random() < noise_rate)) for e in d.trigger_exposure
        )
        out.append(
            DER(
                der_id=d.der_id,
                der_type=d.der_type,
                capacity_kw=d.capacity_kw,
                contract_cost_active=d.contract_cost_active,
                contract_cost_standby=d.contract_cost_standby,
                trigger_exposure=flipped,
            )
        )
    return tuple(out)


# ----------------------------------------------------------------- IO


def write_trace_summary_csv(trace: ChurnTrace, path: Path) -> None:
    """Write a per-step summary (active count) for visual inspection."""
    path.parent.mkdir(parents=True, exist_ok=True)
    with path.open("w", newline="", encoding="utf-8") as fh:
        writer = csv.writer(fh)
        writer.writerow(["step", "t_min", "active_count", "active_fraction"])
        n_d = len(trace.der_ids)
        for step, row in enumerate(trace.der_active_status):
            t_min = step * trace.timestep_min
            n_active = sum(row)
            writer.writerow([step, t_min, n_active, n_active / n_d if n_d else 0.0])
