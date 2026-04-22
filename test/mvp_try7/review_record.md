# MVP try7 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: stochastic HCA の結果は閾値選択で 0 と 0.98 MW の間を変動する。既存 metric (固定閾値 HC, HCA-R) は physical interpretability か actionability のいずれかが欠ける
- **先行研究**: Monte Carlo HCA は確立。閾値感度の存在は知られるが、応答曲線の特徴点を形式化した指標はない。薬理学の IC₅₀ がこの問題に構造的に対応するが、HCA への転用は未実施
- **方法**: HC(θ) を dose-response curve として捉え、50% 応答点を HC₅₀ (pu)、遷移幅を HC-width (pu) として定義。IC₅₀ からの cross-disciplinary transfer
- **実験結果**: IEEE 13 で HC₅₀ = 0.914 pu (CI [0.914, 0.915])、HC-width = 0.018 pu。MV ring で HC₅₀ > 0.950 (censored)。Range B から 0.014 pu の閾値強化で HC が半減するという actionable finding
- **考察**: HC₅₀ は fixed-threshold HC にも HCA-R にもない「閾値 headroom の定量化」を提供。ただし 2 フィーダーのみ、censored case の扱いは限定的

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-22 |
| 対象ファイル | `test/mvp_try7/report.md` |
| レビュー方式 | hc50_analysis.json との全数値照合 + hc50_metric.py の root-finding 検証 |
| レビュー方針 | `docs/mvp_review_policy.md` (§4.2 A-E) |

---

## A. 方針適合性

| チェック | 判定 | 根拠 |
|---|---|---|
| §3.1 準拠 | ✅ | Abstract に gridflow 言及なし。Contribution は IC₅₀ 転用 + HC₅₀ 定義 |
| 課題出典 | ✅ | C-2 (ScienceDirect 2025), C-10 (MDPI 2023) |

**A: 合格**

## B. 数値の信頼性

| report 記載 | JSON 実値 | 一致 |
|---|---|---|
| HC₅₀ = 0.9142 | 0.914198 | ✅ |
| HC₅₀ CI [0.9136, 0.9147] | [0.91358, 0.91467] | ✅ |
| HC-width = 0.0175 | 0.017452 | ✅ (4dp round) |
| HC-width CI [0.0170, 0.0181] | [0.01701, 0.01808] | ✅ |
| HC_max = 0.9789 | 0.978910 | ✅ |
| MV ring censored | True | ✅ |
| MV ring HC_max = 1.0377 | 1.037700 | ✅ |

hc50_metric.py L42-49 の `_find_crossing` 関数は線形補間で正しく root-finding を実装。
bootstrap CI は 1000 resamples (seed=42) で一貫。

**B: 合格**

## C. 科学的妥当性

| チェック | 判定 | 根拠 |
|---|---|---|
| 実験設計と主張の整合 | ✅ | HC₅₀ の定義実証には 2 フィーダーで十分 |
| IC₅₀ analogy は構造的か | ✅ | dose (θ) → response (HC) の対応は表面的でなく、曲線上の特徴点抽出という方法論が共通 |
| HC₅₀ = 0.914 の "0.014 pu" 主張は正しいか | ✅ | 0.914 - 0.90 = 0.014 pu ✓ |
| Limitations | ✅ | 5 項目 (2-feeder, censoring, 交絡, 時系列, Hill fit) |

### MODERATE C-1: MV ring の HC₅₀ censoring が指標の限界を露呈

MV ring で HC₅₀ > 0.950 (censored) は「robust」という情報を与えるが、
具体的な HC₅₀ 値は得られない。HC₅₀ = 0.96 と HC₅₀ = 1.05 を区別できない。
extrapolation (Range A 以上への閾値拡張) で対処可能だが未実施。

PES GM 5p としては censored を報告すれば十分。Journal version で extrapolation を要検討。

### MODERATE C-2: HC-width の N/A (MV ring)

HC-width は curve が 90% と 10% を跨ぐ必要があるが、MV ring では curve が flat なため計算不能。指標の適用範囲が feeder characteristics に依存する。Limitations で認知済み。

**C: 合格** (MODERATE 2 件)

## D. 完成度

| チェック | 判定 |
|---|---|
| 図ラベル | ✅ dose-response 表記、HC₅₀ annotation 正確 |
| 用語 | ✅ IC₅₀, Hill coefficient を正確に参照 |
| 再現手順 | ✅ try6 data + hc50_metric.py で再現可能 |

**D: 合格**

## E. 投稿先水準 (IEEE PES GM)

### E-1. 新規性

| チェック | 判定 | 根拠 |
|---|---|---|
| 先行研究との差分 | **✅** | IC₅₀ → HCA の cross-disciplinary transfer は前例なし。HCA-R (ただの平均) とは質的に異なる新規性 |
| 差分が自明でないか | **✅** | 「HC 曲線上の 50% 点を報告する」は事後的には明快だが、薬理学 analogy なしには "threshold sweep のどこを見るか" は自明でない。IC₅₀ analogy が invention の鍵 |
| 先行指標比較 | ⚠️ MODERATE | §2.4 で HCA-R と定性比較あり。EPRI DRIVE 等との定量比較なし |

### E-2. 実験規模

| チェック | 判定 |
|---|---|
| n >= 1000 | ✅ |
| IEEE 標準フィーダー | ✅ IEEE 13 |
| 2 フィーダー以上 | ✅ IEEE 13 + MV ring |
| 時間粒度 | ⚠️ MODERATE ピーク 1 時刻 |
| 制約の網羅性 | ⚠️ MODERATE 電圧のみ |

### E-3. 科学的健全性

| チェック | 判定 |
|---|---|
| Bootstrap CI | ✅ 1000 resamples |
| Cross-disciplinary grounding | ✅ IC₅₀ analogy 明示 |
| Comparison to baseline | ✅ vs fixed HC, vs HCA-R |

### E-4. 実用的メッセージ

| チェック | 判定 | 根拠 |
|---|---|---|
| Actionable | **✅** | 「0.014 pu の閾値変更で HC 半減」は utility planner / regulator が直接使える情報 |
| Policy | **✅** | ANSI 規格改訂議論への具体的 input |

**E: 投稿可 (Top venue)** — MODERATE 3 件 (先行指標比較、時間粒度、熱制約)

---

## 総合判定

| 観点 | 判定 |
|---|---|
| A 方針適合性 | ✅ |
| B 数値信頼性 | ✅ |
| C 科学的妥当性 | ✅ (MODERATE 2) |
| D 完成度 | ✅ |
| E 投稿先水準 | ✅ **Top venue** (MODERATE 3) |

### 総合判定: **合格 (Top venue)**

### HCA-R (try6) vs HC₅₀ (try7) の新規性比較

| 観点 | HCA-R | HC₅₀ |
|---|---|---|
| "just averaging" 批判 | ✅ 該当 | ❌ 該当しない |
| Cross-disciplinary insight | ❌ | ✅ IC₅₀ analogy |
| Physical interpretability | 低 (平均 HC) | **高** (HC 半減閾値) |
| Actionability | 低 | **高** (regulator 直接利用可能) |
| E-1 novelty 判定 | MODERATE (自明) | **合格** (non-trivial transfer) |

HC₅₀ は HCA-R の弱点を全て解消し、genuine novelty を構成する。

---

## 残存 MODERATE

| # | 内容 | 対応 |
|---|---|---|
| C-1 | HC₅₀ censoring (MV ring) | extrapolation or wider θ range |
| C-2 | HC-width N/A (flat feeder) | flat feeder では定義上 "infinite width" |
| E-1 | EPRI DRIVE 等との比較 | 1 段落追記で対応可 |
| E-2a | 時系列 | Phase 2 |
| E-2b | 熱制約 | Phase 2 |
