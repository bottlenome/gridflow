# MVP try4 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: Stochastic HCA は配電事業者のDER導入可否判断に使われるが、閾値（どの電圧基準を使うか）の影響は体系的に調査されていない。先行研究では各自が独自の閾値を採用し、結果の比較可能性が失われている
- **先行研究**: HCA 手法の比較研究は存在するが (MDPI Energies 2020, ScienceDirect 2025)、閾値選択が結果に与える感度を controlled study で示した文献は稀
- **方法（提案手法の価値）**: IEEE 13-node feeder 上で同一 PV 配置列 (n=1000, seed 固定) に対し 3 種の電圧閾値 (Range A/Custom/Range B) を適用し、閾値の変更のみで HCA がどう変わるかを定量化。交絡要因（ソルバー・フィーダー・配置列）を完全排除した controlled study
- **実験結果**: Mean HC が 0.000 MW (Range A, 100% reject) → 0.308 MW (Custom, 81.1% reject) → 0.979 MW (Range B, 3.5% reject) に変化。95% CI は Range B で [0.944, 1.014]。収束分析で n=1000 の十分性を確認
- **考察**: 閾値選択は HCA の first-order determinant。IEEE 13 の baseline voltage が Range A 境界にあるため効果が極端に現れた。他フィーダーでは感度が異なる可能性があるが、閾値の明示が必須であることは一般的に成立する

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-22 |
| 対象ファイル | `test/mvp_try4/report.md` |
| レビュー方式 | 全成果物 (JSON x6, PNG x1, スクリプト x7) との照合 |
| レビュー方針 | `docs/mvp_review_policy.md` (§4.2 A-E) |

---

## A. 方針適合性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow を論文 contribution に含めていないか | ✅ 合格 | Abstract (§4.2) に gridflow の語なし。§4.4 末尾で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ 合格 | C-2 (ScienceDirect 2025), C-10 (MDPI 2023) |

**A 判定: 合格**

## B. 数値の信頼性

### B-1. 全数値の照合

comparison.json vs report §2.1:

| metric | report | JSON 実値 | 一致 |
|---|---|---|---|
| Range A HC mean | 0.0000 | 0.0 | ✅ |
| Custom HC mean | 0.3084 | 0.30839694... (=0.3084) | ✅ |
| Range B HC mean | 0.9789 | 0.97891018... (=0.9789) | ✅ |
| Custom CI low | 0.2684 | 0.26841069... | ✅ |
| Custom CI high | 0.3484 | 0.34838318... | ✅ |
| Range B CI low | 0.9438 | 0.94380875... | ✅ |
| Range B CI high | 1.0140 | 1.01401162... | ✅ |
| Range A rejection | 100.0% | 1.0 | ✅ |
| Custom rejection | 81.1% | 0.811 | ✅ |
| Range B rejection | 3.5% | 0.035 | ✅ |
| Range B median | 0.9664 | 0.96639945... | ✅ |

### B-2. 統計方法

- 95% CI: normal approximation (mean ± 1.96 * SE) ✅ 明示
- relative delta 不要 (3 閾値は同一ベースラインで比較しないため)
- rejection rate: n_rejected / n_total で定義 ✅

### B-3. アーティファクト

- voltage_deviation が全 3 シナリオで同一: レポートで「同じ物理実験に異なる閾値を適用」と明示 ✅
- Range A の 100% rejection: artifact ではなく IEEE 13 の電圧特性の帰結 ✅ (§2.2, §4.5 で議論)

**B 判定: 合格**

## C. 科学的妥当性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 実験設計が主張を支持するか | ✅ | 「閾値が first-order determinant」という主張に対し、同一フィーダー・同一 seed で閾値のみ変更する controlled study は直接的な検証 |
| 交絡排除 | ✅ | ソルバー・フィーダー・seed 全て固定。try3 の「solver×topology 交絡」が解消 |
| DoD 判定 | ✅ | 全項目に適切な根拠。未検証項目なし |
| Limitations | ✅ | 5 項目: 単一フィーダー、単一時刻、定電流 PV、metric 定義、Range A の 100% reject |

**C 判定: 合格**

## D. 論文材料としての完成度

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図ラベル | ✅ | IEEE 13-node, pu 単位, 3 閾値のラベルが正確 |
| 用語 | ✅ | ANSI C84.1 Range A/B を正確に定義 |
| 再現手順 | ✅ | run_threshold_study.sh + analyze + plot で全行程再現可能 |

**D 判定: 合格**

## E. 投稿先水準 (IEEE PES GM)

### E-1. 手法的新規性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 先行研究との差分 | ✅ | 閾値感度の controlled study は稀。HCA review (MDPI 2020, ScienceDirect 2025) で voltage standard selection の影響は言及されるが体系的定量化なし |
| 差分が自明でないか | ✅ | 「100% rejection vs 3.5% rejection」という結果は定性的には予想されるが、定量的な差の大きさは自明ではない |
| 先行研究比較 | ⚠️ MODERATE | Abstract で先行研究を引用しているが、具体的な数値比較 (他の HCA 論文の閾値・結果と対照) がない |

### E-2. 実験規模

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| Monte Carlo n >= 1000 | ✅ | n=1000 per scenario |
| IEEE 標準フィーダー | ✅ | IEEE 13-node |
| 時間粒度 | ⚠️ MODERATE | ピーク 1 時刻のみ。Limitations で認知しているが改善なし |
| 制約の網羅性 | ⚠️ MODERATE | 電圧制約のみ。熱制約 (line loading) なし |

### E-3. 科学的健全性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 交絡排除 | ✅ | 完全 (単一ソルバー・フィーダー・seed) |
| 信頼区間 | ✅ | 95% CI あり |
| 収束分析 | ✅ | n=50→1000 の convergence plot あり |
| 感度分析 | ✅ | 閾値感度が本論文の主題そのもの |

### E-4. 実用的メッセージ

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| Actionable な知見 | ✅ | 「Range A vs Range B で HC が 0→0.98 MW」は配電事業者に直接関係する |
| Policy implication | ✅ | 「HCA 論文の比較には閾値の明示が必須」という policy recommendation あり |

### E 判定

- E-1: MODERATE 1 件 (先行研究との具体的数値比較不足)
- E-2: MODERATE 2 件 (単一時刻 + 電圧制約のみ)
- E-3: CRITICAL/MAJOR なし
- E-4: CRITICAL/MAJOR なし

**E 判定: 投稿可 (Top venue)** — CRITICAL なし、MAJOR なし。MODERATE 3 件は改善推奨だが PES GM 5 ページの conference paper としては許容範囲

---

## 総合判定

| 観点 | 判定 |
|---|---|
| A 方針適合性 | ✅ 合格 |
| B 数値信頼性 | ✅ 合格 |
| C 科学的妥当性 | ✅ 合格 |
| D 完成度 | ✅ 合格 |
| E 投稿先水準 (PES GM) | ✅ 投稿可 (MODERATE 3 件) |

### 総合判定: 合格 (Top venue)

try2 からの進化:
- try2: 不合格 (FATAL + CRITICAL x2 + MAJOR x2)
- try3: 合格 (基本品質) だが E (top venue) は不合格
- **try4: 合格 (Top venue)** — n=1000, controlled study, 95% CI, 収束分析, policy implication

---

## 残存 MODERATE 指摘 (改善推奨、合否には影響しない)

| # | 内容 | 改善案 |
|---|---|---|
| E-1a | 先行 HCA 論文との具体的数値比較がない | MDPI 2020 review の閾値一覧表と本結果を対照する 1 段落を追加 |
| E-2a | 単一時刻 (ピーク) のみ | 24h 代表日プロファイルの追加は Phase 2 scope |
| E-2b | 電圧制約のみ | 熱制約 (line loading %) の追加は Phase 2 scope |
