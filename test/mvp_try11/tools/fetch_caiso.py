"""Fetch CAISO 5-minute system load via OASIS public API.

Phase D-5 (NEXT_STEPS.md §7.2.1) — fetcher script. Runs **at the
contributor's machine** with network access; the smoke test for the
real-data trace adapter (``_msD5_smoke_test.py``) does NOT call this
because the gridflow CI environment has no public-API egress.

Usage:

    PYTHONPATH=src .venv/bin/python -m tools.fetch_caiso \\
        --start 2024-01-01 --end 2024-01-08 \\
        --out $GRIDFLOW_DATASET_ROOT/caiso/system_load_5min/v1/data.csv

The output CSV is in the format expected by
:class:`gridflow.adapter.dataset.CAISOLoader` —
``ts_iso, system_load_mw`` columns, 5-minute resolution. The script
chunks queries at 30 days max per request (CAISO API limit) and
applies a polite 1.5 s sleep between calls (CAISO rate-limits at
≈ 60 queries / hour).

Reference:
  https://www.caiso.com/Documents/OASISAPISpecification.pdf
  Query name SLD_FCST returns system-load forecast; for actual
  realised load use ENE_HASP (= hour-ahead) or PRC_RTPD_LMP joined
  with metering. Adjust ``QUERY_NAME`` per the data vintage you need.
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
import time
import urllib.error
import urllib.request
import zipfile
from datetime import date, datetime, timedelta
from pathlib import Path

CAISO_OASIS_URL = "https://oasis.caiso.com/oasisapi/SingleZip"
DEFAULT_QUERY_NAME = "SLD_FCST"  # System-Load forecast; alt: ENE_HASP
MAX_DAYS_PER_QUERY = 30
RATE_LIMIT_SECONDS = 1.5
REQUEST_TIMEOUT_S = 60


def _iso_z(ts: datetime) -> str:
    """CAISO expects ``YYYYMMDDThh:mm-0000`` in the URL."""
    return ts.strftime("%Y%m%dT%H:%M-0000")


def _chunk_ranges(start: date, end: date) -> list[tuple[date, date]]:
    """Split [start, end) into ≤ MAX_DAYS_PER_QUERY chunks."""
    out: list[tuple[date, date]] = []
    cur = start
    while cur < end:
        nxt = min(end, cur + timedelta(days=MAX_DAYS_PER_QUERY))
        out.append((cur, nxt))
        cur = nxt
    return out


def _fetch_one_chunk(
    chunk_start: datetime,
    chunk_end: datetime,
    query_name: str = DEFAULT_QUERY_NAME,
) -> list[tuple[str, float]]:
    """Fetch one chunk and parse to ``[(ts_iso, value_mw), ...]``."""
    url = (
        f"{CAISO_OASIS_URL}?queryname={query_name}"
        f"&startdatetime={_iso_z(chunk_start)}"
        f"&enddatetime={_iso_z(chunk_end)}"
        f"&resultformat=6"  # CSV
    )
    print(f"  GET {url}", file=sys.stderr)
    req = urllib.request.Request(url, headers={"User-Agent": "gridflow/0.1"})
    try:
        with urllib.request.urlopen(req, timeout=REQUEST_TIMEOUT_S) as resp:
            payload = resp.read()
    except urllib.error.HTTPError as e:
        raise RuntimeError(f"CAISO HTTP {e.code} for {url}") from e
    except urllib.error.URLError as e:
        raise RuntimeError(f"CAISO URL error for {url}: {e.reason}") from e

    # Response is a ZIP with one or more CSV files; parse and merge
    rows: list[tuple[str, float]] = []
    with zipfile.ZipFile(io.BytesIO(payload)) as zf:
        for name in zf.namelist():
            if not name.lower().endswith(".csv"):
                continue
            with zf.open(name) as fh:
                reader = csv.DictReader(io.TextIOWrapper(fh, encoding="utf-8"))
                for row in reader:
                    # The exact column names vary by query_name. The
                    # canonical OASIS schema for SLD_FCST is
                    # INTERVALSTARTTIME_GMT (ISO) and MW (load value).
                    ts_raw = (
                        row.get("INTERVALSTARTTIME_GMT")
                        or row.get("OPR_DT")
                        or row.get("ts_iso")
                    )
                    val_raw = (
                        row.get("MW")
                        or row.get("LOAD_VALUE")
                        or row.get("value")
                    )
                    if ts_raw is None or val_raw is None:
                        continue
                    try:
                        rows.append((ts_raw, float(val_raw)))
                    except ValueError:
                        continue
    return rows


def fetch_caiso_load(
    start: date,
    end: date,
    *,
    query_name: str = DEFAULT_QUERY_NAME,
) -> list[tuple[str, float]]:
    """Fetch the load series for ``[start, end)`` and return rows."""
    rows: list[tuple[str, float]] = []
    for i, (chunk_s, chunk_e) in enumerate(_chunk_ranges(start, end)):
        if i > 0:
            time.sleep(RATE_LIMIT_SECONDS)
        rows.extend(
            _fetch_one_chunk(
                datetime.combine(chunk_s, datetime.min.time()),
                datetime.combine(chunk_e, datetime.min.time()),
                query_name=query_name,
            )
        )
    rows.sort(key=lambda r: r[0])
    return rows


def write_csv(rows: list[tuple[str, float]], out_path: Path) -> None:
    """Write rows in the schema CAISOLoader expects."""
    out_path.parent.mkdir(parents=True, exist_ok=True)
    with out_path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.writer(fh)
        writer.writerow(["ts_iso", "system_load_mw"])
        writer.writerows(rows)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--start", required=True, help="YYYY-MM-DD inclusive")
    parser.add_argument("--end", required=True, help="YYYY-MM-DD exclusive")
    parser.add_argument("--query", default=DEFAULT_QUERY_NAME)
    parser.add_argument("--out", required=True, type=Path)
    args = parser.parse_args()

    start = date.fromisoformat(args.start)
    end = date.fromisoformat(args.end)
    if end <= start:
        raise SystemExit("--end must be strictly after --start")
    if (end - start).days > 365:
        raise SystemExit(
            "Range > 1 year — split into smaller windows to stay polite "
            "with CAISO rate limits"
        )

    print(
        f"[fetch_caiso] {args.query} from {start} to {end} → {args.out}",
        file=sys.stderr,
    )
    rows = fetch_caiso_load(start, end, query_name=args.query)
    if not rows:
        print(
            "[fetch_caiso] no rows returned — query name may not match the "
            "data vintage. See CAISO OASIS API spec for the correct name.",
            file=sys.stderr,
        )
        return 1
    write_csv(rows, args.out)
    print(f"[fetch_caiso] wrote {len(rows)} rows to {args.out}", file=sys.stderr)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
