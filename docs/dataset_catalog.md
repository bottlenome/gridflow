# gridflow データセットカタログ

**バージョン**: 1.0 (2026-04-29 初版)
**追加方法**: `docs/dataset_contribution.md` 参照

---

## High-priority registered datasets

(なし — 初版時点。貢献者は `docs/dataset_contribution.md` §6.1 のリクエスト一覧から取り組み開始)

---

## Synthetic datasets (try11 baseline)

### gridflow/synthetic_vpp_churn/v1

- **Source**: gridflow research collective (synthetic)
- **License**: CC0-1.0
- **DOI / URL**: (このリポジトリ `test/mvp_try11/tools/trace_synthesizer.py`)
- **Channels**: der_active_status (bool), aggregate_kw (kW), trigger_event_log (event)
- **Period**: 30 day synthetic (variable)
- **Resolution**: 5 min
- **Description**: Hand-crafted churn trace with C1-C8 variants (single trigger / extreme burst / simultaneous / OOD / frequency shift / label noise / correlation reversal / scarce orthogonal)
- **Contributor**: gridflow team
- **Added**: 2026-04-29
- **gridflow uses**: try11 main experiments (1080 cells)
- **Note**: 合成データのみ。本実験補助 + smoke test 用。実データ不在の補完で、PWRS reject 寄り評価の主因 (mvp_review_policy.md §4.2 E-2)

---

## Notes on requested datasets

`docs/dataset_contribution.md` §6.1 で挙げた高優先度データセットは現時点未登録。

特に以下は PWRS 投稿前に **必須**:

1. **Pecan Street residential EV** — `pecanstreet/residential_ev/` (registration required, contributor が手元で取得)
2. **CAISO 5-min load** — `caiso/load_5min/` (public download)
3. **AEMO Tesla VPP report** — `aemo/tesla_vpp_sa/` (public download)

データセットを取得した contributor は **PR で本カタログに追加** すること。

---

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-29 | 初版作成。synthetic データセットのみ登録 |
