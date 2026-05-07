# gridflow データセットカタログ

**バージョン**: 2.0 (2026-05-07 改訂)
**追加方法**: `docs/dataset_contribution.md` 参照
**手動登録要データ**: `docs/dataset_registration_guide.md` 参照

---

## 0. 一覧表 (Quick Reference)

| ID | Source | License | 取得方法 | 推定 size | 主用途 |
|---|---|---|---|---|---|
| **acn/caltech_sessions** | Caltech ACN-Data | Public (DEMO_TOKEN) | ✅ 自動 `fetch_acn.py` | 50KB / month | EV charging session, per-DER plug/unplug timestamp |
| **caiso/system_load_5min** | CAISO OASIS | Public Domain (US Federal) | ✅ 自動 `fetch_caiso.py` | 1MB / month | 5-min ISO-wide load, frequency event 起点 |
| **aemo/nem_5min** | AEMO NEM | Public Domain (AU) | ✅ 自動 `fetch_aemo_nem.py` | 400KB / month / region | 5-min price + demand, 5 regions (NSW1/QLD1/SA1/TAS1/VIC1) |
| **eia/eia930_balance** | US EIA-930 | Public Domain (US Federal) | ✅ 自動 `fetch_eia_930.py` | 40MB / 6-month bundle | 70+ US BAs, hourly demand/generation/interchange |
| **opsd/time_series** | OPSD | CC-BY-4.0 | ✅ 自動 `fetch_opsd_timeseries.py` | 124MB / full snapshot | 37 EU 国 hourly load + solar/wind generation, 2010-2020 |
| **nrel/nsrdb** | NREL NSRDB | Public, **要 API key** | 📝 [registration_guide §1](dataset_registration_guide.md#1-nrel-nsrdb) | varies | 太陽放射量 (GHI/DNI/DHI) 30-min |
| **entsoe/transparency** | ENTSO-E | Free, **要 API key** | 📝 [registration_guide §2](dataset_registration_guide.md#2-entso-e-transparency) | varies | EU bid-area generation/load/outage 詳細 |
| **pecanstreet/dataport** | Pecan Street | **要 academic 登録** | 📝 [registration_guide §3](dataset_registration_guide.md#3-pecan-street-dataport) | 数 GB | 住宅 EV / PV / battery 1-min disaggregated |
| **gridflow/synthetic_vpp_churn** | gridflow | CC0-1.0 | (内蔵) | < 1MB | smoke test / baseline |

「✅ 自動」は registration 不要、`python -m tools.fetch_*` 1 行で取得できます。
「📝」は `docs/dataset_registration_guide.md` で登録手順をスクリーンショット付きで案内。

---

## 1. 自動取得 (registration 不要)

### 1.1 acn/caltech_sessions/v1 — Caltech ACN-Data

- **Source**: California Institute of Technology, Adaptive Charging Network
- **URL**: https://ev.caltech.edu/dataset
- **License**: Public (DEMO_TOKEN — 登録不要)
- **Citation**: Lee, Z., Li, T., Low, S. H. (2019). *ACN-Data: Analysis and Application of an Open EV Charging Dataset*. ACM e-Energy 2019.
- **Schema**: `sessionID, stationID, userID, connectionTime, disconnectTime, doneChargingTime, kWhDelivered, siteID, clusterID, spaceID, timezone`
- **Sites**: `caltech` (31k+ sessions, default), `jpl`, `office001`
- **Time period**: 2018-04 から継続更新
- **Resolution**: per-session (event-level)
- **取得**: 
  ```bash
  python -m test.mvp_try11.tools.fetch_acn \
      --start 2019-01-01 --end 2019-02-01 \
      --site caltech --out ./data/acn/caltech_sessions/v1/data.csv
  ```
- **既存 fixture**: `test/mvp_try11/data/acn_caltech_sessions_2019_01.csv` (986 sessions, 50KB), `test/mvp_try13/data/acn_caltech_2019_{02,03}.csv` + `acn_jpl_2019_01.csv`
- **gridflow 用途**: try11/13/14/15/16 で per-DER churn 解析

### 1.2 caiso/system_load_5min/v1 — CAISO OASIS

- **Source**: California ISO Open Access Same-time Information System (OASIS)
- **URL**: http://oasis.caiso.com/
- **License**: Public Domain (US federal energy information)
- **Citation**: CAISO. *OASIS API Specification*. Public technical doc.
- **Schema**: `ts_iso, system_load_mw`
- **Time period**: 2009 から継続更新
- **Resolution**: 5 分 (RTM real-time market) / 1 時間 (HASP) / 1 時間 (DAM day-ahead)
- **取得**:
  ```bash
  python -m test.mvp_try11.tools.fetch_caiso \
      --start 2024-01-01 --end 2024-01-08 \
      --out ./data/caiso/system_load_5min/v1/data.csv
  ```
- **既存 fixture**: `test/mvp_try11/data/caiso_system_load_real_2024w1.csv` (1 週間)
- **rate limit**: ≈ 60 query/h; fetcher は 1.5s sleep + 30 day max chunk
- **gridflow 用途**: 周波数 event 起点 / dispatch trigger / system stress 識別

### 1.3 aemo/nem_5min/v1 — AEMO National Electricity Market ⭐ NEW

- **Source**: Australian Energy Market Operator (AEMO)
- **URL**: https://aemo.com.au/energy-systems/electricity/national-electricity-market-nem/data-nem
- **License**: Public Domain (AEMO publishes for transparency)
- **Citation**: AEMO. *NEM Price and Demand Reports* (公開ダウンロード)
- **Schema**: `REGION, SETTLEMENTDATE, TOTALDEMAND, RRP, PERIODTYPE`
- **Regions**: `NSW1`, `QLD1`, `SA1`, `TAS1`, `VIC1`
- **Time period**: 1998-12 から継続更新 (28 年史料)
- **Resolution**: 5 分
- **取得**:
  ```bash
  python -m test.mvp_try11.tools.fetch_aemo_nem \
      --start 2024-01 --end 2024-03 \
      --regions NSW1,VIC1 --out ./data/aemo/nem_5min/v1/
  ```
- **既存 fixture**: `test/mvp_try11/data/aemo_nem/aemo_nem_nsw1_202401.csv` (8928 rows / 月 / region)
- **rate limit**: なし (cloudflare CDN); fetcher は 0.5s sleep
- **gridflow 用途**: VPP 補助サービス契約のための market trigger event 構築、SA は世界最大 Tesla VPP の地域

### 1.4 eia/eia930_balance/v1 — US EIA-930 Hourly Grid Operations ⭐ NEW

- **Source**: U.S. Energy Information Administration (EIA)
- **URL**: https://www.eia.gov/electricity/gridmonitor/about
- **License**: Public Domain (US Federal)
- **Citation**: EIA Form 930. *Hourly Electric Grid Monitor*. Public data.
- **Schema**: `Balancing Authority, Data Date, Hour Number, Local Time, UTC Time, Demand Forecast (MW), Demand (MW), Net Generation (MW), Total Interchange (MW), ...` (50+ columns including by-source generation breakdown)
- **Coverage**: 70+ US Balancing Authorities (PJM, ERCOT, CAISO, MISO, NYISO, ISONE, AECI, ...)
- **Time period**: 2015-07 から継続更新
- **Resolution**: 1 時間
- **取得**:
  ```bash
  python -m test.mvp_try11.tools.fetch_eia_930 \
      --bundles 2024_Jan_Jun --out ./data/eia/eia930_balance/v1/
  ```
- **Bundle ID 形式**: `YYYY_(Jan_Jun|Jul_Dec)` (= 半年単位 ≈ 40MB)
- **Note**: bundle は git にコミットしない (`.gitignore` 済); 各 contributor が再 fetch
- **gridflow 用途**: BA-level 異常 event log (frequency excursion, demand spike, generation outage), 70 BA × 半年 = 305k 時間レコード

### 1.5 opsd/time_series/v1 — Open Power System Data ⭐ NEW

- **Source**: Open Power System Data project (Neon Neue Energieökonomik, German)
- **URL**: https://open-power-system-data.org/
- **License**: CC-BY-4.0
- **Citation**: Open Power System Data. *Time series* (latest snapshot 2020-10-06). https://doi.org/10.25832/time_series/2020-10-06
- **Schema**: 1 行 per timestamp、列は `{country}_{channel}` (e.g. `DE_load_actual_entsoe_transparency`, `FR_solar_generation_actual`, `GB_UKM_wind_offshore_generation_actual`, ...). 全 ~370 列。
- **Coverage**: 37 EU 国
- **Channels per country**: load_actual, load_forecast, price_day_ahead, solar_generation_actual, wind_onshore/offshore_generation_actual, capacities (where reported)
- **Time period**: 2010-01-01 から 2020-09-30 (10年9ヶ月、50,401 hourly rows)
- **Resolution**: 60 min (デフォルト) / 30 min (UK 中心) / 15 min (DE 中心)
- **取得**:
  ```bash
  python -m test.mvp_try11.tools.fetch_opsd_timeseries \
      --variant 60min --out ./data/opsd/time_series/v1/
  ```
- **Note**: 60min variant 1 ファイルで 124 MB; git にコミットしない (`.gitignore` 済)
- **gridflow 用途**: EU 全域 generation/load の 10 年 heavy-tail 統計、PV/wind drop event の数学的モデル校正、heavy-tail Pareto α の country-by-country fit

### 1.6 gridflow/synthetic_vpp_churn/v1

- **Source**: gridflow research collective
- **License**: CC0-1.0
- **URL**: (内蔵 — `test/mvp_try11/tools/trace_synthesizer.py`)
- **Schema**: `der_active_status (bool), aggregate_kw (kW), trigger_event_log (event)`
- **Period**: 30 day, variable
- **Resolution**: 5 min
- **Note**: 合成データ。実 data 不在時の baseline / smoke test。**実データ実験を bypass しないこと** (PWRS reject 寄り)

---

## 2. 手動登録必要 (`dataset_registration_guide.md` で詳細手順)

### 2.1 nrel/nsrdb/v1 — NREL National Solar Radiation Database

- **登録**: 無料、メールアドレスのみ (NREL Developer Network API key)
- **手順**: [dataset_registration_guide.md §1](dataset_registration_guide.md#1-nrel-nsrdb)
- **取得後**: GHI / DNI / DHI 太陽放射量を任意の北米座標 × 過去 22 年 30 分粒度で取得
- **gridflow 用途**: PV inverter Volt-VAR 制御の雲影モデル校正、frequency-of-occurrence empirical

### 2.2 entsoe/transparency/v1 — ENTSO-E Transparency Platform

- **登録**: 無料、メールアドレス (3 営業日承認)
- **手順**: [dataset_registration_guide.md §2](dataset_registration_guide.md#2-entso-e-transparency)
- **取得後**: EU 35 bid area の generation / load / outage / interconnection を XML/CSV で
- **gridflow 用途**: 真の DER outage event log (= "unavailability of production units" report、A77/A80 document type)

### 2.3 pecanstreet/dataport/v1 — Pecan Street Dataport

- **登録**: academic affiliation 必要 (= 大学メールアドレス)、承認に 1-2 週間
- **手順**: [dataset_registration_guide.md §3](dataset_registration_guide.md#3-pecan-street-dataport)
- **取得後**: 米テキサス 1000+ 住宅の EV charging / PV / battery / HVAC 1-分粒度
- **gridflow 用途**: 住宅 DER の真の churn pattern、appliance-level disaggregation

---

## 3. データ取得 quick start

### 自動取得 (1 行)

```bash
# ACN-Data EV charging (1 month)
python -m test.mvp_try11.tools.fetch_acn --start 2024-01-01 --end 2024-02-01

# CAISO 5-min load (1 week)
python -m test.mvp_try11.tools.fetch_caiso --start 2024-01-01 --end 2024-01-08

# AEMO NEM 5-min (3 months × 2 regions)
python -m test.mvp_try11.tools.fetch_aemo_nem --start 2024-01 --end 2024-03 --regions NSW1,VIC1

# EIA-930 (6 months, 70+ US BAs)
python -m test.mvp_try11.tools.fetch_eia_930 --bundles 2024_Jan_Jun

# OPSD time-series (full 10-year EU snapshot)
python -m test.mvp_try11.tools.fetch_opsd_timeseries --variant 60min
```

### 手動登録 → 取得

`docs/dataset_registration_guide.md` を順に実行。所要 5 分 (NSRDB) 〜 1-2 週間 (Pecan Street academic 承認待ち)。

---

## 4. 追加データセットの登録 (contributor 向け)

新データセットを fetcher 化して PR で本カタログに追加する手順は `docs/dataset_contribution.md` 参照。

新エントリ追加 checklist:
- [ ] Source / URL / License 明示
- [ ] 学術 citation (BibTeX 形式) 追加
- [ ] schema (列名 + 型 + unit) 列挙
- [ ] coverage (geographic / temporal / resolution)
- [ ] 取得 fetcher OR 手動登録 guide のリンク
- [ ] 既存 fixture があれば SHA256 + size 明示
- [ ] gridflow 用途を 1-2 文で記述

---

## 5. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-29 | 初版作成。synthetic データセットのみ登録 |
| 2026-05-07 | v2.0 全面改訂。auto-fetch 5 sources (ACN / CAISO / AEMO / EIA-930 / OPSD) 整備、registration-required 3 sources (NSRDB / ENTSO-E / Pecan Street) を `dataset_registration_guide.md` で詳細案内 |
