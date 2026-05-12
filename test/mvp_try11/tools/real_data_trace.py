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


def build_trace_from_decomposed_load_signal(
    ts: DatasetTimeSeries,
    pool: tuple[DER, ...],
    *,
    sla_kw: float,
    seed: int = 0,
    trace_id: str = "REAL-decomposed",
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    train_days: int = DEFAULT_TRAIN_DAYS,
    load_channel: str = "system_load_mw",
    commute_peak_hours_local: tuple[int, ...] = (16, 17, 18, 19, 20),
    timezone_offset_min: int = -8 * 60,  # PST (CAISO local time relative to UTC)
    weather_sigma_above: float = 1.0,
    weather_window_steps: int = 7 * 24 * 12,  # 7-day rolling window at 5-min
) -> ChurnTrace:
    """Trace from a load signal decomposed into commute / weather axes.

    Phase D-5 follow-up to address reviewer M-1 (semantic non-sequitur).
    Where ``build_trace_from_load_signal`` mapped any load excursion onto
    a single arbitrarily-chosen axis, this function decomposes the signal
    into two physically-motivated trigger classes:

      * ``commute`` events fire when the timestamp falls inside the
        local-time evening peak window (default 16:00–20:00 PT, the
        canonical California duck-curve evening rise). This corresponds
        physically to residential EV / VPP-DER drop-out as owners arrive
        home and use their cars.
      * ``weather`` events fire when the load exceeds a 7-day rolling
        baseline by more than ``weather_sigma_above`` standard deviations
        of the residual. This captures cold-snap / heat-wave deviations
        from a typical-week pattern (= the physical mechanism for
        heat-pump synchronous activation).

    Both decompositions are purely geometric on the load series; they do
    not require additional data sources. The split is the main
    semantic-alignment fix relative to the v1 single-axis mapping.
    """
    series = _channel(ts, load_channel)
    if not series:
        raise ValueError(f"empty channel '{load_channel}'")

    # ----- (1) Commute axis: diurnal peak window
    commute_events: list[TriggerEvent] = []
    timestamps_iso = ts.timestamps_iso
    # Walk timestamps; classify each step by local-hour. We do this without
    # a heavy datetime dependency by parsing the ISO string's hour field
    # (CAISO rows are ``YYYY-MM-DDTHH:MM:SS-00:00``).
    in_peak_run = False
    run_start_step = 0
    for step, t_iso in enumerate(timestamps_iso):
        try:
            utc_hour = int(t_iso[11:13])
            utc_minute = int(t_iso[14:16])
            local_total_min = (utc_hour * 60 + utc_minute + timezone_offset_min) % (24 * 60)
            local_hour = local_total_min // 60
        except (ValueError, IndexError):
            continue
        is_peak = local_hour in commute_peak_hours_local
        if is_peak and not in_peak_run:
            in_peak_run = True
            run_start_step = step
        elif not is_peak and in_peak_run:
            in_peak_run = False
            commute_events.append(
                TriggerEvent(
                    trigger="commute",
                    start_min=run_start_step * timestep_min,
                    duration_min=float((step - run_start_step) * timestep_min),
                    magnitude=0.50,
                )
            )
    if in_peak_run:
        commute_events.append(
            TriggerEvent(
                trigger="commute",
                start_min=run_start_step * timestep_min,
                duration_min=float((len(timestamps_iso) - run_start_step) * timestep_min),
                magnitude=0.50,
            )
        )

    # ----- (2) Weather axis: residual above rolling-7day baseline
    n = len(series)
    rolling: list[float] = []
    win = max(1, min(weather_window_steps, n))
    cumsum = 0.0
    for step in range(n):
        cumsum += series[step]
        if step >= win:
            cumsum -= series[step - win]
            rolling.append(cumsum / win)
        else:
            rolling.append(cumsum / (step + 1))
    residuals = tuple(series[i] - rolling[i] for i in range(n))
    if n > 1:
        mean_r = statistics.fmean(residuals)
        std_r = statistics.pstdev(residuals)
    else:
        mean_r, std_r = 0.0, 0.0
    threshold = mean_r + weather_sigma_above * std_r
    span = max(1.0, std_r if std_r > 0 else 1.0)
    weather_events = _events_from_threshold(
        residuals,
        timestep_min=timestep_min,
        threshold=threshold,
        above=True,
        trigger="weather",
        magnitude_scale=0.3 / span,
    )

    events = tuple(sorted(commute_events + list(weather_events), key=lambda e: e.start_min))
    n_steps_envelope, horizon_days, train_clamped = _trace_envelope(
        series, timestep_min, train_days
    )
    matrix = _build_active_matrix(
        pool, events, n_steps_envelope, timestep_min, TRIGGER_BASIS_K4, seed
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
    "build_trace_from_decomposed_load_signal",
    "build_trace_from_acn_sessions",
    "trace_summary",
)


def _parse_acn_dt(s: str) -> "datetime":
    """Parse an ACN-style ``Fri, 04 Jan 2019 00:16:32 GMT`` timestamp."""
    from datetime import datetime
    return datetime.strptime(s, "%a, %d %b %Y %H:%M:%S GMT")


def build_trace_from_acn_sessions(
    sessions_csv: "Path",
    pool: tuple[DER, ...],
    *,
    sla_kw: float,
    horizon_days: int | None = None,
    start_offset_days: int = 0,
    pairing_seed: int = 0,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    train_days: int = DEFAULT_TRAIN_DAYS,
    seed: int = 0,
    trace_id: str = "REAL-acn",
    site_timezone_offset_min: int = -8 * 60,  # Caltech PST
    commute_local_hours: tuple[int, ...] = (16, 17, 18, 19, 20),
    commute_event_min_disconnects: int = 3,
) -> ChurnTrace:
    """Build a ChurnTrace from Caltech ACN-Data charging sessions.

    Phase D-5 v2 (semantic-aligned real-DER validation, addresses
    reviewer M-1 / M-2). Each ACN session is an interval during which
    a real EV is plugged in; outside the session the EV is **not
    available** to the VPP — i.e. a real per-DER drop-out event. We
    map this directly onto the simulator's per-step active matrix:

      * Pool ``residential_ev`` DERs are paired 1-to-1 with the K most
        active ACN users (K = min(|residential_ev|, |unique users|)).
        At each step, the paired EV's active flag is True iff the ACN
        user has a session covering the step's timestamp.
      * ``residential_ev`` DERs beyond K, and DERs of any other type,
        follow a Gaussian-process-of-1 fallback: always active. This
        is conservative — only real-EV churn drives ``commute`` axis
        violations; non-EV DERs (heat pumps, batteries) are stable in
        this trace because ACN does not observe them. Synthetic
        weather / market axes remain available via separate traces.
      * TriggerEvents are emitted only for record-keeping (not used to
        re-generate the active matrix; the matrix IS the observation).
        We cluster disconnect timestamps within commute-local-hour
        windows; runs of ≥ ``commute_event_min_disconnects``
        disconnects within a 30-minute window become one
        ``commute`` TriggerEvent.

    Args:
        sessions_csv: Path to a CSV produced by ``tools/fetch_acn.py``.
        pool: The DER pool to drive (200-DER mixed-type expected).
        sla_kw: VPP SLA target (kW), passed through to ChurnTrace.
        horizon_days: Number of days to use from the data, starting at
            ``start_offset_days``. Defaults to the full span.
        start_offset_days: Offset (in days) from the first
            connectionTime in the CSV to slice the analysis window.
            Together with ``horizon_days`` lets a sweep walk multiple
            non-overlapping weeks of the same fixture (= reviewer M-3
            statistical-variance fix).
        pairing_seed: Seeds the user→DER pairing. ``pairing_seed=0``
            keeps the deterministic top-K-by-session-count rule
            (default, reproduces the v2 first run). For
            ``pairing_seed>0`` the top-2K most active users are
            sampled randomly to size K, so each seed sees a different
            subset of real EV behavior.
        site_timezone_offset_min: Used to identify the local-evening
            commute window from UTC ACN timestamps. Caltech is UTC-8.
        commute_local_hours: Local hours that count as the evening
            commute window (default 16:00-20:59).
        commute_event_min_disconnects: Minimum simultaneous disconnects
            within a 30-minute window for a TriggerEvent to be emitted.

    Returns:
        A ``ChurnTrace`` whose ``der_active_status`` is **observed
        per-EV availability** (real data) for the residential_ev slice
        of the pool.
    """
    import csv as _csv
    import random as _random
    from datetime import timedelta

    with open(sessions_csv, encoding="utf-8") as fh:
        sessions = list(_csv.DictReader(fh))
    if not sessions:
        raise ValueError(f"no sessions in {sessions_csv}")

    # Determine date range from data
    conns = [_parse_acn_dt(s["connectionTime"]) for s in sessions if s.get("connectionTime")]
    if not conns:
        raise ValueError("no parseable connectionTime fields")
    csv_t0 = min(conns).replace(hour=0, minute=0, second=0, microsecond=0)
    csv_t_end = max(_parse_acn_dt(s["disconnectTime"]) for s in sessions if s.get("disconnectTime"))
    csv_span_days = max(1, (csv_t_end - csv_t0).days + 1)

    # Slice the requested window
    t0 = csv_t0 + timedelta(days=start_offset_days)
    if horizon_days is None:
        horizon_days = csv_span_days - start_offset_days
    if horizon_days <= 0:
        raise ValueError(
            f"horizon_days={horizon_days} after start_offset_days={start_offset_days}; "
            f"CSV spans {csv_span_days} days"
        )
    t_end = t0 + timedelta(days=horizon_days)
    n_steps = horizon_days * 24 * 60 // timestep_min

    # Identify the K most active ACN users; fall back to stationID when userID is null
    def _did(s: dict[str, str]) -> str:
        u = s.get("userID") or ""
        if u and u != "None":
            return f"u:{u}"
        return f"st:{s.get('stationID', '')}"

    # Restrict to sessions whose connectionTime falls in [t0, t_end)
    window_sessions = []
    for s in sessions:
        try:
            conn = _parse_acn_dt(s["connectionTime"])
        except (KeyError, ValueError):
            continue
        if t0 <= conn < t_end:
            window_sessions.append(s)
    if not window_sessions:
        raise ValueError(
            f"no sessions in window [{t0.date()}, {t_end.date()}); "
            f"check start_offset_days / horizon_days"
        )

    user_session_count: dict[str, int] = {}
    for s in window_sessions:
        user_session_count[_did(s)] = user_session_count.get(_did(s), 0) + 1
    sorted_users = sorted(user_session_count.items(), key=lambda kv: -kv[1])

    ev_indices = [i for i, d in enumerate(pool) if d.der_type == "residential_ev"]
    n_paired = min(len(ev_indices), len(sorted_users))

    # pairing_seed=0 → deterministic top-K (legacy v2). pairing_seed>0 → random
    # subsample of K users from the top-min(2K, |users|) most active, so each
    # seed exercises a different real-EV subset.
    if pairing_seed == 0 or n_paired >= len(sorted_users):
        chosen_users = [u for u, _ in sorted_users[:n_paired]]
    else:
        rng = _random.Random(pairing_seed)
        candidate_pool = [u for u, _ in sorted_users[: min(2 * n_paired, len(sorted_users))]]
        chosen_users = rng.sample(candidate_pool, n_paired)
    paired_user_ids = {chosen_users[k]: ev_indices[k] for k in range(n_paired)}

    # Group sessions by user → list of (start_step, end_step) intervals
    intervals_by_pool_idx: dict[int, list[tuple[int, int]]] = {}
    for s in window_sessions:
        uid = _did(s)
        if uid not in paired_user_ids:
            continue
        try:
            conn = _parse_acn_dt(s["connectionTime"])
            disc = _parse_acn_dt(s["disconnectTime"])
        except (KeyError, ValueError):
            continue
        start_step = max(0, int((conn - t0).total_seconds() // (timestep_min * 60)))
        end_step = max(start_step, int((disc - t0).total_seconds() // (timestep_min * 60)))
        end_step = min(end_step, n_steps)
        if start_step >= n_steps:
            continue
        idx = paired_user_ids[uid]
        intervals_by_pool_idx.setdefault(idx, []).append((start_step, end_step))

    # Build per-step active matrix (n_steps × |pool|)
    n_d = len(pool)
    matrix: list[list[bool]] = [[True] * n_d for _ in range(n_steps)]
    for j in range(n_d):
        if j in intervals_by_pool_idx:
            ranges = intervals_by_pool_idx[j]
            for step in range(n_steps):
                matrix[step][j] = False
            for s_step, e_step in ranges:
                for step in range(s_step, e_step):
                    if 0 <= step < n_steps:
                        matrix[step][j] = True

    # Detect commute TriggerEvents from disconnect clusters within the window
    commute_events: list[TriggerEvent] = []
    bin_min = 30
    bin_steps = bin_min // timestep_min
    disconnect_steps: list[int] = []
    for s in window_sessions:
        try:
            disc = _parse_acn_dt(s["disconnectTime"])
        except (KeyError, ValueError):
            continue
        if not (t0 <= disc < t_end):
            continue
        local_dt = disc + timedelta(minutes=site_timezone_offset_min)
        if local_dt.hour not in commute_local_hours:
            continue
        step = int((disc - t0).total_seconds() // (timestep_min * 60))
        if 0 <= step < n_steps:
            disconnect_steps.append(step)
    if disconnect_steps:
        from collections import Counter
        per_bin: Counter[int] = Counter()
        for step in disconnect_steps:
            per_bin[step // bin_steps] += 1
        for bin_idx, count in per_bin.items():
            if count >= commute_event_min_disconnects:
                start_step = bin_idx * bin_steps
                magnitude = min(0.95, 0.20 + 0.05 * count)
                commute_events.append(
                    TriggerEvent(
                        trigger="commute",
                        start_min=start_step * timestep_min,
                        duration_min=float(bin_min),
                        magnitude=float(magnitude),
                    )
                )

    train_clamped = min(train_days, max(0, horizon_days - 1)) if horizon_days >= 2 else 0
    return ChurnTrace(
        trace_id=trace_id,
        timestep_min=timestep_min,
        horizon_days=horizon_days,
        train_days=train_clamped,
        test_days=horizon_days - train_clamped,
        der_ids=tuple(d.der_id for d in pool),
        trigger_basis=TRIGGER_BASIS_K4,
        events=tuple(sorted(commute_events, key=lambda e: e.start_min)),
        der_active_status=tuple(tuple(row) for row in matrix),
        sla_target_kw=sla_kw,
        seed=seed,
    )
