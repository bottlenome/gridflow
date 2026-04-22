# MVP try5 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: 既存 stochastic HCA は単一の電圧閾値で HC を報告するため、閾値選択（Range A vs Range B）が結果を支配し、論文間の比較が不可能。同一フィーダーでも HC が 0 〜 0.98 MW に変動する
- **先行研究**: Monte Carlo HCA は確立手法 (MDPI 2020) だが、閾値パラメータ空間を sweep して scalar に統合する指標は提案されていない。既存の sensitivity study は ad-hoc なパラメータバリエーションであり、形式的 metric 定義には至っていない
- **方法（提案手法の価値）**: α ∈ [0,1] で Range B ↔ Range A を線形補間し HC(α) curve を定義。その台形積分 HCA-R を「規制不変な HC scalar」として提案。補助指標 HCA-S (感度) と HCA-RR (頑健性比) を併せて 3 指標を形式定義。既存 Monte Carlo 結果の post-processing のみで計算可能
- **実験結果**: IEEE 13 (n=1000) で HCA-R = 0.287 MW (CI [0.272, 0.304])、HCA-S = 0.979 MW、HCA-RR = 0.000。HC(α) curve は α=0.5 付近で急峻に 0 に遷移
- **考察**: Fixed-threshold HC の 0 vs 0.98 MW 二択を 0.287 MW に集約。ただし IEEE 13 は Range A で全配置 reject の degenerate case であり、HCA-RR の識別力が発揮されていない

---

## 総合判定: 条件付き合格

**理由**: methodological contribution (HCA-R の形式定義) は新規性を持つが、
**単一フィーダーの degenerate case のみでの実証** は提案手法の価値を十分に示せていない。
MAJOR 1 件 (E-2a) + MODERATE 5 件。mvp_review_policy §4.3 により条件付き合格。

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-22 |
| 対象ファイル | `test/mvp_try5/report.md` |
| レビュー方式 | 全成果物 (JSON x3, PNG x1, Python x4) との照合 + 数式実装検証 |
| レビュー方針 | `docs/mvp_review_policy.md` (§4.2 A-E) |

---

## A. 方針適合性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow を contribution に含めていないか | ✅ | Abstract (§5.2) に "gridflow" の語なし。Contribution (§5.3) は HCA-R の方法論・性質・実用性・policy の 4 点。§5.3 末尾で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ | C-2 (ScienceDirect 2025)、C-10 (MDPI 2023) を参照。research_landscape.md で引用確認済み |

**A 判定: 合格**

---

## B. 数値の信頼性

### B-1. HC(α) curve: report §3.2 vs hcar_analysis.json

| α | report HC | JSON hc_mw | 一致 |
|---|---|---|---|
| 0.0 | 0.9789 | 0.97891018... | ✅ |
| 0.1 | 0.9342 | 0.93415787... | ✅ |
| 0.2 | 0.6812 | 0.68119771... | ✅ |
| 0.3 | 0.4345 | 0.43449249... | ✅ |
| 0.4 | 0.3084 | 0.30839694... | ✅ |
| 0.5 | 0.0256 | 0.02556838... | ✅ |
| 0.6-1.0 | 0.0000 | 0.0 | ✅ |

CI 値も 11 点全て JSON と 4dp で一致 ✅

### B-2. 提案指標: report §3.3 vs JSON metrics

| 指標 | report | JSON | 一致 |
|---|---|---|---|
| HCA-R | 0.2873 | 0.28732685... | ✅ |
| HCA-R CI | [0.2717, 0.3038] | [0.27173489..., 0.30382122...] | ✅ |
| HCA-S | 0.9789 | 0.97891018... | ✅ |
| HCA-S CI | [0.9465, 1.0137] | [0.94648411..., 1.01372452...] | ✅ |
| HCA-RR | 0.0000 | 0.0 | ✅ |

### B-3. 収束分析: report §3.5 vs JSON convergence

| n | report HCA-R | JSON | 一致 | report CI | JSON CI | 一致 |
|---|---|---|---|---|---|---|
| 100 | 0.2632 | 0.26321... | ✅ | [0.2121, 0.3201] | [0.2121..., 0.3201...] | ✅ |
| 200 | 0.2872 | 0.28718... | ✅ | [0.2519, 0.3268] | [0.2519..., 0.3268...] | ✅ |
| 500 | 0.2917 | 0.29168... | ✅ | [0.2681, 0.3154] | [0.2681..., 0.3154...] | ✅ |
| 1000 | 0.2873 | 0.28733... | ✅ | [0.2717, 0.3038] | ⚠️ 後述 | ⚠️ |

#### MINOR B-3a: n=1000 行の CI が convergence ブロックと不一致

convergence JSON (bootstrap=500) の n=1000 CI: [0.2729, 0.3033] (幅 0.030)
report §3.5 の n=1000 CI: [0.2717, 0.3038] (幅 0.032)
— 後者は **primary analysis** (bootstrap=1000) の値を使用。

同一テーブル内で n=100/200/500 は bootstrap=500、n=1000 のみ bootstrap=1000
から引用しており、bootstrap resample 数が暗黙に切り替わっている。
CI 幅の 1/√n 収束の議論に影響するレベルではないが、方法論的不統一。

### B-4. 実装照合: hcar_metric.py の数式

`hc_at_alpha()` (L82-92): indicator × pv_kw/1000 の mean → 定義 §2.1 と一致 ✅
`hcar()` (L95-105): 台形積分 / span → 定義と一致 ✅
`hcas()` (L108-110): HC(grid[0]) - HC(grid[-1]) → 定義と一致 ✅
`hcarr()` (L113-119): HC(grid[-1]) / HC(grid[0]), clip [0,1] → 定義と一致 ✅

### B-5. 再現性

plan_hash `ac188f2c43da0f66` 両 run で一致、10 physics metrics bit-identical ✅

**B 判定: 合格** (MINOR 1件: B-3a)

---

## C. 科学的妥当性

### MAJOR C-1: 単一フィーダー (degenerate case) での実証は提案手法の価値を示すのに不十分

HCA-R の最大のセールスポイントは「フィーダー間比較を規制不変に行える」(§2.2 point 2)。
しかし本レポートは **IEEE 13 の 1 フィーダーのみ** で実証しており:

1. **cross-feeder 比較が未実施**: 提案手法の中核的利点が検証されていない
2. **degenerate case**: IEEE 13 では HC(Range A) = 0 → HCA-RR = 0、HCA-S = HC(Range B)。
   3 指標が実質 1 自由度 (HCA-R のみが非自明)。指標の識別力が発揮されていない
3. **HC(α) curve の "dead zone"**: α=0.6 以上で完全に 0。
   積分の半分以上が 0 区間に割り当てられ、HCA-R は実質的に
   「Range B 側だけの weighted average」になっている

**PES GM 査読者の予想コメント**: "The paper claims HCA-R enables cross-feeder comparison, but only one feeder is evaluated. Adding at least IEEE 34 or IEEE 123 — where HC(Range A) > 0 — is essential to demonstrate discriminative power."

**修正案**: IEEE 34 (or 37 or 123) の少なくとも 1 フィーダーを追加し、
(HCA-R, HCA-S, HCA-RR) の 2-feeder 比較を実施。HCA-RR > 0 のケースで
指標群の識別力を実証する。

### MODERATE C-2: 「規制不変」主張は厳密には不正確

HCA-R は α ∈ [0, 1] = [Range B, Range A] の特定区間で定義される。
この区間自体が規制依存 (ANSI C84.1 固有) であり、IEC 規格圏では
[Range B, Range A] の数値が異なる。

正確には:
- ❌ "regulation-invariant" (規制不変)
- ✅ "threshold-selection-invariant within a given regulatory range"
  (所与の規制範囲内で閾値選択に不変)

Abstract の "regulatory-invariant hosting capability" は over-claim。
"threshold-choice-invariant" に修正すべき。

### MODERATE C-3: §2.2 "Theoretical properties" の記述が不十分

report §2.2 は 4 性質を列挙するが証明/議論なし:

1. **有界性**: 正しいが trivial (HC(α) ≥ 0 の mean が ≥ 0)
2. **単調性**: **HC(α) の単調減少は一般に保証されない**。over-voltage dominant feeder で
   θ_high が下がることで reject が増える場合、HC(α) は θ_low が支配する区間では
   非単調になりうる。IEEE 13 では θ_low が binding なため偶然単調
3. **連続性**: 有限 N では HC(α) は離散関数 (各配置が境界 α で不連続に accept/reject)。
   N → ∞ で連続になるが、この区別が未記述
4. **比較可能性**: 未実証 (C-1 と同じ)

§5.3 Contribution item 2 で "議論" と書いているが列挙のみで議論ではない。

### MODERATE C-4: α の線形補間の根拠が不十分

Range B → Range A の線形補間は ONE possible choice。
代替として:
- θ_low のみ sweep (θ_high 固定)
- regulatory adoption probability に基づく重み付き積分
- θ_low, θ_high を独立に grid sweep → 2D 積分

線形補間を選ぶ理由 (simplicity / interpretability / regulatory correspondence) は
述べるべき。現状は "規制学的に自然" の一文のみで根拠不足。

### その他合格項目

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| DoD の判定が適切か | ✅ | 全 8 項目に適切な根拠。未検証に ✅ なし |
| Limitations が十分か | ⚠️ | 5 項目列挙あり。ただし C-2 (over-claim) は Limitations に含まれていない |
| 収束分析 | ✅ | n=100→1000 で CI 縮小を確認 |
| Bootstrap 手法 | ✅ | 1000 resamples, seed 明示、i.i.d. 前提を Limitations で認知 |

**C 判定: MAJOR 1件 (C-1) + MODERATE 3件 (C-2, C-3, C-4)**

---

## D. 論文材料としての完成度

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図のラベル・キャプション | ✅ | plot_hcar.py: 4 panel 構成、IEEE 13 / α / θ_low 軸表記正確 |
| 用語 | ✅ | ANSI C84.1 Range A/B 正確定義、bootstrap / trapezoidal 明示 |
| 再現手順 | ✅ | run_hcar_study.sh で全 5 steps (sweep + rerun + analysis + plot) |
| 数式表記 | ✅ | §2.1 に LaTeX 形式で HC(α), HCA-R, HCA-S, HCA-RR を定義 |

**D 判定: 合格**

---

## E. 投稿先水準 (IEEE PES GM)

### E-1. 手法的新規性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 先行研究との差分 | ✅ | 「閾値パラメータ空間を積分して scalar 化する HCA 指標」は MDPI 2020 review / arXiv 2305.07818 / ScienceDirect 2025 等に前例なし。概念は新規 |
| 差分が自明でないか | ✅ | 積分による robust 化は他分野で既知だが、HCA での α 規制パラメータ化 + 3 指標セット定義は新規。"trivial extension" ではない |
| 他の提案指標との比較 | ⚠️ MODERATE | EPRI DRIVE の stochastic HC 等との比較が未実施 |

### E-2. 実験規模・妥当性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| **複数フィーダー** | **❌ MAJOR** | **1 フィーダーのみ。C-1 と同根。提案手法の比較可能性が未実証** |
| n >= 1000 | ✅ | n = 1000 |
| 時間粒度 | ⚠️ MODERATE | ピーク 1 時刻。Limitations 認知 |
| 制約の網羅性 | ⚠️ MODERATE | 電圧制約のみ。熱制約なし |

### E-3. 科学的健全性

| チェック項目 | 判定 |
|---|---|
| 交絡排除 | ✅ — single feeder, single seed, pure post-processing |
| 信頼区間 | ✅ — bootstrap 1000 resamples, 95% CI |
| 収束分析 | ✅ — 4 checkpoint sizes |

### E-4. 実用的メッセージ

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| Actionable な知見 | ✅ | 既存文献の post-processing 変換可能性 |
| Policy implication | ✅ | regulation-invariant (→ threshold-choice-invariant) 比較の必要性 |

**E 判定: MAJOR 1件 (E-2 複数フィーダー) + MODERATE 3件 → 条件付き投稿可**

前回セルフレビューの「合格 (Top venue)」判定は楽観的。
MAJOR C-1 / E-2 が解消されれば Top venue 投稿可。

---

## 指摘一覧

| ID | 重要度 | 内容 | 修正案 |
|---|---|---|---|
| C-1 | **MAJOR** | 単一フィーダー (degenerate) での実証は cross-feeder 比較可能性を検証できない | IEEE 34 or 123 を追加し 2-feeder で HCA-R/S/RR を比較 |
| C-2 | MODERATE | "regulatory-invariant" は over-claim | "threshold-choice-invariant" に修正 |
| C-3 | MODERATE | §2.2 "Theoretical properties" が列挙のみで議論なし。単調性は一般に非保証 | 有界性の 1 行証明 + 単調性の条件 (θ_low dominant case) を注記 |
| C-4 | MODERATE | α 線形補間の根拠不足 | simplicity / ANSI 2-range 体系との対応を 1 段落で議論 |
| E-2 | **MAJOR** (C-1 同根) | 複数フィーダー未実施 | 同上 |
| B-3a | MINOR | 収束テーブル n=1000 の CI が primary analysis (bootstrap=1000) を使用、他行 (bootstrap=500) と不統一 | テーブル内 bootstrap 数を統一 |

---

## 結論

**HCA-R の概念的 contribution は明確であり、PES GM 投稿に値する手法的新規性がある。**
しかし、提案手法の**中核的利点 (cross-feeder comparison)** が未検証のまま
「比較可能性」を主張するのは科学的に不十分。

**修正計画**:
1. **P0 (MAJOR 解消)**: IEEE 34 or 123 を追加し、HCA-RR > 0 のフィーダーで
   3 指標の識別力を実証。2-feeder (HCA-R, HCA-S, HCA-RR) 比較表を report に追加
2. **P1**: Abstract の "regulatory-invariant" → "threshold-choice-invariant" に修正
3. **P1**: §2.2 の性質記述を補強 (有界性の証明、単調性の条件付き議論)
4. **P2**: α 補間の根拠を 1 段落追記
5. **P2**: 収束テーブルの bootstrap 数統一

P0 が解消されれば **合格 (Top venue)** に昇格する。
