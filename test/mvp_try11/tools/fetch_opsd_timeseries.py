"""Fetch Open Power System Data (OPSD) hourly time-series CSV (EU, public).

OPSD is the gold-standard public dataset for European national grid
hourly load and generation by source.  Covers 37 European countries,
hourly for 2010-present (with patches for missing data).

Per-country channels (subset):
  * load_actual_entsoe_transparency        — observed total load (MW)
  * solar_capacity                          — installed solar PV (MW)
  * wind_capacity                           — installed wind (MW)
  * solar_generation_actual                 — observed solar (MW)
  * wind_onshore_generation_actual          — observed wind (MW)
  * wind_offshore_generation_actual         — observed wind (MW)
  * price_day_ahead                         — day-ahead price (€/MWh)

This is **directly relevant** for VPP standby modelling: hourly load
fluctuations and renewable generation drops are exactly the stress
events that VPP services respond to, and the data spans 14+ years
giving rich heavy-tail empirical statistics.

Reference:
  * https://open-power-system-data.org/
  * License: CC-BY-4.0 (per OPSD)

Usage:

    python -m fetch_opsd_timeseries --variant 60min --out ./data/opsd/

Variants:
  * 60min   — hourly (~140 MB), default
  * 30min   — half-hourly (UK-focused, ~150 MB)
  * 15min   — quarter-hourly (DE-focused, ~80 MB)
"""

from __future__ import annotations

import argparse
import sys
import urllib.error
import urllib.request
from pathlib import Path

OPSD_URL = (
    "https://data.open-power-system-data.org/time_series/"
    "{snapshot}/time_series_{variant}_singleindex.csv"
)
DEFAULT_SNAPSHOT = "2020-10-06"   # last full release with 14-year span
TIMEOUT_S = 900


def fetch(variant: str, snapshot: str, out_dir: Path,
          overwrite: bool = False) -> Path | None:
    url = OPSD_URL.format(snapshot=snapshot, variant=variant)
    out_path = out_dir / f"opsd_time_series_{variant}_{snapshot}.csv"
    if out_path.exists() and not overwrite:
        print(f"[fetch_opsd] skip (exists): {out_path.name}")
        return out_path
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "gridflow-fetcher/0.1"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
        out_path.write_bytes(data)
        print(f"[fetch_opsd] {out_path.name}: {len(data)//1024//1024} MB")
        return out_path
    except urllib.error.HTTPError as e:
        print(f"[fetch_opsd] HTTPError: {e.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[fetch_opsd] URLError: {e.reason}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--variant", default="60min", choices=("60min", "30min", "15min"))
    p.add_argument("--snapshot", default=DEFAULT_SNAPSHOT,
                   help=f"OPSD release date (default: {DEFAULT_SNAPSHOT})")
    p.add_argument("--out", default="./data/opsd")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    res = fetch(args.variant, args.snapshot, out_dir, overwrite=args.overwrite)
    return 0 if res else 1


if __name__ == "__main__":
    sys.exit(main())
