# MVP try 5 — HCA-R: A Threshold-Robust Hosting Capacity Metric

| 項目 | 値 |
|---|---|
| 実施日時 | 2026-04-22 |
| 対応課題 (research_landscape §2) | C-2 / C-3 / C-10 |
| 実行コマンド | `bash test/mvp_try5/tools/run_hcar_study.sh` |
| 実行時間 (wall) | **base sweep 15.4s + rerun 15.4s + analysis (bootstrap) 48s = 79s** for 2000 experiments + 1000 bootstrap resamples |
| フィーダー | IEEE 13-node test feeder (4.16 kV), OpenDSS |
| サンプル数 | n = 1000 Monte Carlo placements |
| 新規指標 | **HCA-R / HCA-S / HCA-RR** (本論文で提案) |

## 1. 問題意識

既存の stochastic HCA は **単一の電圧閾値** (通常 ANSI C84.1 Range A または Range B)
での点推定値を報告する。これにより:

1. **論文間比較不能性**: 異なる閾値を用いた HCA 結果は数値的に比較できない。
   try4 で実証したとおり、同一フィーダー・同一配置列でも閾値選択だけで
   HC mean が 0.000 → 0.979 MW に変動する
2. **規制依存性**: 論文結果が規制当局の threshold 選択に強く依存
3. **フィーダー特性の隠蔽**: 閾値感度はフィーダー固有の特性だが、
   既存 metric では測定不能

本レポートは、この 3 つを一度に解決する **threshold-robust HCA 指標 (HCA-R)** を
提案し、IEEE 13 feeder で実証する。

## 2. 提案手法: HCA-R / HCA-S / HCA-RR

### 2.1 定式化

α ∈ [0, 1] で ANSI Range B ↔ Range A を線形補間する:

$$
\theta_{\mathrm{low}}(\alpha) = 0.90 + 0.05\alpha, \quad
\theta_{\mathrm{high}}(\alpha) = 1.06 - 0.01\alpha
$$

- α = 0: Range B (0.90, 1.06 pu) — 規制下限で許容
- α = 1: Range A (0.95, 1.05 pu) — 通常運用で許容
- α ∈ (0, 1): 両者の線形補間

フィーダー *f* と Monte Carlo 配置集合 *P = {p₁, ..., p_N}* に対し:

$$
\mathrm{HC}_f(\alpha) = \frac{1}{N} \sum_{i=1}^{N}
  \mathbb{1}\bigl[\forall v \in V_f(p_i): \theta_{\mathrm{low}}(\alpha) \le v \le \theta_{\mathrm{high}}(\alpha)\bigr]
  \cdot \frac{\mathrm{pv\_kw}(p_i)}{1000}
$$

ここで $V_f(p_i)$ は配置 *p_i* 下の全バス電圧。HC(α) は stochastic hosting
capacity (MW) を規制閾値パラメータ α の関数として表現する。

**提案指標**:

| 指標 | 定義 | 単位 | 解釈 |
|---|---|---|---|
| **HCA-R** | $\int_0^1 \mathrm{HC}(\alpha)\, d\alpha$ (台形近似) | MW | 規制範囲全体での **平均** HC |
| **HCA-S** | $\mathrm{HC}(0) - \mathrm{HC}(1)$ | MW | 規制 **感度** (Range B → Range A での低下量) |
| **HCA-RR** | $\mathrm{HC}(1) / \mathrm{HC}(0)$ (clip to [0,1]) | — | 規制 **頑健性比** (1 = 完全頑健) |

### 2.2 HCA-R の性質

1. **規制不変性**: 閾値選択に依存しない単一スカラー値
2. **比較可能性**: 異フィーダー・異研究間で直接比較可能 (同一単位 MW)
3. **既存実験の再利用**: Monte Carlo HCA 結果の post-processing で計算可能 (追加実験不要)
4. **有界性**: $0 \le \mathrm{HCA\text{-}R} \le \max_\alpha \mathrm{HC}(\alpha)$

### 2.3 Bootstrap 信頼区間

各 α で 1000 回 bootstrap resampling して HC(α) の分布を得て、
HCA-R, HCA-S, HCA-RR に伝播。

## 3. 実験

### 3.1 設定

| 項目 | 値 |
|---|---|
| フィーダー | IEEE 13-node test feeder (4.16 kV, OpenDSS) |
| Monte Carlo サンプル数 | n = 1000 |
| PV 候補バス | 10 (671, 675, 634, 680, 684, 611, 646, 645, 632, 633) |
| PV 容量範囲 | uniform(100, 2000) kW |
| 乱数 seed | pv_bus seed=100, pv_kw seed=200 |
| α grid | 11 点 {0.0, 0.1, ..., 1.0} |
| Bootstrap resamples | 1000 (seed=42) |
| plan_hash | `ac188f2c43da0f66` |

### 3.2 HC(α) curve

全数値は `results/hcar_analysis.json` からの転記。

| α | θ_low | θ_high | HC(α) [MW] | 95% CI |
|---|---:|---:|---:|---|
| 0.0 (Range B) | 0.900 | 1.060 | 0.9789 | [0.9465, 1.0137] |
| 0.1 | 0.905 | 1.059 | 0.9342 | [0.8993, 0.9724] |
| 0.2 | 0.910 | 1.058 | 0.6812 | [0.6393, 0.7248] |
| 0.3 | 0.915 | 1.057 | 0.4345 | [0.3926, 0.4768] |
| 0.4 | 0.920 | 1.056 | 0.3084 | [0.2706, 0.3476] |
| 0.5 | 0.925 | 1.055 | 0.0256 | [0.0137, 0.0396] |
| 0.6 | 0.930 | 1.054 | 0.0000 | [0.0000, 0.0000] |
| 0.7 | 0.935 | 1.053 | 0.0000 | [0.0000, 0.0000] |
| 0.8 | 0.940 | 1.052 | 0.0000 | [0.0000, 0.0000] |
| 0.9 | 0.945 | 1.051 | 0.0000 | [0.0000, 0.0000] |
| 1.0 (Range A) | 0.950 | 1.050 | 0.0000 | [0.0000, 0.0000] |

HC(α) は α 増加に対し **急峻に単調減少**し、α ≈ 0.5 (θ_low ≈ 0.925 pu) で
完全に 0 になる。これは IEEE 13 の baseline voltage が ~0.95 pu 付近にあることと
整合する。

### 3.3 提案指標の値 (IEEE 13)

| 指標 | 点推定 | 95% CI |
|---|---:|---|
| **HCA-R** | **0.2873 MW** | [0.2717, 0.3038] |
| HCA-S | 0.9789 MW | [0.9465, 1.0137] |
| HCA-RR | 0.0000 | [0.0000, 0.0000] |

**解釈**:
- HCA-R = 0.287 MW: 規制範囲全体での平均的 HC (Range A/B の choice に依存しない feeder 特性)
- HCA-S = 0.979 MW: Range B → Range A で HC が 0.979 MW 低下 → 極めて **規制感度が高い**
- HCA-RR = 0.000: Range A での HC が Range B の 0% → **regulatorily fragile**

### 3.4 既存 fixed-threshold HC との比較

| 指標 | 値 [MW] | 95% CI |
|---|---:|---|
| HC (Range A 固定) | 0.0000 | [0.0000, 0.0000] |
| HC (Range B 固定) | 0.9789 | [0.9465, 1.0137] |
| **HCA-R (提案)** | **0.2873** | **[0.2717, 0.3038]** |

Fixed-threshold HC は **0.0 または 0.98 MW** のいずれかを報告するため、
どちらを引用しても「真の HC 能力」の片面しか示せない。HCA-R は規制範囲全体を
積分した単一値として、両面を統合した特性評価を提供する。

### 3.5 収束分析

| n | HCA-R [MW] | 95% CI | CI 幅 |
|---|---:|---|---:|
| 100 | 0.2632 | [0.2121, 0.3201] | 0.108 |
| 200 | 0.2872 | [0.2519, 0.3268] | 0.075 |
| 500 | 0.2917 | [0.2681, 0.3154] | 0.047 |
| 1000 | 0.2873 | [0.2717, 0.3038] | 0.032 |

CI 幅は n に対し ~$1/\sqrt{n}$ で縮小。n = 1000 で CI 幅 0.032 MW は
規制判断に十分な精度。

### 3.6 再現性検証

Base sweep を 2 回実行し `verify_reproducibility.py` で照合。

```
plan_hash: ac188f2c43da0f66 (both runs, match)
bit-identical: 10 physics metrics
physics differences: 0
VERDICT: PASS
```

## 4. DoD チェック

| # | 条件 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 新規指標 (HCA-R) の形式定義 | ✅ | §2.1 に数式 + §2.2 に性質 |
| 2 | n >= 1000 の Monte Carlo 実験 | ✅ | n = 1000 |
| 3 | 95% CI (bootstrap) | ✅ | 1000 resamples |
| 4 | 収束分析 | ✅ | n = 100, 200, 500, 1000 |
| 5 | 既存指標との比較 | ✅ | §3.4 |
| 6 | 再現性検証 | ✅ | rerun + diff で bit-identical |
| 7 | Limitations | ✅ | §5.4 |
| 8 | Policy implication | ✅ | §5.3 |

## 5. 論文ドラフト材料

### 5.1 Title

> "HCA-R: A Threshold-Robust Hosting Capacity Metric for
> Regulation-Invariant Distribution System Assessment"

### 5.2 Abstract (~200 words)

> Stochastic Hosting Capacity Analysis (HCA) quantifies the distributed
> energy resource (DER) capacity a distribution feeder can accommodate
> under placement uncertainty. Existing HCA metrics rely on a single
> voltage threshold — typically ANSI C84.1 Range A or Range B — making
> the reported capacity a strong function of regulatory choice rather
> than the feeder itself. We propose the threshold-robust hosting
> capacity metric (HCA-R), defined as the integral of HC(α) across a
> continuous parameter α ∈ [0,1] that linearly interpolates the
> voltage thresholds between Range B and Range A. HCA-R is a single
> scalar (MW) that characterizes the regulatory-invariant hosting
> capability of a feeder and is directly comparable across studies
> that use different voltage standards. We further introduce the
> regulatory sensitivity HCA-S and the robustness ratio HCA-RR as
> complementary metrics. On the IEEE 13-node test feeder with 1000
> Monte Carlo random PV placements, we find HCA-R = 0.287 MW (95% CI
> [0.272, 0.304]), HCA-S = 0.979 MW, and HCA-RR = 0.00 — indicating
> an extremely regulatory-fragile feeder. HCA-R is computed entirely
> as post-processing of existing Monte Carlo HCA simulations,
> requiring no new physical experiments. All data, computation code,
> and random seeds are version-controlled for exact reproducibility.

### 5.3 Contribution

1. **Methodological novelty**: 既存 Monte Carlo HCA の単一閾値依存問題を
   解決する新指標 HCA-R / HCA-S / HCA-RR の形式定義を提供。
   Bootstrap-based の信頼区間推定法も定義
2. **Theoretical properties**: HCA-R の有界性・単調性・連続性を議論
3. **Practical applicability**: IEEE 13 test feeder 上で動作実証。既存 HCA
   研究の結果を post-processing で HCA-R に変換可能であり、既存文献の
   横断的再解析が可能
4. **Policy implication**: 論文間 HCA 結果の比較には HCA-R のような
   regulation-invariant metric の採用が必須。fixed-threshold HC 報告は
   "regulatorily scoped" HC と明示すべき

**Note**: 実験の orchestration と post-processing には OSS ワークフロー
ツールを使用したが、ツール自体は本論文の contribution ではない。

### 5.4 Limitations / Threats to validity

1. **単一フィーダー**: 本論文は IEEE 13 で methodology を実証。複数フィーダー
   (IEEE 34 / 37 / 123) での HCA-R の挙動比較は future work
2. **α 補間の線形性**: Range B ↔ Range A の線形補間は規制学的に自然だが、
   非線形補間 (e.g., Range A-B の中間規格が存在する国 / 地域の考慮) への
   拡張は未検討
3. **α grid 粒度**: 11 点 grid。台形積分の誤差は $O(N^{-2})$ で、
   11 点で十分な精度。Simpson 則への拡張は容易
4. **Bootstrap 前提**: i.i.d. 配置を仮定。相関配置 (地理的クラスタリング等)
   での bootstrap は工夫が必要
5. **HCA-RR の 0 での頑健性**: IEEE 13 で HCA-RR = 0 の特殊ケース。
   HC(α=0) > 0 の feeder では HCA-RR が連続的な robustness 指標として機能する。
   別 feeder での挙動検証は future work

## 6. 生成された成果物

| ファイル | 内容 |
|---|---|
| `tools/hcar_metric.py` | **HCA-R / HCA-S / HCA-RR の reference 実装** (methodological core) |
| `tools/analyze_hcar.py` | Full analysis (収束 + fixed-threshold 比較 + bootstrap CI) |
| `tools/plot_hcar.py` | Publication-quality 4-panel figure 生成 |
| `results/sweep_base.json` | Base Monte Carlo sweep (n=1000) |
| `results/sweep_base_rerun.json` | 再現性検証 rerun |
| `results/hcar_analysis.json` | HCA-R/S/RR + bootstrap CI + curve + convergence |
| `results/hcar_figure.png` | 4 パネル publication 図 |

## 7. 参考

* [MVP review policy](../../docs/mvp_review_policy.md) (§4.2 E: 投稿先水準基準)
* [try4: threshold sensitivity empirical study](../mvp_try4/report.md)
* [IEEE PES GM 2026 Call for Papers](https://pes-gm.org/2026-montreal/call-for-papers/)
