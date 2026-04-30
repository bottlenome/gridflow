"""Build a ``ChurnTrace`` from a registered ``DatasetTimeSeries``.

Phase D-5 (NEXT_STEPS.md §7) — the bridge from real-world signals to
the simulator's expected interface. PWRS reviewer C2 demands that at
least one source of evidence be drawn from real data, not from
synthetic generators alone. This module turns any registered loader's
output (CAISO load, AEMO VPP availability, Pecan Street EV trace,
etc.) into a ``ChurnTrace`` that ``grid_simulate`` consumes the same
way as the synthetic ``synth_c1``/``synth_c2``/etc. traces.

Two construction paths are exposed:

  * :func:`build_trace_from_active_count` — when the dataset already
    carries an ``aggregate_active_count`` channel (Pecan Street, AEMO
    Tesla VPP). The series is interpreted as the per-step *number of
    DERs available*; the trace is built by computing a per-step
    drop-out fraction and synthesising a single-axis ``commute`` event
    whenever availability dips below a configurable threshold.
  * :func:`build_trace_from_load_signal` — when the dataset is a load
    or price series (CAISO, JEPX). A high-load period (e.g. value
    above ``mean + sigma * std``) is interpreted as a stress event
    that fires the chosen trigger axis with magnitude proportional
    to the deviation.

Both functions return a value-object ``ChurnTrace`` indistinguishable
in shape from a synthetic trace, so all downstream harnesses
(``grid_simulate``, ``run_phase1_multifeeder``) work unchanged.
"""

from __future__ import annotations

import statistics

from gridflow.domain.dataset import DatasetTimeSeries

from .der_pool import DER, TRIGGER_BASIS_K4
from .trace_synthesizer import (
    DEFAULT_TIMESTEP_MIN,
    DEFAULT_TRAIN_DAYS,
    ChurnTrace,
    TriggerEvent,
    _build_active_matrix,
)


def _channel(ts: DatasetTimeSeries, name: str) -> tuple[float, ...]:
    for ch_name, _unit, values in ts.channels:
        if ch_name == name:
            return values
    raise KeyError(
        f"channel '{name}' not present in dataset {ts.metadata.dataset_id}; "
        f"available: {[c[0] for c in ts.channels]}"
    )


def _events_from_threshold(
    values: tuple[float, ...],
    *,
    timestep_min: int,
    threshold: float,
    above: bool,
    trigger: str,
    magnitude_scale: float,
    base_magnitude: float = 0.4,
) -> tuple[TriggerEvent, ...]:
    """Convert a per-step boolean condition into ``TriggerEvent`` runs.

    Consecutive steps satisfying the condition are merged into a single
    event whose duration spans the run; the magnitude scales with the
    peak deviation in the run, clamped to [base_magnitude, 0.95].
    """
    events: list[TriggerEvent] = []
    in_event = False
    start_step = 0
    peak_dev = 0.0
    for step, v in enumerate(values):
        violates = (v >= threshold) if above else (v <= threshold)
        deviation = (
            (v - threshold) if above else (threshold - v)
        ) if threshold != 0 else 0.0
        if violates:
            if not in_event:
                in_event = True
                start_step = step
                peak_dev = deviation
            else:
                peak_dev = max(peak_dev, deviation)
        elif in_event:
            duration_min = (step - start_step) * timestep_min
            magnitude = max(
                base_magnitude,
                min(0.95, base_magnitude + magnitude_scale * peak_dev),
            )
            events.append(
                TriggerEvent(
                    trigger=trigger,
                    start_min=start_step * timestep_min,
                    duration_min=float(duration_min),
                    magnitude=float(magnitude),
                )
            )
            in_event = False
            peak_dev = 0.0
    # Close trailing event
    if in_event:
        duration_min = (len(values) - start_step) * timestep_min
        magnitude = max(
            base_magnitude,
            min(0.95, base_magnitude + magnitude_scale * peak_dev),
        )
        events.append(
            TriggerEvent(
                trigger=trigger,
                start_min=start_step * timestep_min,
                duration_min=float(duration_min),
                magnitude=float(magnitude),
            )
        )
    return tuple(events)


def _trace_envelope(
    values: tuple[float, ...],
    timestep_min: int,
    train_days: int,
) -> tuple[int, int, int]:
    """Return ``(n_steps, horizon_days, train_days_clamped)``.

    The dataset may not be aligned with ``DEFAULT_TRAIN_DAYS``; we use
    its full length and clamp the train period to (length - 1 day) when
    necessary so the test split remains non-empty.
    """
    n_steps = len(values)
    steps_per_day = (24 * 60) // timestep_min
    horizon_days = max(1, n_steps // steps_per_day)
    if horizon_days < 2:
        return n_steps, horizon_days, max(0, horizon_days - 1)
    train = min(train_days, horizon_days - 1)
    return n_steps, horizon_days, train


def build_trace_from_active_count(
    ts: DatasetTimeSeries,
    pool: tuple[DER, ...],
    *,
    sla_kw: float,
    seed: int = 0,
    trace_id: str = "REAL-active",
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    train_days: int = DEFAULT_TRAIN_DAYS,
    count_channel: str = "aggregate_active_count",
    trigger: str = "commute",
    threshold_quantile: float = 0.20,
) -> ChurnTrace:
    """Trace from a dataset's per-step active-count signal.

    Drop-outs are detected when the active-count series falls below
    its ``threshold_quantile`` (default 20-th percentile). Each contiguous
    run of low-availability steps becomes one ``TriggerEvent`` on
    ``trigger`` axis, with magnitude scaled by the deviation.
    """
    counts = _channel(ts, count_channel)
    if not counts:
        raise ValueError(f"empty channel '{count_channel}'")

    sorted_counts = sorted(counts)
    idx = max(0, min(len(sorted_counts) - 1,
                     int(threshold_quantile * (len(sorted_counts) - 1))))
    threshold = float(sorted_counts[idx])

    median = statistics.median(counts)
    span = max(1.0, abs(median - threshold))
    events = _events_from_threshold(
        counts,
        timestep_min=timestep_min,
        threshold=threshold,
        above=False,  # below-threshold = drop-out
        trigger=trigger,
        magnitude_scale=0.4 / span,
    )

    n_steps, horizon_days, train_clamped = _trace_envelope(
        counts, timestep_min, train_days
    )
    matrix = _build_active_matrix(
        pool, events, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id=trace_id,
        timestep_min=timestep_min,
        horizon_days=horizon_days,
        train_days=train_clamped,
        test_days=horizon_days - train_clamped,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4,
        events=events,
        der_active_status=matrix,
        sla_target_kw=sla_kw,
        seed=seed,
    )


def build_trace_from_load_signal(
    ts: DatasetTimeSeries,
    pool: tuple[DER, ...],
    *,
    sla_kw: float,
    seed: int = 0,
    trace_id: str = "REAL-load",
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    train_days: int = DEFAULT_TRAIN_DAYS,
    load_channel: str = "system_load_mw",
    trigger: str = "weather",
    sigma_above: float = 1.0,
) -> ChurnTrace:
    """Trace from a load / price signal.

    Each contiguous run of steps where the signal exceeds
    ``mean + sigma_above * std`` becomes one ``TriggerEvent`` on
    ``trigger`` axis. The magnitude grows with the peak deviation,
    capped at 0.95.
    """
    series = _channel(ts, load_channel)
    if not series:
        raise ValueError(f"empty channel '{load_channel}'")

    mean = statistics.fmean(series)
    sd = statistics.pstdev(series) if len(series) > 1 else 0.0
    threshold = mean + sigma_above * sd
    span = max(1.0, sd if sd > 0 else 1.0)
    events = _events_from_threshold(
        series,
        timestep_min=timestep_min,
        threshold=threshold,
        above=True,
        trigger=trigger,
        magnitude_scale=0.3 / span,
    )

    n_steps, horizon_days, train_clamped = _trace_envelope(
        series, timestep_min, train_days
    )
    matrix = _build_active_matrix(
        pool, events, n_steps, timestep_min, TRIGGER_BASIS_K4, seed
    )
    return ChurnTrace(
        trace_id=trace_id,
        timestep_min=timestep_min,
        horizon_days=horizon_days,
        train_days=train_clamped,
        test_days=horizon_days - train_clamped,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4,
        events=events,
        der_active_status=matrix,
        sla_target_kw=sla_kw,
        seed=seed,
    )


def trace_summary(trace: ChurnTrace) -> dict[str, object]:
    """Compact summary of a built trace, useful for logs / smoke tests."""
    n_active_per_step = [sum(1 for v in row if v) for row in trace.der_active_status]
    pool_size = len(trace.der_ids)
    avail_min = min(n_active_per_step) if n_active_per_step else 0
    avail_max = max(n_active_per_step) if n_active_per_step else 0
    avail_mean = (
        statistics.fmean(n_active_per_step) if n_active_per_step else 0.0
    )
    triggers_count: dict[str, int] = {}
    for ev in trace.events:
        triggers_count[ev.trigger] = triggers_count.get(ev.trigger, 0) + 1
    return {
        "trace_id": trace.trace_id,
        "n_steps": trace.n_steps,
        "horizon_days": trace.horizon_days,
        "n_events": len(trace.events),
        "events_by_trigger": triggers_count,
        "pool_size": pool_size,
        "availability_min": avail_min,
        "availability_max": avail_max,
        "availability_mean": round(avail_mean, 1),
        "min_avail_fraction": round(avail_min / pool_size, 4) if pool_size else 0.0,
    }


# Re-export for convenience
__all__ = (
    "build_trace_from_active_count",
    "build_trace_from_load_signal",
    "trace_summary",
)
