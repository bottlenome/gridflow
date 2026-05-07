# try11 / shared data fixtures

This directory holds **fixtures for end-to-end pipeline validation** using the gridflow
`Dataset` framework (see `docs/dataset_catalog.md`, `docs/dataset_contribution.md`).

There are two classes of files here:

- **Real public-data fixtures** (small; committed): downloaded via `tools/fetch_*.py`.
  Currently `acn_caltech_sessions_2019_01.csv`, `caiso_system_load_real_2024w1.csv`,
  `aemo_nem/aemo_nem_*_*.csv`.
- **Synthetic demos** (clearly labelled `*_demo.csv`): hand-shaped to match published
  schema for smoke testing only. **These are NOT real data**; do NOT use them as the
  basis for any published claim.

## Fetching real data

See `docs/dataset_catalog.md` for the full catalogue. Quick start:

```bash
# Caltech ACN-Data (per-session EV charging)
python -m test.mvp_try11.tools.fetch_acn --start 2024-01-01 --end 2024-02-01 \
    --out ./data/acn/caltech_sessions/v1/data.csv

# CAISO 5-min system load
python -m test.mvp_try11.tools.fetch_caiso --start 2024-01-01 --end 2024-01-08 \
    --out ./data/caiso/system_load_5min/v1/data.csv

# AEMO NEM 5-min price + demand (5 regions)
python -m test.mvp_try11.tools.fetch_aemo_nem --start 2024-01 --end 2024-03 \
    --regions NSW1,VIC1,QLD1,SA1,TAS1 --out ./data/aemo/nem_5min/v1/

# US EIA-930 hourly grid operations (70+ BAs, 6-month bundle ≈ 40 MB)
python -m test.mvp_try11.tools.fetch_eia_930 --bundles 2024_Jan_Jun \
    --out ./data/eia/eia930_balance/v1/

# Open Power System Data 60-min EU snapshot (≈ 124 MB)
python -m test.mvp_try11.tools.fetch_opsd_timeseries --variant 60min \
    --out ./data/opsd/time_series/v1/
```

Large bundles (EIA-930 / OPSD) are listed in `.gitignore`; rerun the fetcher to
reproduce locally.

For datasets requiring registration (NREL NSRDB, ENTSO-E, Pecan Street),
follow `docs/dataset_registration_guide.md`.

## Synthetic demo fixtures (smoke test only)

### `caiso_system_load_demo.csv`

- **Schema match**: CAISO OASIS PRC_RTPD_LMP / system load (5-min)
- **Generated**: 7 days × 5-min = 2016 rows of system_load_mw
- **Realistic patterns**: diurnal cycle (~28 GW peak, ~22 GW valley),
  weekend reduction, weather-correlated weekday spikes
- **NOT real data** — synthetic with statistical patterns published in
  CAISO 2024 annual report

### `aemo_tesla_vpp_demo.csv`

- **Schema match**: AEMO South Australia VPP report tabular extraction
- **Generated**: 30 days × 5-min = 8640 rows
- **Channels**: n_units_online (count), total_capacity_kw (kW),
  frequency_hz_observed (Hz)
- **NOT real data** — modelled after published VPP demonstration report
  summary statistics
