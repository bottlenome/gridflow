# try11 demo data fixtures

This directory contains **demo CSV fixtures** for end-to-end pipeline
validation using the gridflow `Dataset` framework
(`docs/dataset_contribution.md`).

## ⚠️ NOT actual real data

The CSVs here are **synthesised** to **match the published schema** of
real public datasets (CAISO OASIS, AEMO Tesla VPP report, etc.) so the
loader pipeline can be tested. They are **NOT** actual recorded data.

For real data:
1. Follow the loader docstring in
   `src/gridflow/adapter/dataset/<source>_loader.py`
2. Download from the public URL listed in the metadata
3. Place at `$GRIDFLOW_DATASET_ROOT/<dataset_id>/data.csv`

## Fixtures

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
- **NOT real data** — modeled after published VPP demonstration report
  summary statistics
