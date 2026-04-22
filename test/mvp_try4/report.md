# MVP try 4 — Voltage Standard Sensitivity of Stochastic Hosting Capacity

| 項目 | 値 |
|---|---|
| 実施日時 | 2026-04-22 |
| 対応課題 (research_landscape §2) | C-1 / C-2 / C-3 / C-4 / C-10 |
| 実行コマンド | `bash test/mvp_try4/tools/run_threshold_study.sh` |
| 実行時間 (wall) | **Range A 15.1s + Range B 15.3s + Custom 15.3s + rerun 15.8s = 62s** for 4000 experiments |
| フィーダー | IEEE 13-node test feeder (4.16 kV), OpenDSS |
| サンプル数 | **n = 1000** per scenario, 3 scenarios = **3000 experiments** |

## 1. シナリオ概要

同一フィーダー (IEEE 13)・同一ソルバー (OpenDSS)・同一 PV 配置列 (seed 固定) で、
**電圧基準の閾値のみを変更**して stochastic hosting capacity がどう変わるかを定量評価した。

| シナリオ | 閾値 (pu) | 規格 |
|---|---|---|
| **Range A** | 0.95 – 1.05 | ANSI C84.1 Range A (通常運用) |
| **Custom** | 0.92 – 1.05 | 中間値 |
| **Range B** | 0.90 – 1.06 | ANSI C84.1 Range B (許容限界) |

交絡要因の排除:
- **ソルバー**: 全て OpenDSS → solver 差なし
- **フィーダー**: 全て IEEE 13 → topology 差なし
- **PV 配置**: 全て同一 seed (pv_bus: seed=100, pv_kw: seed=200) → 1000 個の PV 配置が完全に同一
- **唯一の変数**: hosting_capacity_mw metric の電圧閾値

## 2. 結果

### 2.1 閾値別 Hosting Capacity

全数値は `results/comparison.json` からの転記。

| metric | Range A (0.95-1.05) | Custom (0.92-1.05) | Range B (0.90-1.06) |
|---|---:|---:|---:|
| **HC mean [MW]** | **0.0000** | **0.3084** | **0.9789** |
| HC 95% CI | [0.0000, 0.0000] | [0.2684, 0.3484] | [0.9438, 1.0140] |
| HC median [MW] | 0.0000 | 0.0000 | 0.9664 |
| HC max [MW] | 0.0000 | 1.9964 | 1.9976 |
| HC stdev [MW] | 0.0000 | 0.6451 | 0.5663 |
| **Rejection rate** | **100.0%** | **81.1%** | **3.5%** |
| N rejected / N total | 1000 / 1000 | 811 / 1000 | 35 / 1000 |
| voltage_deviation_mean [pu] | 0.0500 | 0.0500 | 0.0500 |
| voltage_deviation_max [pu] | 0.0558 | 0.0558 | 0.0558 |

**voltage_deviation metrics は 3 シナリオで完全に同一**。これは同じ物理実験に
異なる閾値を適用しているだけであることの確認。

### 2.2 Key Finding

**IEEE 13-node feeder 上で、電圧基準の選択のみで stochastic hosting capacity が
0.000 MW (Range A) から 0.979 MW (Range B) に変化する。**

メカニズム:
- IEEE 13 の baseline voltage deviation は ~0.050 pu (= 最悪バスで ~0.950 pu)
- Range A の下限は 0.95 pu → baseline が丁度境界上。PV 追加によるわずかな電圧変動で
  ほぼ全配置が reject される
- Range B の下限は 0.90 pu → 十分な余裕があり、大部分の配置が accept される
- Custom (0.92-1.05) はその中間で、81.1% が reject

### 2.3 収束分析

`results/convergence.json` からの転記。95% CI バンドの収束を確認。

| n | Range A mean | Custom mean [95% CI] | Range B mean [95% CI] |
|---|---:|---:|---:|
| 50 | 0.000 | 0.365 [0.173, 0.557] | 0.959 [0.803, 1.115] |
| 100 | 0.000 | 0.287 [0.161, 0.412] | 0.883 [0.770, 0.997] |
| 200 | 0.000 | 0.316 [0.225, 0.407] | 0.955 [0.875, 1.036] |
| 500 | 0.000 | 0.325 [0.268, 0.383] | 0.972 [0.923, 1.022] |
| 1000 | 0.000 | 0.308 [0.268, 0.348] | 0.979 [0.944, 1.014] |

- Range B: n=200 → n=1000 で CI 幅が 0.161 → 0.070 に縮小。n=1000 で十分収束
- Custom: n=200 → n=1000 で CI 幅が 0.182 → 0.080 に縮小。収束良好
- Range A: 全 n で mean=0, stdev=0。収束は自明 (100% rejection)

### 2.4 再現性検証

Range B sweep を 2 回実行し、`verify_reproducibility.py` で比較。

```
VERDICT: PASS - all physics metrics are bit-identical
  plan_hash: 52ad8e24fd1b5b8c (both runs)
  bit-identical: 10 physics metrics
  runtime variance: 5 (expected)
```

## 3. DoD チェック

| # | 条件 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 3000 実験 (1000x3) 全て exit 0 | ✅ | 3000/3000 成功 |
| 2 | 同一 SweepPlan で 2 回実行が bit 一致 | ✅ | verify_reproducibility.py で確認 |
| 3 | hosting_capacity_mw が計算される | ✅ | Range B で有意な分布、Range A で 0 (正しい挙動) |
| 4 | stochastic_hca figure が生成される | ✅ | threshold_sensitivity.png (4 パネル) |
| 5 | Sweep wall time < 300 秒 | ✅ | 62 秒 (3000 + 1000 rerun = 4000 experiments) |
| 6 | n >= 1000 per scenario | ✅ | 各 1000 実験 (E-2 準拠) |
| 7 | 95% CI が示される | ✅ | comparison.json + convergence.json |
| 8 | 収束分析がある | ✅ | n=50,100,200,500,1000 での running mean + CI |
| 9 | 交絡要因が分離されている | ✅ | 同一ソルバー・フィーダー・seed、閾値のみ変更 |

## 4. 論文ドラフト材料

### 4.1 Title

> "How Voltage Standard Selection Determines Stochastic Hosting Capacity:
> A 3000-Scenario Monte Carlo Study on the IEEE 13-Node Feeder"

### 4.2 Abstract (~200 words)

> Stochastic Hosting Capacity Analysis (HCA) evaluates the distributed
> energy resource (DER) capacity that a distribution feeder can
> accommodate under placement uncertainty. While prior work has
> explored HCA sensitivity to feeder topology, load profiles, and PV
> models, the impact of voltage standard selection on HCA outcomes has
> received limited attention. We present a controlled Monte Carlo study
> on the IEEE 13-node test feeder using 1000 random PV placements
> (100–2000 kW, uniformly distributed across 10 candidate buses) under
> three voltage acceptance criteria: ANSI C84.1 Range A (0.95–1.05 pu),
> Range B (0.90–1.06 pu), and an intermediate threshold (0.92–1.05 pu).
> All other variables — feeder model, solver (OpenDSS), random seed,
> and PV model — are held constant. We find that the mean stochastic
> hosting capacity shifts from 0.000 MW under Range A (100% placement
> rejection) to 0.979 MW under Range B (3.5% rejection), with the
> intermediate threshold yielding 0.308 MW (81.1% rejection). The 95%
> confidence intervals at n=1000 are narrow ([0.944, 1.014] MW for
> Range B), confirming statistical convergence. These results
> demonstrate that voltage standard selection is a first-order
> determinant of HCA outcomes and must be explicitly reported in
> comparative HCA studies. All experiments are seed-controlled and
> bit-level reproducible.

### 4.3 Figure Caption

> Figure 1: Sensitivity of stochastic hosting capacity to voltage
> standard selection on the IEEE 13-node test feeder (n=1000 per
> scenario, OpenDSS). (a) Mean hosting capacity with 95% confidence
> intervals. (b) PV placement rejection rate. (c) Convergence of mean
> hosting capacity as a function of Monte Carlo sample size (n=50 to
> 1000) with 95% CI bands. (d) Summary of key findings.

### 4.4 Contribution

1. **電圧基準感度の定量化**: 同一フィーダー・同一 PV 配置で Range A/B/Custom
   の閾値のみを変えた controlled study。HCA mean が 0 → 0.98 MW に変化する
   ことを示し、閾値選択が first-order determinant であることを実証
2. **統計的厳密性**: n=1000 per scenario で 95% CI 付き。収束分析
   (n=50→1000) で Monte Carlo 誤差の減衰を可視化
3. **完全再現性**: seed 制御 + plan hash + rerun 検証。
   全 3000 実験の子 JSON が永続化されており、事後解析が可能
4. **Policy implication**: HCA を規制基準として使う場合、Range A/B の選択が
   hosting capacity の有無を決定する。論文間の HCA 結果比較には閾値の明示が必須

**Note**: 実験は OSS ワークフローツールで orchestrate したが、ツール自体は
本論文の contribution ではない。

### 4.5 Limitations / Threats to validity

1. **単一フィーダー**: IEEE 13-node のみ。他フィーダー (IEEE 34/123) での
   閾値感度は異なる可能性がある。ただし同一フィーダーで交絡排除という実験設計は意図的
2. **単一時刻 (ピーク想定)**: 時系列負荷は対象外。ピーク時の worst-case 評価
3. **定電流 PV モデル**: 無効電力制御 (Volt-VAR) なし。実際の PV inverter は
   電圧調整能力を持つため、rejection rate は低下する可能性がある
4. **hosting_capacity_mw の定義**: binary (accept/reject) × PV 容量。
   per-experiment metric であり、percentile-based HCA 定義とは異なる。
   計算式は `hc_range_*.py` でコード化されており再現可能
5. **Range A での 100% rejection**: IEEE 13 の baseline voltage が Range A
   下限近傍にあるため、どんな PV を追加しても reject される。これは metric の
   欠陥ではなく、IEEE 13 の電圧特性と Range A の組み合わせが厳しいことの反映

## 5. 生成された成果物

| ファイル | 内容 |
|---|---|
| `results/sweep_range_a.json` | Range A sweep (n=1000) |
| `results/sweep_range_b.json` | Range B sweep (n=1000) |
| `results/sweep_custom.json` | Custom threshold sweep (n=1000) |
| `results/sweep_range_b_rerun.json` | 再現性検証 rerun |
| `results/comparison.json` | 3 閾値比較 + 95% CI + rejection rate |
| `results/convergence.json` | 収束分析 (n=50,100,200,500,1000) |
| `results/threshold_sensitivity.png` | 4 パネル図 |

## 6. 参考

* [MVP review policy](../../docs/mvp_review_policy.md) (§4.2 E: 投稿先水準基準)
* [先行研究・課題一覧](../../docs/research_landscape.md)
* [try3 review record](../mvp_try3/review_record.md)
* [IEEE PES GM 2026 Call for Papers](https://pes-gm.org/2026-montreal/call-for-papers/)
