"""Fetch AEMO NEM 5-minute price-and-demand CSV (public, no registration).

The Australian Energy Market Operator (AEMO) publishes the 5-minute
NEM (National Electricity Market) settlement prices and dispatch
demand for all 5 regions (NSW1, QLD1, SA1, TAS1, VIC1) at:

  https://www.aemo.com.au/aemo/data/nem/priceanddemand/PRICE_AND_DEMAND_YYYYMM_REGION.csv

Each file is a calendar month of 5-minute records:

  REGION, SETTLEMENTDATE, TOTALDEMAND, RRP, PERIODTYPE
  NSW1,   2024/01/01 00:05:00, 6574.92, 57.98, TRADE
  ...

This is **direct match** for try17/M11 trigger-axis modelling: TOTALDEMAND
spikes correspond to the kind of grid-stress events that activate VPP
ancillary services contracts.  No API key, no registration; AEMO
publishes the data in the public domain for transparency.

Reference:
  * https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem
  * License: AEMO public-domain data

Usage:

    python -m fetch_aemo_nem --start 2024-01 --end 2024-03 \\
        --regions NSW1,QLD1,VIC1 --out ./data/aemo_nem/

Output: one csv per (region, year, month).
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

AEMO_URL = (
    "https://www.aemo.com.au/aemo/data/nem/priceanddemand/"
    "PRICE_AND_DEMAND_{yyyymm}_{region}.csv"
)
DEFAULT_REGIONS = ("NSW1", "QLD1", "SA1", "TAS1", "VIC1")
RATE_LIMIT_S = 0.5
TIMEOUT_S = 60


def _yyyymm_range(start: str, end: str) -> list[tuple[int, int]]:
    """[YYYY-MM, YYYY-MM] inclusive → list of (year, month)."""
    sy, sm = (int(x) for x in start.split("-"))
    ey, em = (int(x) for x in end.split("-"))
    out: list[tuple[int, int]] = []
    y, m = sy, sm
    while (y, m) <= (ey, em):
        out.append((y, m))
        m += 1
        if m > 12:
            y, m = y + 1, 1
    return out


def fetch_one(year: int, month: int, region: str, out_dir: Path,
              overwrite: bool = False) -> Path | None:
    yyyymm = f"{year:04d}{month:02d}"
    url = AEMO_URL.format(yyyymm=yyyymm, region=region)
    out_path = out_dir / f"aemo_nem_{region.lower()}_{yyyymm}.csv"
    if out_path.exists() and not overwrite:
        print(f"[fetch_aemo_nem] skip (exists): {out_path.name}")
        return out_path
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "gridflow-fetcher/0.1"})
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
        out_path.write_bytes(data)
        n_lines = data.decode("utf-8", errors="replace").count("\n")
        print(f"[fetch_aemo_nem] {out_path.name}: {n_lines} rows, {len(data)//1024} KB")
        return out_path
    except urllib.error.HTTPError as e:
        print(f"[fetch_aemo_nem] HTTPError for {region} {yyyymm}: {e.code}",
              file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[fetch_aemo_nem] URLError for {region} {yyyymm}: {e.reason}",
              file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--start", required=True, help="YYYY-MM start (inclusive)")
    p.add_argument("--end", required=True, help="YYYY-MM end (inclusive)")
    p.add_argument("--regions", default=",".join(DEFAULT_REGIONS))
    p.add_argument("--out", default="./data/aemo_nem")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    months = _yyyymm_range(args.start, args.end)
    regions = [r.strip().upper() for r in args.regions.split(",") if r.strip()]
    print(f"[fetch_aemo_nem] {len(months)} months × {len(regions)} regions "
          f"= {len(months)*len(regions)} files → {out_dir}")
    n_ok = n_fail = 0
    for y, m in months:
        for r in regions:
            res = fetch_one(y, m, r, out_dir, overwrite=args.overwrite)
            if res:
                n_ok += 1
            else:
                n_fail += 1
            time.sleep(RATE_LIMIT_S)
    print(f"[fetch_aemo_nem] done: {n_ok} ok / {n_fail} fail")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
