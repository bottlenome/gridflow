"""Fetch Caltech ACN-Data EV charging sessions via the public REST API.

ACN-Data (Lee et al. 2019, "ACN-Data: Analysis and Application of an
Open EV Charging Dataset") is the gold-standard public dataset for
**per-EV individual** charging behaviour in academic research. Each
session record carries:

  * ``sessionID``        — unique session identifier
  * ``stationID``        — physical charging port
  * ``userID``           — anonymised driver (when known)
  * ``connectionTime``   — when the EV plugged in   (= became available)
  * ``disconnectTime``   — when the EV unplugged    (= drop-out event)
  * ``kWhDelivered``     — energy delivered (kWh)
  * ``timezone``         — timezone of the site
  * ``siteID`` / ``clusterID`` / ``spaceID`` — physical layout metadata

This is a direct match for try11's per-DER ``churn`` semantic:
each session is a contiguous interval during which the EV is
**available to the VPP**, and a disconnect event is the physical
realisation of a per-DER ``commute`` trigger.

The ACN API requires a public token (no registration; ``DEMO_TOKEN``
documented in https://ev.caltech.edu/dataset_api works for read).
The default site is ``caltech`` (most populous, 31k+ sessions).
``jpl`` and ``office001`` are alternative sites.

Reference:
  * Z. Lee, T. Li, S. H. Low, "ACN-Data: Analysis and Application of
    an Open EV Charging Dataset", e-Energy 2019.
  * https://ev.caltech.edu/dataset

Usage:

    PYTHONPATH=src .venv/bin/python -m tools.fetch_acn \\
        --start 2019-01-01 --end 2019-02-01 \\
        --out $GRIDFLOW_DATASET_ROOT/acn/caltech_sessions/v1/data.csv
"""

from __future__ import annotations

import argparse
import base64
import csv
import json
import sys
import time
import urllib.error
import urllib.request
from datetime import date, datetime
from pathlib import Path

ACN_API_URL = "https://ev.caltech.edu/api/v1/sessions"
DEFAULT_SITE = "caltech"
PUBLIC_TOKEN = "DEMO_TOKEN"
PAGE_SIZE = 200  # ACN's per-page max; minimises HTTP calls
RATE_LIMIT_SECONDS = 0.5
REQUEST_TIMEOUT_S = 60


def _http_get_json(url: str, token: str) -> dict[str, object]:
    """Fetch JSON via HTTP Basic auth with retry on rate-limit / transient.

    ACN-Data uses HTTP Basic with the token as the username (empty
    password). Retry policy mirrors ``fetch_caiso`` — exponential
    backoff up to ~5 minutes for 401 / 429 / 5xx.
    """
    auth = base64.b64encode(f"{token}:".encode()).decode()
    req = urllib.request.Request(
        url,
        headers={
            "User-Agent": "gridflow/0.1",
            "Authorization": f"Basic {auth}",
        },
    )
    last_err: Exception | None = None
    for attempt, sleep_s in enumerate((0, 5, 30, 60, 120, 240), start=1):
        if sleep_s > 0:
            print(
                f"    transient error; sleeping {sleep_s}s before attempt {attempt}",
                file=sys.stderr,
            )
            time.sleep(sleep_s)
        try:
            with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
                return json.loads(resp.read())
        except urllib.error.HTTPError as e:
            last_err = e
            if e.code in (401, 429) or 500 <= e.code < 600:
                continue
            raise RuntimeError(f"ACN HTTP {e.code} for {url}") from e
        except urllib.error.URLError as e:
            last_err = e
            continue
    raise RuntimeError(f"ACN request failed after retries: {last_err}; URL={url}")


def _format_acn_iso(d: date) -> str:
    """ACN expects RFC-1123 dates inside the ``where=`` clause."""
    return datetime.combine(d, datetime.min.time()).strftime("%a, %d %b %Y %H:%M:%S GMT")


def fetch_acn_sessions(
    start: date,
    end: date,
    *,
    site: str = DEFAULT_SITE,
    token: str = PUBLIC_TOKEN,
    page_size: int = PAGE_SIZE,
) -> list[dict[str, object]]:
    """Fetch all sessions with ``connectionTime`` in ``[start, end)``."""
    where = (
        f'connectionTime>="{_format_acn_iso(start)}" '
        f'and connectionTime<"{_format_acn_iso(end)}"'
    )
    base = f"{ACN_API_URL}/{site}"
    sessions: list[dict[str, object]] = []
    page = 1
    while True:
        url = (
            f"{base}?where={urllib.parse.quote(where)}"
            f"&page={page}&page_size={page_size}&pretty"
        )
        if page > 1:
            time.sleep(RATE_LIMIT_SECONDS)
        print(f"  GET page {page}", file=sys.stderr)
        payload = _http_get_json(url, token)
        items = payload.get("_items") or []
        if not isinstance(items, list):
            break
        sessions.extend(items)
        meta = payload.get("_meta") or {}
        total = int(meta.get("total", 0))
        max_results = int(meta.get("max_results", page_size))
        if len(sessions) >= total or len(items) < max_results:
            break
        page += 1
    print(f"  fetched {len(sessions)} sessions", file=sys.stderr)
    return sessions


def write_csv(sessions: list[dict[str, object]], out_path: Path) -> None:
    """Persist sessions in the schema the trace builder expects.

    Columns: sessionID, stationID, userID, connectionTime, disconnectTime,
    doneChargingTime, kWhDelivered, siteID, clusterID, spaceID, timezone.
    Rows are sorted by connectionTime so downstream binning is monotonic.
    """
    keys = (
        "sessionID",
        "stationID",
        "userID",
        "connectionTime",
        "disconnectTime",
        "doneChargingTime",
        "kWhDelivered",
        "siteID",
        "clusterID",
        "spaceID",
        "timezone",
    )

    def _key(s: dict[str, object]) -> str:
        v = s.get("connectionTime") or ""
        return str(v)

    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(keys)
        for s in sorted(sessions, key=_key):
            writer.writerow(["" if s.get(k) is None else str(s.get(k)) for k in keys])


# urllib.parse imported lazily so it's resolved alongside fetch_acn_sessions
import urllib.parse  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD exclusive")
    parser.add_argument("--site", default=DEFAULT_SITE, choices=("caltech", "jpl", "office001"))
    parser.add_argument("--token", default=PUBLIC_TOKEN)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end <= start:
        raise SystemExit("--end must be strictly after --start")
    if (end - start).days > 366:
        raise SystemExit(
            "Range > 1 year — split into smaller windows so progress is checkpointable"
        )

    print(
        f"[fetch_acn] site={args.site} from {start} to {end} → {args.out}",
        file=sys.stderr,
    )
    sessions = fetch_acn_sessions(
        start, end, site=args.site, token=args.token,
    )
    if not sessions:
        print("[fetch_acn] no sessions returned for this range", file=sys.stderr)
        return 1
    write_csv(sessions, args.out)
    print(
        f"[fetch_acn] wrote {len(sessions)} sessions to {args.out}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
