"""Fetch EIA-930 hourly grid operations CSV bundles (US BAs, public).

The U.S. Energy Information Administration publishes the EIA-930
hourly electric grid monitor data, covering all 70+ US Balancing
Authorities (BAs) including ERCOT, CAISO, PJM, MISO, NYISO, etc.
Each row has demand (MWh), net generation (MWh), interchange (MWh),
and (where reported) **forced/scheduled outage MWh** which directly
maps to DER reliability events.

Bundles are released as 6-month CSVs from:

  https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/EIA930_BALANCE_YYYY_{Jan_Jun|Jul_Dec}.csv

Each bundle is ≈ 40-50 MB compressed.  Public-domain US federal data
(no registration, no rate-limit quoted).

Reference:
  * https://www.eia.gov/electricity/gridmonitor/about
  * https://www.eia.gov/opendata/ (full programmatic API also available
    with free EIA API key, but six-month bundles are sufficient for
    most research)

Usage:

    python -m fetch_eia_930 --bundles 2024_Jan_Jun,2024_Jul_Dec \\
        --out ./data/eia_930/

Output: one csv per bundle, kept in original schema.
"""

from __future__ import annotations

import argparse
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

EIA930_URL = (
    "https://www.eia.gov/electricity/gridmonitor/sixMonthFiles/"
    "EIA930_BALANCE_{bundle}.csv"
)
RATE_LIMIT_S = 1.0
TIMEOUT_S = 600


def fetch_one(bundle: str, out_dir: Path, overwrite: bool = False) -> Path | None:
    url = EIA930_URL.format(bundle=bundle)
    out_path = out_dir / f"eia930_balance_{bundle}.csv"
    if out_path.exists() and not overwrite:
        print(f"[fetch_eia_930] skip (exists): {out_path.name}")
        return out_path
    try:
        req = urllib.request.Request(
            url, headers={"User-Agent": "gridflow-fetcher/0.1"},
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT_S) as resp:
            data = resp.read()
        out_path.write_bytes(data)
        print(f"[fetch_eia_930] {out_path.name}: {len(data)//1024} KB")
        return out_path
    except urllib.error.HTTPError as e:
        print(f"[fetch_eia_930] HTTPError for {bundle}: {e.code}", file=sys.stderr)
        return None
    except urllib.error.URLError as e:
        print(f"[fetch_eia_930] URLError for {bundle}: {e.reason}", file=sys.stderr)
        return None


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--bundles", required=True,
                   help="Comma-separated YYYY_(Jan_Jun|Jul_Dec) tokens")
    p.add_argument("--out", default="./data/eia_930")
    p.add_argument("--overwrite", action="store_true")
    args = p.parse_args(argv)
    out_dir = Path(args.out).resolve()
    out_dir.mkdir(parents=True, exist_ok=True)
    bundles = [b.strip() for b in args.bundles.split(",") if b.strip()]
    print(f"[fetch_eia_930] {len(bundles)} bundle(s) → {out_dir}")
    n_ok = n_fail = 0
    for b in bundles:
        res = fetch_one(b, out_dir, overwrite=args.overwrite)
        n_ok += 1 if res else 0
        n_fail += 0 if res else 1
        time.sleep(RATE_LIMIT_S)
    print(f"[fetch_eia_930] done: {n_ok} ok / {n_fail} fail")
    return 0 if n_fail == 0 else 1


if __name__ == "__main__":
    sys.exit(main())
