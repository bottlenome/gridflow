"""ACN phase-invert: residential VPP proxy from workplace charging data.

The Caltech ACN-Data used by try11..try13 is *workplace* EV charging
(arrive 9am, depart 5pm). Residential VPP behaves with the **opposite
phase**: EVs are at home in the evening / night (= available to VPP)
and depart in the morning (= drop out). Reviewer N-7 (try11 zero-base
PWRS pass) flagged this phase mismatch as a semantic issue.

This module provides ``build_trace_from_acn_residential`` which
reuses the same ACN session CSV but **inverts** the meaning:

  * In ACN-workplace (try11): active iff in-session.
  * In residential phase: active iff **NOT** in-session (= at home).

Trigger events for residential are extracted from **connection time
clusters** (= mornings when many EVs leave home, simultaneously
disconnect from residential VPP). This is the residential analogue
of try11's disconnect-cluster commute event.

This is still a *proxy* — true residential VPP data (Pecan Street)
remains future work. But the phase semantics are now correct.
"""

from __future__ import annotations

import csv as _csv
import sys
from collections import Counter
from datetime import datetime, timedelta
from pathlib import Path

_TRY11 = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

from tools.der_pool import DER, TRIGGER_BASIS_K4  # noqa: E402
from tools.real_data_trace import _parse_acn_dt  # noqa: E402
from tools.trace_synthesizer import (  # noqa: E402
    DEFAULT_TIMESTEP_MIN,
    DEFAULT_TRAIN_DAYS,
    ChurnTrace,
    TriggerEvent,
)


def build_trace_from_acn_residential(
    sessions_csv: Path,
    pool: tuple[DER, ...],
    *,
    sla_kw: float,
    horizon_days: int | None = None,
    start_offset_days: int = 0,
    pairing_seed: int = 0,
    timestep_min: int = DEFAULT_TIMESTEP_MIN,
    train_days: int = DEFAULT_TRAIN_DAYS,
    seed: int = 0,
    trace_id: str = "REAL-acn-residential",
    site_timezone_offset_min: int = -8 * 60,
    morning_local_hours: tuple[int, ...] = (6, 7, 8, 9, 10),
    morning_event_min_connects: int = 3,
) -> ChurnTrace:
    """Build a ChurnTrace where ACN sessions are inverted to residential phase.

    For each pool DER paired with an ACN user:
      * matrix[step][j] = True iff the user is **NOT** in a workplace
        session at step (= at home, available to residential VPP).
    For unpaired DERs, the active state is True (synthetic baseline).

    Trigger events are extracted from connection time clusters
    occurring in the **local-morning window** (default 06:00-10:59),
    which represent the morning home → workplace commute.
    """
    import random as _random

    with open(sessions_csv, encoding="utf-8") as fh:
        sessions = list(_csv.DictReader(fh))
    if not sessions:
        raise ValueError(f"no sessions in {sessions_csv}")

    conns = [_parse_acn_dt(s["connectionTime"]) for s in sessions if s.get("connectionTime")]
    if not conns:
        raise ValueError("no parseable connectionTime")
    csv_t0 = min(conns).replace(hour=0, minute=0, second=0, microsecond=0)
    csv_t_end = max(_parse_acn_dt(s["disconnectTime"]) for s in sessions if s.get("disconnectTime"))
    csv_span_days = max(1, (csv_t_end - csv_t0).days + 1)

    t0 = csv_t0 + timedelta(days=start_offset_days)
    if horizon_days is None:
        horizon_days = csv_span_days - start_offset_days
    if horizon_days <= 0:
        raise ValueError(f"horizon_days={horizon_days}")
    t_end = t0 + timedelta(days=horizon_days)
    n_steps = horizon_days * 24 * 60 // timestep_min

    def _did(s: dict[str, str]) -> str:
        u = s.get("userID") or ""
        if u and u != "None":
            return f"u:{u}"
        return f"st:{s.get('stationID', '')}"

    window_sessions = []
    for s in sessions:
        try:
            conn = _parse_acn_dt(s["connectionTime"])
        except (KeyError, ValueError):
            continue
        if t0 <= conn < t_end:
            window_sessions.append(s)
    if not window_sessions:
        raise ValueError("no sessions in window")

    user_count: dict[str, int] = {}
    for s in window_sessions:
        user_count[_did(s)] = user_count.get(_did(s), 0) + 1
    sorted_users = sorted(user_count.items(), key=lambda kv: -kv[1])

    ev_indices = [i for i, d in enumerate(pool) if d.der_type == "residential_ev"]
    n_paired = min(len(ev_indices), len(sorted_users))

    if pairing_seed == 0 or n_paired >= len(sorted_users):
        chosen_users = [u for u, _ in sorted_users[:n_paired]]
    else:
        rng = _random.Random(pairing_seed)
        candidate_pool = [u for u, _ in sorted_users[: min(2 * n_paired, len(sorted_users))]]
        chosen_users = rng.sample(candidate_pool, n_paired)
    paired_user_ids = {chosen_users[k]: ev_indices[k] for k in range(n_paired)}

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
        intervals_by_pool_idx.setdefault(paired_user_ids[uid], []).append((start_step, end_step))

    n_d = len(pool)
    matrix: list[list[bool]] = [[True] * n_d for _ in range(n_steps)]
    for j in range(n_d):
        if j in intervals_by_pool_idx:
            # PHASE-INVERT: at workplace = NOT available; complement is True
            ranges = intervals_by_pool_idx[j]
            for s_step, e_step in ranges:
                for step in range(s_step, e_step):
                    if 0 <= step < n_steps:
                        matrix[step][j] = False  # at workplace → unavailable to home VPP

    # Morning commute events: cluster CONNECT times in local-morning window
    bin_min = 30
    bin_steps = bin_min // timestep_min
    connect_steps: list[int] = []
    for s in window_sessions:
        try:
            conn = _parse_acn_dt(s["connectionTime"])
        except (KeyError, ValueError):
            continue
        if not (t0 <= conn < t_end):
            continue
        local_dt = conn + timedelta(minutes=site_timezone_offset_min)
        if local_dt.hour not in morning_local_hours:
            continue
        step = int((conn - t0).total_seconds() // (timestep_min * 60))
        if 0 <= step < n_steps:
            connect_steps.append(step)
    morning_events: list[TriggerEvent] = []
    if connect_steps:
        per_bin: Counter[int] = Counter()
        for step in connect_steps:
            per_bin[step // bin_steps] += 1
        for bin_idx, count in per_bin.items():
            if count >= morning_event_min_connects:
                start_step = bin_idx * bin_steps
                magnitude = min(0.95, 0.20 + 0.05 * count)
                morning_events.append(
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
        events=tuple(sorted(morning_events, key=lambda e: e.start_min)),
        der_active_status=tuple(tuple(row) for row in matrix),
        sla_target_kw=sla_kw,
        seed=seed,
    )
