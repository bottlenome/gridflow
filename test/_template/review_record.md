# try NN — review_record

<!-- 独立査読者（著者とは別）が report.md と results/ のみから記入する。
     mvp_review_policy.md §4.1.1 / §4.1.2 参照。 -->

## 論文主張のリフレーズ（査読者の言葉で、成果物のみから）

<report を見ずに results/ から主張を再構成し、著者のリフレーズと食い違わないか確認>

## 標準経路の使用状況（issue #25）

各ステップで gridflow 標準 CLI を使ったか。自作した場合は理由と、なぜ framework
機能で代替できなかったかを必須で記入する（代替不能なら issue 化する）。

| ステップ | 標準経路 | 使用 | 逸脱理由（自作した場合） |
|---|---|---|---|
| baseline 派生 | `scenario clone` | ☐ | |
| パラメータ探索 | `sweep`（n_replicates≥2） | ☐ | |
| メトリクス再評価 / CI | `evaluate --bootstrap-n` | ☐ | |
| 統計判定 | `benchmark`（レプリケート群） | ☐ | |
| 違反起因分離 | `attribute-violations` | ☐ | |
| エンジン検証 | `validate-engines` | ☐ | |
| 論文表 | `export paper` | ☐ | |

## 機構的ガードの確認（§4.1.2）

- [ ] `benchmark` JSON に significant / p / 効果量 / CI がある
- [ ] `zero_variance` / `insufficient_replicates` 警告が出ていない
- [ ] `validate-engines` agree（exit 0）
- [ ] 電圧違反の主張は `dispatch_induced_rate` に基づく
- [ ] 合成属性は `stable_hash` 由来（builtin `hash` 不使用）
- [ ] `non_convergence_rate` ≈ 0

## 数値の信頼性（§4.2 B）

- 本文数値と results/*.json の照合結果:
- artifact（共有 seed / 決定論入力による見かけの一致）の識別:

## 意味的妥当性（§4.1.3 — 査読者の認知作業）

- データと主張の物理的対応（non-sequitur がないか）:
- paradigm fixation（Rule 6）の有無:

## 判定

- 結論: <合格 / Major / Minor / 不合格>
- CRITICAL / MAJOR 指摘:
