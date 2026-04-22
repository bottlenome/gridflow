# MVP try 7 — HC₅₀: Pharmacology-Inspired Hosting Capacity Transition Metric

| 項目 | 値 |
|---|---|
| 実施日時 | 2026-04-22 |
| 対応課題 (research_landscape §2) | C-2 / C-10 |
| フィーダー | (1) IEEE 13-node (4.16 kV, OpenDSS)  (2) MV ring 7-bus (20 kV, pandapower) |
| サンプル数 | n = 1000 / feeder (try6 data を post-processing) |
| 新規指標 | **HC₅₀** / **HC-width** |
| 発想法 | TRIZ 原理 13「逆転」+ pharmacological IC₅₀ analogy |

## 1. 問題意識と発想の経緯

### 1.1 try5-6 (HCA-R) の限界

HCA-R は「HC を閾値範囲で平均した」指標であり、数学的に自明 (mean of sensitivity sweep)。
PES GM 査読者に "just averaging" と指摘される根本的弱点があった。

### 1.2 発想法の適用

**TRIZ 原理 13「逆転」**: 入力と出力を逆転する。
- 従来: 閾値 θ → HC (MW)  「この閾値で HC はいくら？」
- **逆転**: HC level → 閾値 θ (pu)  「HC が半分になるのは何 pu？」

**Analogy Transfer (Pharmacology → Power Systems)**:

薬理学の **IC₅₀** (50% Inhibitory Concentration) は薬剤の「効力」を
応答曲線上の特徴点 (50% 阻害濃度) で定義する。これにより:
- 異なる薬を共通のスケールで比較できる
- 絶対的効果量ではなく応答曲線の「位置」で特性を記述
- 応答曲線の「急峻性」(Hill 係数) が付随する情報を与える

配電フィーダーの HCA も「dose-response」構造を持つ:
- **dose** = 規制の厳しさ (θ_low)
- **response** = HC の低下

## 2. 提案手法: HC₅₀ / HC-width

### 2.1 HC₅₀ (Half-Hosting-Capacity Threshold)

HC(θ_low) を下限閾値 θ_low の関数として定義
(上限は θ_high(α) = 1.06 − 0.01α で連動)。

**HC₅₀** = HC(θ) = 0.5 × HC_max を満たす θ_low [pu]

HC_max = HC(0.90) (Range B 下限での HC, 最も寛容な閾値)。
HC₅₀ は HC(θ) curve 上の線形補間で求める。

HC が規制範囲内で 50% に達しない場合、HC₅₀ > 0.95 (censored) と報告する。
これは「Range A を超えても HC が半減しない = 規制的に robust」を意味する。

### 2.2 HC-width (Transition Width)

**HC-width** = θ(HC=0.1×HC_max) − θ(HC=0.9×HC_max) [pu]

HC が max の 90% から 10% に低下する閾値幅。
- 狭い = cliff-like transition (fragile)
- 広い = graceful degradation

### 2.3 IC₅₀ との対応

| 薬理学 | HC₅₀ | 意味 |
|---|---|---|
| Drug concentration | θ_low (pu) | 規制の厳しさ |
| Biological response | HC (MW) | 電力系統の DER 受容力 |
| IC₅₀ | **HC₅₀** | 50% 応答を引き起こす「投与量」 |
| Hill coefficient n | **1 / HC-width** | 応答曲線の急峻性 |
| 高い IC₅₀ = 低い potency | 高い HC₅₀ = **高い robustness** | |

### 2.4 HCA-R との比較

| 観点 | HCA-R (try5-6) | HC₅₀ (本 try) |
|---|---|---|
| 計算 | ∫ HC(α) dα (平均) | root-finding: HC(θ) = 0.5×HC_max |
| 物理的解釈 | 「平均 HC」 | 「HC が半減する閾値」 |
| Actionability | 低い (平均は行動に繋がらない) | **高い** (「θ を X pu にすると HC 半減」) |
| 新規性 | ❌ 平均を取るだけ | ✅ cross-disciplinary transfer |
| 付随情報 | なし | HC-width (遷移の急峻性) |

## 3. 結果

全数値は `results/hc50_analysis.json` からの転記。

### 3.1 2-Feeder HC₅₀ 比較

| 指標 | IEEE 13 | MV ring |
|---|---|---|
| HC_max | 0.9789 MW | 1.0377 MW |
| **HC₅₀** | **0.9142 pu** | **> 0.950 pu** (censored) |
| HC₅₀ 95% CI | [0.9136, 0.9147] | — |
| **HC-width** | **0.0175 pu** | N/A |
| HC-width 95% CI | [0.0170, 0.0181] | — |

### 3.2 解釈

**IEEE 13**:
- HC₅₀ = 0.914 pu: Range B (0.90 pu) から **わずか 0.014 pu** 閾値を
  厳しくするだけで HC が半減する
- HC-width = 0.018 pu: HC の 90%→10% 遷移がわずか **0.018 pu 幅**で完了する
  cliff-like transition
- **規制者への含意**: IEEE 13 フィーダーは Range B (0.90 pu) 前提でしか
  DER を受容できない。Range A 方向へのわずかな規制強化が DER 導入を壊滅させる

**MV ring**:
- HC₅₀ > 0.950 pu (censored): Range A (0.95 pu) の閾値でも HC は半減しない
- HC-width = N/A: HC(θ) curve が flat (全 θ で HC ≈ HC_max)
- **規制者への含意**: MV ring は**いかなる ANSI 閾値選択でも DER 受容力を維持する**
  inherently robust feeder

### 3.3 「HC₅₀ = 0.914 pu」の衝撃

IEEE 13 の HC₅₀ = 0.914 pu は以下を意味する:

Range B (0.90 pu) と HC₅₀ (0.914 pu) の差はわずか **0.014 pu (1.4%)**。
国際的に電圧規格の議論が 0.01 pu 単位で行われていることを考えると、
**規格改訂 1 回分の閾値変更で HC が半減する**。

この知見は fixed-threshold HC (0 MW or 0.98 MW) や HCA-R (0.28 MW) からは
得られない — HC₅₀ 固有の actionable information。

### 3.4 再現性

try6 の child experiment データを post-processing しているため、
try6 の再現性検証 (bit-identical physics metrics) がそのまま適用される。

## 4. 論文ドラフト材料

### 4.1 Title

> "HC₅₀: A Pharmacology-Inspired Metric for Characterizing
> Voltage-Standard Sensitivity of Distribution Feeder Hosting Capacity"

### 4.2 Abstract (~200 words)

> Stochastic Hosting Capacity Analysis (HCA) results are a strong
> function of the voltage threshold chosen: on the IEEE 13-node feeder,
> the same Monte Carlo placement ensemble yields HC = 0 MW at ANSI
> Range A or HC = 0.98 MW at Range B. We observe that the hosting
> capacity response to threshold tightening mirrors the dose-response
> relationship in pharmacology, and borrow the IC₅₀ concept to define
> HC₅₀ — the voltage threshold at which a feeder's stochastic HC
> drops to half its maximum. Complementing HC₅₀, the transition width
> (HC-width) measures the steepness of the dose-response curve,
> analogous to the Hill coefficient. On IEEE 13 (n=1000 placements),
> HC₅₀ = 0.914 pu (95% CI [0.914, 0.915]) with HC-width = 0.018 pu,
> revealing that a mere 0.014 pu tightening from Range B causes 50%
> HC loss — a cliff-like regulatory fragility. On a 7-bus MV feeder,
> HC₅₀ is censored beyond Range A, indicating inherent robustness.
> HC₅₀ is computed as post-processing of standard Monte Carlo HCA,
> requires no new simulations, and provides directly actionable
> information for regulators: exactly how much threshold headroom a
> feeder has before DER hosting capacity collapses.

### 4.3 Contribution

1. **Cross-disciplinary innovation**: 薬理学の IC₅₀ を配電系 HCA に
   transplant。応答曲線上の特徴点 (HC₅₀) + 急峻性 (HC-width) で
   フィーダー特性を記述する新しいフレームワーク
2. **Actionable metric**: HC₅₀ は「閾値を何 pu 厳しくすると HC が半減するか」を
   直接報告する。Fixed-threshold HC や HCA-R にはない actionability
3. **2-feeder demonstration**: IEEE 13 (HC₅₀=0.914, fragile) と
   MV ring (HC₅₀>0.950, robust) で指標の識別力を実証
4. **Post-processing applicability**: 既存 Monte Carlo HCA 結果から
   追加実験なしで計算可能

**Note**: 実験の orchestration には OSS ワークフローツールを使用したが、
ツール自体は本論文の contribution ではない。

### 4.4 Limitations

1. **2 フィーダーのみ**: IEEE 34/123 での HC₅₀ 挙動は future work
2. **HC₅₀ censoring**: MV ring で HC₅₀ > 0.95 (censored)。
   Range A 以上で HC₅₀ を求めるには extrapolation が必要
3. **ソルバー / トポロジ交絡**: IEEE 13 (OpenDSS) vs MV ring (pandapower)
4. **ピーク 1 時刻 + 電圧制約のみ**
5. **Hill equation fit**: 本論文では線形補間で HC₅₀ を求めた。
   Hill equation (4-parameter logistic) fit による HC₅₀ 推定は future work

## 5. 生成された成果物

| ファイル | 内容 |
|---|---|
| `tools/hc50_metric.py` | **HC₅₀ / HC-width reference 実装** |
| `tools/analyze_hc50.py` | 2-feeder 分析 (bootstrap CI) |
| `tools/plot_hc50.py` | 4-panel publication figure |
| `results/hc50_analysis.json` | 全数値結果 |
| `results/hc50_figure.png` | Publication figure |

## 6. 参考

* [try6 report](../mvp_try6/report.md) (HCA-R, base sweep data)
* [try5 review](../mvp_try5/review_record.md) (HCA-R の novelty 限界の指摘)
* IC₅₀ 概念: Cheng & Prusoff (1973), Biochemical Pharmacology
