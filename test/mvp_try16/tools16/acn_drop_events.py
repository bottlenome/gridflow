"""Convert ACN-Data charging-session csv into a per-DER drop-event stream.

For try16 we treat each ACN ``stationID`` as a virtual DER.  A "drop"
event is the moment a charging session ends (= ``disconnectTime``);
between two consecutive sessions the DER is "offline" (= cannot serve
SLA).  This is the simplest mapping that preserves heavy-tail churn
statistics observed in ACN-Data: per-station session durations are
Pareto-distributed (Lee 2019, *ACN-Data: Analysis and Application*).

We expose:

  * ``DropEvent`` — frozen tuple
  * ``parse_acn_csv`` — list of DropEvent rows
  * ``build_pool`` — set of unique stationIDs (= DER pool)
  * ``presence_at`` — given (stationID, t) → bool active in session

The stream is deterministic given input csv path order; downstream
sweep iterates over multiple csv files (Q1 / Q2 / JPL / etc.) for
seed-style variance.
"""

from __future__ import annotations

import csv
import datetime as _dt
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class DropEvent:
    der_id: str       # = ACN stationID
    t_drop: float     # epoch seconds at session disconnect
    t_connect: float  # epoch seconds at session connect (= preceding "online" start)
    kwh: float        # delivered kWh during session


def _parse_rfc1123(s: str) -> float:
    if not s:
        return 0.0
    # ACN-Data uses RFC 1123 with "GMT" suffix
    try:
        dt = _dt.datetime.strptime(s, "%a, %d %b %Y %H:%M:%S GMT")
        return dt.replace(tzinfo=_dt.timezone.utc).timestamp()
    except ValueError:
        return 0.0


def parse_acn_csv(csv_path: Path) -> tuple[DropEvent, ...]:
    """Read one ACN session csv and return its drop event tuple."""
    rows: list[DropEvent] = []
    with open(csv_path, encoding="utf-8") as f:
        reader = csv.DictReader(f)
        for r in reader:
            t_c = _parse_rfc1123(r.get("connectionTime", ""))
            t_d = _parse_rfc1123(r.get("disconnectTime", ""))
            if t_d <= 0 or t_c <= 0 or t_d <= t_c:
                continue
            rows.append(DropEvent(
                der_id=r["stationID"],
                t_drop=t_d,
                t_connect=t_c,
                kwh=float(r.get("kWhDelivered", 0.0) or 0.0),
            ))
    rows.sort(key=lambda e: e.t_drop)
    return tuple(rows)


def build_pool(events: tuple[DropEvent, ...]) -> tuple[str, ...]:
    """Return sorted unique DER ids that appear in the event stream."""
    return tuple(sorted({e.der_id for e in events}))


def presence_intervals_for(
    der_id: str,
    events: tuple[DropEvent, ...],
) -> tuple[tuple[float, float], ...]:
    """Return tuple of (t_connect, t_drop) intervals for one DER (sorted)."""
    return tuple(
        (e.t_connect, e.t_drop) for e in events if e.der_id == der_id
    )


def is_active(intervals: tuple[tuple[float, float], ...], t: float) -> bool:
    """Binary search for any interval covering t."""
    for c, d in intervals:
        if c <= t <= d:
            return True
        if c > t:
            break
    return False


def inter_drop_intervals(
    der_id: str,
    events: tuple[DropEvent, ...],
) -> tuple[float, ...]:
    """Per-DER inter-drop intervals (= gaps between consecutive disconnects)."""
    drops = sorted(e.t_drop for e in events if e.der_id == der_id)
    return tuple(drops[i + 1] - drops[i] for i in range(len(drops) - 1))


def session_durations(
    der_id: str,
    events: tuple[DropEvent, ...],
) -> tuple[float, ...]:
    """Per-DER session durations (= disconnect - connect)."""
    return tuple(
        e.t_drop - e.t_connect for e in events if e.der_id == der_id
    )
