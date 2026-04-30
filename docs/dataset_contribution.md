# gridflow データセット貢献ガイド

**バージョン**: 1.0 (2026-04-29 初版)
**対象**: gridflow に実世界データセット (DER 可用性、配電負荷、市場価格、EV 充電需要等) を追加したい貢献者

## 0. 趣旨

gridflow の MVP 検証 (`docs/mvp_review_policy.md`) では、IEEE Trans / PWRS 等の top venue 投稿水準を目標としており、合成データのみの実証は不十分とされる (`mvp_review_policy.md` §4.2 E)。本ガイドは:

- 誰でも気軽に実世界データセットを gridflow に登録できるようにする
- 同時に、再現性 / ライセンス / プロベナンスの厳密性を担保する

を両立させる目的で策定された。

---

## 1. データセットの全体像

### 1.1 ドメイン型 (実装済み)

`src/gridflow/domain/dataset/` 配下:

- **`DatasetMetadata`** (frozen): 来歴 (DOI / URL / ライセンス / sha256 / 期間 / units / contributors)
- **`DatasetSpec`** (frozen): 取得スライス指定 (時間範囲 / channel フィルタ)
- **`DatasetTimeSeries`** (frozen): データ payload (timestamps + multi-channel values)
- **`DatasetLoader`** (Protocol): pure func `spec → timeseries`
- **`DatasetRegistry`** (Protocol): カタログ照会 API
- **`DatasetLicense`** (Enum): SPDX 準拠ライセンス識別子

### 1.2 アダプター層 (`src/gridflow/adapter/dataset/`)

各データソースごとに 1 ファイル:

```
src/gridflow/adapter/dataset/
├── __init__.py
├── pecan_street_loader.py        # Pecan Street (residential EV / PV)
├── nrel_resstock_loader.py       # NREL ResStock simulated data
├── caiso_loader.py               # CAISO 5-min load
├── jepx_loader.py                # JEPX wholesale price
├── aemo_tesla_vpp_loader.py      # AEMO South Australia Tesla VPP
└── synthetic_loader.py           # 既存合成 trace の loader 化
```

### 1.3 レジストリ (`src/gridflow/infra/dataset/`)

- **`InMemoryDatasetRegistry`**: テスト用、metadata のみ
- **`FilesystemDatasetRegistry`**: 本番用、`~/.gridflow/datasets/` 以下に payload を sha256 で content-address する

---

## 2. 新規データセット追加の手順 (チェックリスト形式)

### Step 1: 適格性判定

データソースが以下を満たすか確認:

- [ ] **ライセンス**: 学術利用が許諾されている (CC-BY, CC0, ODC-BY 等が望ましい)
- [ ] **DOI / URL**: 永続的な参照可能 (preprint / dataset URL でも可)
- [ ] **時間粒度**: 5 分〜1 時間が望ましい (秒オーダーは特例)
- [ ] **期間**: 14 日以上の連続データ (訓練/テスト分割可能)
- [ ] **scope**: gridflow のいずれかのユースケースに関連 (DER 可用性 / 負荷 / 市場価格 / 電圧 / 電流)

### Step 2: メタデータの作成

`gridflow/adapter/dataset/<source>_loader.py` に loader を作成し、以下のメタデータを記述:

```python
from datetime import datetime, UTC
from gridflow.domain.dataset import DatasetMetadata, DatasetLicense

PECAN_STREET_RESIDENTIAL_EV = DatasetMetadata(
    dataset_id="pecanstreet/residential_ev/2024-01",
    title="Pecan Street Residential EV Charging (2024-01)",
    description=(
        "5-minute EV charging power for ~100 households in Austin, TX, "
        "covering January 2024. Includes per-household availability flags "
        "(EV connected to charger / not)."
    ),
    source="Pecan Street Inc.",
    license=DatasetLicense.PROPRIETARY_RESEARCH,  # academic registration
    retrieval_url="https://www.pecanstreet.org/dataport/",
    doi="",  # no DOI assigned
    retrieval_method="registration_required",
    sha256="<fill after first download>",
    time_resolution_seconds=300,
    period_start_iso="2024-01-01T00:00:00Z",
    period_end_iso="2024-02-01T00:00:00Z",
    units=(
        ("ev_power_kw", "kW"),
        ("ev_connected", "bool"),
    ),
    contributors=("contributor@example.com",),
    added_at_iso="2026-04-29T00:00:00Z",
)
```

### Step 3: Loader 実装

```python
from gridflow.domain.dataset import DatasetLoader, DatasetSpec, DatasetTimeSeries

class PecanStreetLoader:
    name = "pecanstreet"

    def supports(self, dataset_id: str) -> bool:
        return dataset_id.startswith("pecanstreet/")

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries:
        if not self.supports(spec.dataset_id):
            raise ValueError(f"unsupported: {spec.dataset_id}")
        # 1. Locate cached payload (or fetch via registered cache)
        # 2. Slice by spec.time_range and spec.channel_filter
        # 3. Verify sha256 against metadata
        # 4. Return DatasetTimeSeries
        ...
```

### Step 4: テスト追加

`tests/dataset/test_<source>_loader.py`:

- [ ] `test_supports_correct_id`
- [ ] `test_supports_rejects_other_id`
- [ ] `test_metadata_immutable`
- [ ] `test_load_returns_correct_channels`
- [ ] `test_sha256_validation` (= 改竄検知)
- [ ] `test_load_deterministic` (= 同 spec で同 result)

### Step 5: ドキュメント追加

`docs/dataset_catalog.md` にエントリを追加 (本ガイド §3 にテンプレ)。

### Step 6: PR 提出

- [ ] CLAUDE.md §0.1 (frozen, no compromise) 遵守
- [ ] DatasetMetadata.contributors に貢献者メールを記載
- [ ] sha256 を記録 (= 後続再取得時の検証用)
- [ ] PR 本文に: license の根拠 / 実データ取得手順 / サンプル数

---

## 3. データセットカタログ (`docs/dataset_catalog.md` テンプレ)

各データセットに 1 セクション、以下のテンプレで:

```markdown
### pecanstreet/residential_ev/2024-01

- **Source**: Pecan Street Inc.
- **License**: Proprietary research-use (academic registration required)
- **DOI / URL**: https://www.pecanstreet.org/dataport/
- **Channels**: ev_power_kw (kW), ev_connected (bool)
- **Period**: 2024-01-01 to 2024-02-01
- **Resolution**: 5 min
- **N samples**: 8,928 timesteps × 100 households
- **Contributor**: contributor@example.com
- **Added**: 2026-04-29
- **gridflow uses**: try11 (VPP DER availability), try13 (residential EV scheduling)
```

---

## 4. ライセンス分類とアクセスポリシー

| License | 配布性 | gridflow への登録 | 自動 fetcher |
|---|---|---|---|
| CC0-1.0, Public Domain | 自由 | metadata + payload | ✅ 可 |
| CC-BY, CC-BY-SA, ODC-BY | 表記要 | metadata + payload | ✅ 可 |
| Apache-2.0, MIT | 表記要 | metadata + payload | ✅ 可 |
| Proprietary-Research | 個別承諾 | metadata のみ (payload は user 取得) | ❌ 不可 |
| その他 | 要 review | metadata のみ | ❌ 不可 |

**自動 fetcher 実装可否**: 配布性が "自由" or "表記要" のみ。Proprietary-Research は **必ず metadata のみ** 登録し、loader は user の手元にある payload を読み込む形 (ローカルパス指定) で実装する。

---

## 5. 再現性 / プロベナンス

### 5.1 SHA-256 必須

すべての payload は **sha256 が一致しなければロードを拒否する** こと:

```python
def _verify_sha256(payload: bytes, expected: str) -> None:
    import hashlib
    actual = hashlib.sha256(payload).hexdigest()
    if actual != expected:
        raise ValueError(f"sha256 mismatch: expected {expected}, got {actual}")
```

これにより、データソース側で content が変更された場合に検知できる。

### 5.2 DOI 推奨

DOI が振られているデータセットを優先する。preprint repository (arXiv, Zenodo) にデータセットを登録してから gridflow に登録するのが理想。

### 5.3 期間 / 単位の明示

`DatasetMetadata.units` は **必ず** 各 channel に単位を含めること。`(("active_power", "kW"),)` のように。**裸の "power" / "voltage" は不可**。

---

## 6. リクエスト中のデータセット (gridflow 観点)

以下は gridflow が必要としているデータセットの一覧。貢献者は優先順に取り組むことを推奨:

### 6.1 高優先度 (PWRS 投稿に必須)

| 用途 | 候補ソース | 使用先 try |
|---|---|---|
| 住宅 EV 充電可用性 (5 分粒度、≥30 日) | Pecan Street, OpenEV Dataset | try11 |
| 配電フィーダー実負荷 trace | Pecan Street feeder, NREL ResStock + ComStock | try11, future try (Volt-VAR) |
| Tesla VPP 提供記録 (公開分) | AEMO South Australia VPP report 由来 | try11 |
| 卸電力 5 分価格 (リアルタイム) | CAISO OASIS, JEPX, ENTSO-E | try11 (market trigger) |

### 6.2 中優先度 (拡張実証に有用)

| 用途 | 候補ソース | 使用先 |
|---|---|---|
| 住宅蓄電池運用 trace | NREL ResStock-Battery | future try |
| 商用フリート EV 運行データ | NREL EV Fleet Reports | future try |
| 気象データ (温度 / 日射) | NOAA, JMA | trigger generation |
| 系統障害 (台風等) 記録 | utility outage reports | future try (復旧順序) |

### 6.3 低優先度 (将来研究)

| 用途 | 候補ソース | 使用先 |
|---|---|---|
| 高速 PMU 計測 | Bonneville Power Admin | 安定度系研究 |
| 配電 AI 公開ベンチマーク | NeurIPS PowerGraph | future ML 統合 |

---

## 7. ライセンス上、payload を gridflow に同梱できないデータの扱い

### 7.1 メタデータのみ登録

`DatasetMetadata.retrieval_method = "registration_required"` または `"private"` の場合:

1. **gridflow リポジトリ には metadata のみコミット**
2. **payload は user が手元で取得** (例: `~/.gridflow/datasets/pecanstreet/...`)
3. Loader が payload のローカルパスを `DatasetSpec.params` または環境変数 `GRIDFLOW_DATASET_<dataset_id>_PATH` で受け取る

### 7.2 サンプル / fixture の扱い

**サンプル (= ライセンス上 OK な小規模 subset) を `tests/fixtures/dataset/` に置く**:

- 1 channel × 24 時間 × 1 月 = ~300 行程度に圧縮
- 元データの **prov / sha256 / source URL を fixture と一緒にコミット**
- これは "reproducible smoke test" 用、本実験には使用不可

---

## 8. Q&A

**Q1**: 自分の研究グループで取得した未公開データを登録できるか?
**A1**: できる。ただし `DatasetLicense.PROPRIETARY_RESEARCH` を選び、`retrieval_method="private"` とし、payload は **登録しない** (= metadata のみ)。Loader は env var or local path で payload を見つける。

**Q2**: データセットに更新があった場合は?
**A2**: 新しい `dataset_id` (= バージョン部分を更新) で別エントリ追加。古いエントリは消さない。

**Q3**: Loader が複数のデータソース URL のフォールバックを持つべきか?
**A3**: 単一の canonical URL のみ。複数 URL を持たせるのはミラーリング目的のみで、すべて同じ sha256 が前提。

**Q4**: データサイズが大きい (> 1 GB) 場合は?
**A4**: gridflow リポジトリ には**含めない**。`DatasetMetadata.retrieval_url` で参照、`FilesystemDatasetRegistry` のキャッシュに置く。

---

## 9. ガバナンス

- 本ガイドの更新は PR + メンテナ承認制
- 新規データセット追加は **PR レビュー必須** (license, sha256, smoke test の確認)
- 違反コミット (license 表記なし、sha256 検証なし) は revert される

---

## 10. 関連ドキュメント

- `docs/mvp_review_policy.md` §4.2 E (top venue 水準の実データ要件)
- `src/gridflow/domain/dataset/` (実装済みドメイン型)
- `tests/dataset/` (loader テスト)
- `docs/dataset_catalog.md` (登録済みデータセット一覧)

## 11. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-29 | 初版作成 (try11 PWRS reviewer C2 指摘対応の一環) |
