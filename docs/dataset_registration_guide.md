# gridflow データセット登録ガイド (手動登録必要なもの)

**バージョン**: 1.0 (2026-05-07 初版)
**対象読者**: gridflow ユーザ — 手動登録が必要な公開 / 半公開データセットの取得手順
**前提**: `docs/dataset_catalog.md` を一読していること

---

## 0. このガイドの範囲

下表のデータセットは **無料** で取得できますが、配信元のサーバ運用上、API key またはアカウント登録を要求します。本ガイドはステップ順に手順を案内します。

| § | データセット | 登録難度 | 承認時間 | 必要情報 |
|---|---|---|---|---|
| 1 | NREL NSRDB (太陽放射量) | ★☆☆ | 即時 | メールアドレス |
| 2 | ENTSO-E Transparency (EU 系統) | ★★☆ | 1-3 営業日 | メールアドレス |
| 3 | Pecan Street Dataport (米住宅 DER) | ★★★ | 1-2 週間 | academic 所属確認 |

完了後、得られた API key / credentials は **`~/.gridflow/credentials.toml`** に保存することを推奨 (gridflow がこのパスを自動参照)。

---

## 1. NREL NSRDB

### 1.1 概要
National Solar Radiation Database。北米 + 中南米の任意座標における 太陽放射量 (GHI/DNI/DHI) と気象を 30 分粒度で 1998-2022 年遡って提供。

### 1.2 登録手順 (5 分で完了)

1. **API key 申請ページにアクセス**:
   https://developer.nrel.gov/signup/

2. **以下の項目を入力**:
   - First Name / Last Name
   - Email
   - Organization (個人ユーザは "Independent Researcher" で可)
   - How will you use the NREL APIs? (1-2 文で用途、例: "Volt-VAR control research at home distribution feeder")

3. **"Sign Up" クリック後、即時にメールが届く**:
   ```
   Subject: NREL Developer Network API Key
   ```
   メール本文に **40 文字程度の API key** が記載 (例: `abc1d23e4f5g6h7...XYZ`)

4. **Email 確認 OK**: 待機時間ゼロ、即時に key 発行

### 1.3 gridflow への credential 設定

```bash
# ~/.gridflow/credentials.toml に追加
mkdir -p ~/.gridflow
cat >> ~/.gridflow/credentials.toml <<EOF
[nrel]
api_key = "abc1d23e4f5g6h7...XYZ"
email   = "your_email@example.com"
EOF
chmod 600 ~/.gridflow/credentials.toml
```

### 1.4 取得 (準備中の fetcher)

```bash
# 単一地点 (Pasadena, 2019)
python -m test.mvp_try11.tools.fetch_nrel_nsrdb \
    --lat 34.139 --lon -118.125 --year 2019 \
    --interval 30 --attributes ghi,dni,dhi,air_temperature \
    --out ./data/nrel/nsrdb/v1/
```

**Note**: 上記 fetcher は本ガイド時点では **未実装**。実装は `test/mvp_try11/tools/fetch_nrel_nsrdb.py` で TODO。NREL API 仕様: https://developer.nrel.gov/docs/solar/nsrdb/psm3-2-2-download/

### 1.5 rate limit / 制約
- 1 day あたり 1000 calls (= 1 call で 1 地点 1 年取得可、緩い制約)
- 1 リクエスト max 5 年
- 商用利用は別途 NREL に許諾要

---

## 2. ENTSO-E Transparency Platform

### 2.1 概要
European Network of Transmission System Operators (ENTSO-E) が運営する欧州系統データの公的窓口。35 bid area の generation / load / **outage / unavailability** を XML 形式で提供。**真の DER outage event log** (A77 / A80 document type) を含むため、heavy-tail churn 研究に最適。

### 2.2 登録手順 (1-3 営業日)

1. **アカウント登録**: 
   https://transparency.entsoe.eu/usrm/user/createPublicUser

2. **以下の項目を入力**:
   - Email (organisation メール推奨、しかし gmail 等も承認実績あり)
   - First Name / Last Name
   - Organisation
   - Country
   - Phone (任意)
   - Password

3. **メール認証**: 登録メールに verification link → クリックで初期承認

4. **API access 申請** (= 重要、忘れがち):
   - ログイン後、右上の username → "My Account Settings"
   - "Web Api Security Token" タブ
   - 「Generate a new token」をクリック
   - 申請内容に研究目的を 1-2 文で記述
   - **3 営業日以内に承認メール**、トークン (36 文字 UUID 形式) が記載

5. **承認後**: 24/7 free access

### 2.3 gridflow への credential 設定

```bash
cat >> ~/.gridflow/credentials.toml <<EOF
[entsoe]
api_token = "12345678-1234-1234-1234-123456789012"
EOF
chmod 600 ~/.gridflow/credentials.toml
```

### 2.4 取得 (準備中の fetcher)

```bash
# Germany generation/load Jan 2024
python -m test.mvp_try11.tools.fetch_entsoe \
    --area 10Y1001A1001A83F --start 2024-01-01 --end 2024-02-01 \
    --document-types A65,A77 --out ./data/entsoe/transparency/v1/

# A65 = Total load
# A77 = Production unit unavailability (= DER outage event)
# A80 = Generation unit unavailability
```

**Note**: fetcher 未実装。仕様 https://transparency.entsoe.eu/content/static_content/Static%20content/web%20api/Guide.html

### 2.5 rate limit / 制約
- 400 calls / minute, 10000 calls / day
- リクエスト max 1 year span
- redistribution OK (CC-BY-4.0 同等)

### 2.6 ⚠ 重要 — DER outage event の文書 type

VPP heavy-tail churn 研究で**最も価値が高い** document type:

| Document type code | 意味 | 用途 |
|---|---|---|
| **A77** | Production unit unavailability | 個別生成 unit の予期せぬ停止 (= DER drop event) |
| **A80** | Generation unit unavailability | aggregate-level の停止 |
| A78 | Transmission unavailability | 送電線停止 (= 隣接 effect) |
| A65 | Total load | 系統需要 (trigger 起点) |

`A77` は **本来 PWRS / IEEE T-SG 級の paper で求められる "real DER failure data"** に直接該当。

---

## 3. Pecan Street Dataport

### 3.1 概要
米テキサス + コロラドの 1000+ 住宅における **1-分粒度の disaggregated 電力消費** (= 各家電 / EV / PV / 蓄電池ごとの計測) を提供。住宅 DER 研究の事実上の標準。

### 3.2 登録手順 (1-2 週間、academic 必要)

1. **University Research Access 申請**:
   https://www.pecanstreet.org/dataport/

2. **以下を準備**:
   - **大学メールアドレス** (= ".edu" 等)、企業メールでは申請却下
   - 所属研究室 / 指導教員氏名
   - 研究テーマ要約 (1-2 段落)
   - データ利用予定範囲 (households, time period, 用途)

3. **University Free License or Free Researcher License を選択**:
   - University = 大学全体に適用 (research lab 推奨)
   - Researcher = 個人 1 人

4. **PDF data use agreement にサイン → メール返送**

5. **承認待ち 1-2 週間** (Pecan Street administrator が手動審査)

6. **承認メールにアカウント情報**: dataport.pecanstreet.org のログイン credentials

### 3.3 取得方法
**Pecan Street は API 経由でなく Web UI ダウンロード or Postgres dump 経由**。

#### Web UI (簡易):
- ログイン → "Data" → "Data Egauge" or "Data Aggregate"
- フィルタ (households, channels, time range) → "Generate Download"
- CSV ダウンロード (大規模時は zip)

#### Postgres dump (本格):
```bash
psql -h dataport.pecanstreet.org -U <username> -d <db> \
     -c "COPY (SELECT * FROM electricity_egauge_minutes \
              WHERE dataid IN (1234,5678) AND localminute >= '2019-01-01') \
              TO STDOUT WITH CSV HEADER" \
     > pecan_street.csv
```

### 3.4 gridflow への credential 設定

```bash
cat >> ~/.gridflow/credentials.toml <<EOF
[pecanstreet]
db_host     = "dataport.pecanstreet.org"
db_user     = "your_username"
db_password = "your_password"
db_name     = "postgres"
EOF
chmod 600 ~/.gridflow/credentials.toml
```

### 3.5 ⚠ 重要 — データ用途と論文 acknowledgment

Pecan Street 利用論文には以下の acknowledgment 文を**必須掲載**:

> "This research used data from Pecan Street Inc. Dataport, available at <https://www.pecanstreet.org/dataport/>."

詳細は受信 PDF agreement 参照。

---

## 4. その他 (将来候補)

以下のデータセットも研究上有用ですが、現時点 gridflow では fetcher 未整備 / 登録手順が複雑です。需要があれば本ガイドに追加します:

- **NERC GADS** (Generating Availability Data System) — NERC 加盟事業者のみアクセス可。研究者は NERC 別途交渉
- **DOE OE-417** (Electric Disturbance Events) — 公開だが PDF 単発 incident report、CSV bulk download なし
- **AEMO Tesla VPP detailed** — 公開だが PDF 添付資料からのテーブル抽出必要 (loader stub あり、fetcher 未実装)
- **Open Smart-Meter Test Cases (UK Low Carbon London)** — ckan portal 経由、登録不要だが個別 dataset id 把握必要

---

## 5. credentials.toml テンプレート

すべて埋めた状態の見本:

```toml
# ~/.gridflow/credentials.toml
# chmod 600 で permission 制限すること

[nrel]
api_key = "your_40char_nrel_api_key"
email   = "your_email@example.com"

[entsoe]
api_token = "12345678-1234-1234-1234-123456789012"

[pecanstreet]
db_host     = "dataport.pecanstreet.org"
db_user     = "your_username"
db_password = "your_password"
db_name     = "postgres"

# (将来追加用)
# [aemo_data_portal]
# api_key = "..."
```

`gridflow` の loader 群はこの TOML を自動読込してデータ取得時に使用します。実装は `src/gridflow/adapter/dataset/_credentials.py` (将来追加予定)。

---

## 6. トラブルシューティング

### NSRDB 「Quota exceeded」
- 1 day 1000 calls 上限。翌 UTC 0 時にリセット。複数コールは bulk request (1 リクエスト 1 年) で合算

### ENTSO-E 「Acknowledgement」だけ返って data なし
- リクエスト periodの一部期間が空 (= 提出されていない) の可能性。日付範囲を狭めて再試行
- **A77** outage 報告は ISO ごとに完全性が異なる: DE/FR は密、SE/IT/EE は疎

### Pecan Street 承認 2 週間以上待ち
- 大学メールアドレス検証で administrator が手動確認するため。1 ヶ月超なら support@pecanstreet.org に問合せ

---

## 7. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-05-07 | 初版作成。NREL NSRDB / ENTSO-E / Pecan Street の登録手順を案内 |
