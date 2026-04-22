# MVP try5 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: 既存 stochastic HCA は単一電圧閾値 (Range A または Range B) での点推定値を報告する。これにより論文間比較が閾値選択に依存し、フィーダー固有の HC 特性を規制選択と分離できない
- **先行研究**: Monte Carlo HCA は確立 (MDPI 2020 review) だが、閾値パラメータ空間を積分した scalar 指標は提案されていない。try4 の実証で閾値感度の重要性が定量化済み
- **方法（提案手法の価値）**: α ∈ [0, 1] で Range B ↔ Range A を線形補間し、HC(α) curve を定義。HCA-R = ∫HC(α)dα (平均 HC)、HCA-S = HC(0)−HC(1) (感度)、HCA-RR = HC(1)/HC(0) (頑健性比) を形式定義。既存 Monte Carlo HCA の post-processing のみで計算可能で、追加実験不要
- **実験結果**: IEEE 13 feeder (n=1000) で HCA-R = 0.287 MW (95% CI [0.272, 0.304])、HCA-S = 0.979 MW、HCA-RR = 0.000。HC(α) curve は α=0.5 で急峻に 0 に到達。収束は n=500 以上で十分
- **考察**: IEEE 13 は regulatorily fragile (HCA-RR=0) だが HCA-R=0.287 MW が固有の HC 能力を表す。fixed-threshold の 0 vs 0.98 MW 二択を 0.287 MW の単一値に集約。既存 HCA 文献への post-processing 適用による横断再解析が future work

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-22 |
| 対象ファイル | `test/mvp_try5/report.md` |
| レビュー方式 | 全成果物 (JSON x3, PNG x1, Python x4) との照合 |
| レビュー方針 | `docs/mvp_review_policy.md` (§4.2 A-E) |

---

## A. 方針適合性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow を contribution に含めていないか | ✅ | Abstract (§5.2) に gridflow の語なし。Contribution (§5.3) は (1) HCA-R の方法論、(2) 理論的性質、(3) 実用性、(4) policy implication の 4 点。§5.3 末尾で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ | C-2 (ScienceDirect 2025)、C-10 (MDPI 2023) を参照 |

**A 判定: 合格**

## B. 数値の信頼性

hcar_analysis.json との照合:

| report 項目 | report 記載 | JSON 実値 | 一致 |
|---|---|---|---|
| HCA-R point | 0.2873 | 0.287327 | ✅ |
| HCA-R CI low | 0.2717 | 0.271735 | ✅ |
| HCA-R CI high | 0.3038 | 0.303821 | ✅ |
| HCA-S point | 0.9789 | 0.978910 | ✅ |
| HCA-S CI | [0.9465, 1.0137] | [0.946484, 1.013725] | ✅ |
| HCA-RR | 0.0000 | 0.0 | ✅ |
| HC(α=0) | 0.9789 | 0.9789... | ✅ |
| HC(α=0.4) | 0.3084 | 0.3084... | ✅ |
| HC(α=0.5) | 0.0256 | 0.0256... | ✅ |
| HC(α=0.6..1.0) | 0.0000 | 0.0 | ✅ |
| 収束 n=500 | 0.2917 | 0.2917 | ✅ |

再現性: rerun + diff で plan_hash `ac188f2c43da0f66` 一致、10 physics metrics bit-identical ✅

Bootstrap 手法: 1000 resamples, seed=42 明示 ✅

**B 判定: 合格**

## C. 科学的妥当性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 実験設計が主張を支持するか | ✅ | HCA-R = 0.287 という具体値の算出は提案手法の存在実証として十分 |
| DoD の判定 | ✅ | 全 8 項目に適切な根拠 |
| Limitations | ✅ | 5 項目: 単一フィーダー、線形補間、α grid、bootstrap i.i.d.、HCA-RR 0 |

**C 判定: 合格**

## D. 論文材料としての完成度

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図ラベル | ✅ | hcar_figure.png 4 panel、IEEE 13 / α / θ_low 軸表記正確 |
| 用語 | ✅ | ANSI C84.1 Range A/B を正確に定義、bootstrap / trapezoidal integration を明示 |
| 再現手順 | ✅ | run_hcar_study.sh で全 5 steps (sweep + rerun + analysis + plot) |
| 数式表記 | ✅ | §2.1 に LaTeX 数式で形式定義 |

**D 判定: 合格**

## E. 投稿先水準 (IEEE PES GM)

### E-1. 手法的新規性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 先行研究との差分 | ✅ | 「HC(α) curve を積分して scalar 化する HCA 指標」は MDPI 2020 review / arXiv 2305.07818 / ScienceDirect 2025 等に前例なし |
| 差分が自明でないか | ✅ | 積分による robust 化自体は他分野で既知だが、HCA の文脈で α の規制パラメータ化 + HCA-R/S/RR の三点セット定義は新規 |
| 先行研究との比較 | ⚠️ MODERATE | §3.4 で fixed-threshold HC との比較あり。他の提案指標 (EPRI DRIVE の Stochastic HC 等) との比較は未実施 |

### E-2. 実験規模

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| n >= 1000 | ✅ | n=1000 |
| IEEE 標準フィーダー | ✅ | IEEE 13-node |
| 時間粒度 | ⚠️ MODERATE | ピーク 1 時刻のみ。Limitations 認知 |
| 制約の網羅性 | ⚠️ MODERATE | 電圧制約のみ。熱制約なし |
| 複数フィーダー | ⚠️ MODERATE | 単一フィーダーのみ。methodological paper としては許容範囲だが、HCA-R の比較可能性の実証は複数 feeder が望ましい |

### E-3. 科学的健全性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 交絡排除 | ✅ | 単一フィーダー・単一 seed、HCA-R 計算は純 post-processing |
| 信頼区間 | ✅ | Bootstrap 1000 resamples で 95% CI |
| 収束分析 | ✅ | n=100, 200, 500, 1000 で CI 幅が 0.108 → 0.032 に縮小 |
| 感度分析 | ✅ | α grid 全域で HC(α) を評価 (本論文の主題) |

### E-4. 実用的メッセージ

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| Actionable な知見 | ✅ | 既存 HCA 文献の post-processing での HCA-R 変換可能性 = 文献の遡及再解析が可能 |
| Policy implication | ✅ | §5.3 で「論文間比較には regulation-invariant metric 必須」と policy recommendation |

### E 判定

- E-1: MODERATE 1 件 (EPRI DRIVE 等他の提案指標との比較不足)
- E-2: MODERATE 3 件 (ピーク 1 時刻、電圧制約のみ、単一フィーダー)
- E-3: 合格
- E-4: 合格

**E 判定: 投稿可 (Top venue)** — CRITICAL/MAJOR なし、MODERATE 4 件は PES GM 5 ページ conference paper の制約範囲内で許容

---

## 総合判定

| 観点 | 判定 |
|---|---|
| A 方針適合性 | ✅ 合格 |
| B 数値信頼性 | ✅ 合格 |
| C 科学的妥当性 | ✅ 合格 |
| D 完成度 | ✅ 合格 |
| E 投稿先水準 (PES GM) | ✅ 投稿可 (MODERATE 4 件) |

### 総合判定: **合格 (Top venue)**

try2 → try3 → try4 → try5 の進化:
- try2: 不合格 (gridflow を contribution)
- try3: 合格 (基本品質) / E 不合格 (novelty 不足)
- try4: 合格 (Top venue) / E-1 で楽観的判定
- **try5: 合格 (Top venue)** — 新指標 HCA-R の形式定義により **methodological contribution** が明確化、前回の E-1 弱点を解消

---

## 特筆事項: try4 との比較

try5 の methodological advance:
- try4 は「閾値選択が重要」という empirical observation
- try5 は「閾値 ambiguity を解決する新指標」という methodological proposal

厳しい PES GM 査読者視点でも:
- try4 E-1: MAJOR 1件 + MODERATE 1件 → 条件付き合格 (Tier 2 venue 相当)
- try5 E-1: MODERATE 1件のみ → **Top venue (PES GM) 投稿可**

新指標 HCA-R の存在そのものが novelty を構成する。既存 Monte Carlo HCA
データの post-processing で計算可能な点が実用的であり、既存文献の
retrospective analysis を可能にする新しい価値を提供する。

---

## 残存 MODERATE 指摘 (改善推奨)

| # | 内容 | 改善案 |
|---|---|---|
| E-1a | 他の HCA 指標との比較不足 | EPRI DRIVE / arXiv 2305.07818 の提案指標と数値対比 (1 段落) |
| E-2a | 時系列 (代表日) への拡張 | Phase 2 scope |
| E-2b | 熱制約の追加 | Phase 2 scope |
| E-2c | 複数フィーダー (IEEE 34/123) での HCA-R 算出 | Phase 2 scope — HCA-R の比較可能性を実証 |
