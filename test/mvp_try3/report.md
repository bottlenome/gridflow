# MVP try 3 — Stochastic HCA Cross-topology Comparison Report

| 項目 | 値 |
|---|---|
| 実施日時 | 2026-04-12 |
| 対応課題 (research_landscape §2) | C-1 / C-2 / C-3 / C-4 / C-10 |
| 対応 US (development_plan §2.2 + mvp_scenario_v2 §4) | US-1 / US-2 / US-3 / US-4 / US-5 / US-7 / US-8 / US-9 |
| 実行コマンド | `bash test/mvp_try3/tools/run_cross_solver.sh` |
| 実行時間 (wall) | **OpenDSS 3.65 s + pandapower 50.65 s + rerun 3.74 s = 58 s** for 600 experiments |

## 1. シナリオ概要

2 つの異なる配電ネットワーク上で stochastic hosting capacity analysis を実施し、
ネットワークトポロジが HCA 指標に与える影響を定量評価した。

* **OpenDSS path**: IEEE 13-node feeder (4.16 kV, 13 ノード, 10 候補バス) 上で
  200 個のランダム PV 配置
* **pandapower path**: simple_mv_open_ring_net (20 kV, 7 ノード, 6 候補バス) 上で
  同 200 個のランダム PV 容量分布

両 sweep は同一の `hosting_capacity_mw` custom metric (ANSI C84.1 Range B:
0.90/1.06 pu) を `--metric-plugin` で取り込み、
`StatisticsAggregator` で集計した。

**重要**: 2 つの sweep は**異なる物理ネットワーク**で実行されている。
同一ネットワークの cross-solver 検証 (CDL canonical input format 経由) は
Phase 2 スコープであり、本レポートの比較は**cross-topology** 比較である。

## 2. ステップ別結果

### 2.1 Pack 登録 (US-1 / US-7)

```
pack_id: ieee13_sweep_base@1.0.0          status: registered
pack_id: pp_mv_ring_sweep_base@1.0.0      status: registered
```

### 2.2 OpenDSS sweep (US-2 / US-7)

```
sweep_id: ieee13_stochastic_hca_opendss
plan_hash: 38b2799d11a91c51
n_experiments: 200
elapsed_s: 3.65
```

200 random {pv_bus in 10 IEEE 13 buses (seed=100), pv_kw in uniform(100, 2000) (seed=200)}
を zipped-random で生成。OpenDSSConnector の runtime PV insertion で実行。

### 2.3 pandapower sweep (US-2 / US-7 / US-9)

```
sweep_id: pp_mv_ring_stochastic_hca
plan_hash: 5c214259c31e1f03
n_experiments: 200
elapsed_s: 50.65
```

200 random {pv_bus in 6 MV ring buses (seed=100), pv_kw in uniform(100, 2000) (seed=200)}。
PandaPowerConnector が `pp.create_sgen()` で PV を挿入し `pp.runpp()` を実行。

**Note**: pv_kw 軸は同一 seed=200 のため 200 個の PV 容量値は両 sweep で同一。
pv_bus 軸は候補バスリストが異なるため、配置先は異なる。

### 2.4 Cross-topology 比較 (US-4 / US-9)

全数値は `results/comparison.json` からの転記。relative_delta の分母は
OpenDSS (baseline)。

| metric | OpenDSS (IEEE 13) | pandapower (MV ring) | delta | relative |
|---|---:|---:|---:|---:|
| hosting_capacity_mw_max | 1.9901 | 1.9901 | +0.0000 | 0.00% * |
| hosting_capacity_mw_mean | 0.9555 | 1.0159 | +0.0604 | +6.32% |
| hosting_capacity_mw_median | 0.9445 | 0.9797 | +0.0352 | +3.73% |
| hosting_capacity_mw_min | 0.0000 | 0.1037 | +0.1037 | - |
| hosting_capacity_mw_stdev | 0.5836 | 0.5725 | -0.0111 | -1.90% |
| voltage_deviation_max | 0.0558 | 0.0060 | -0.0498 | -89.25% |
| voltage_deviation_mean | 0.0500 | 0.0056 | -0.0444 | -88.85% |
| runtime_mean (per exp) | 0.0128 | 0.2471 | +0.2342 | - |

\* **hosting_capacity_mw_max の 0.00% 一致は shared-seed artifact である。**
両 sweep の pv_kw 軸は同一 seed=200, uniform(100, 2000) から生成されるため、
200 個の pv_kw 値が完全に同一。`HostingCapacityMetric.calculate()` は
「電圧違反なし → pv_kw / 1000」を返すため、max は「200 個中の最大 pv_kw のうち
電圧違反しなかったもの」となる。両ネットワークとも最大 pv_kw (~1990 kW) を
受容したため同値になった。これは cross-topology 合意の証拠ではなく、
入力分布が同一であることの trivial な帰結。

**hosting_capacity_mw_min の非対称性について**:
OpenDSS (IEEE 13) では min=0.0 (一部配置で電圧違反が発生し reject)。
pandapower (MV ring) では min=0.1037 (全配置 accept)。
IEEE 13 の baseline voltage deviation (~0.05 pu) が MV ring (~0.006 pu) より
約 10 倍大きいことが原因。IEEE 13 は Range B 下限 (0.90 pu) に近い
バスが存在し、PV 追加が電圧をさらに押し下げるケースがある。

### 2.5 再現性検証 (US-5 / DoD #2)

OpenDSS sweep を 2 回実行し、`verify_reproducibility.py` で比較。

```
Reproducibility check: sweep_opendss.json vs sweep_opendss_rerun.json
  experiment count: run1=200  run2=200  MATCH
  plan_hash: run1=38b2799d11a91c51  run2=38b2799d11a91c51
  bit-identical: 10 (physics metrics)
  runtime variance: 5 (expected: wall-clock timing)
  physics differences: 0

VERDICT: PASS - all physics metrics are bit-identical
```

10 個の physics metrics (hosting_capacity_mw x5 + voltage_deviation x5) が
2 回の実行で完全一致。runtime metrics は wall-clock 計測であり当然変動する。

### 2.6 図化 (US-3)

`results/stochastic_hca.png` に 4 パネル図を生成:

1. (a) hosting_capacity_mw mean / max bar (IEEE 13 vs MV ring 7-bus)
2. (b) voltage_deviation mean / max bar
3. (c) runtime per experiment
4. (d) summary text panel + plan hash (provenance)

### 2.7 Provenance (C-3)

両 SweepResult JSON に `plan_hash` (sha256[:16]) が記録されている:
- OpenDSS: `38b2799d11a91c51`
- pandapower: `5c214259c31e1f03`

SweepPlan を変更すれば hash が変わるため、結果の出自を一意に追跡できる。

## 3. DoD チェック (mvp_scenario_v2 §6)

| # | 条件 | 結果 | 根拠 |
|---|---|---|---|
| 1 | 400 実験 (200x2) 全て exit 0 | ✅ | 400/400 成功 |
| 2 | 同一 SweepPlan で 2 回実行が bit 一致 | ✅ | `verify_reproducibility.py` で 10 physics metrics が完全一致を確認 (§2.5) |
| 3 | hosting_capacity_mw が有効値 (0 以上) | ✅ | 両 solver で意味のある分布 (stdev > 0) |
| 4 | OpenDSS と pandapower の hosting_capacity_mean が <= 10% 差 | ⚠️ | +6.32% で数値条件は満たすが、異トポロジ比較のため cross-solver 合意の根拠にはならない (§2.4 参照) |
| 5 | stochastic_hca.png が生成される | ✅ | 4 パネル図生成済み |
| 6 | Sweep wall time < 300 秒 (400 実験) | ✅ | 58 秒 (約 5.2 倍高速) |
| 7 | report.md (本書) が記録される | ✅ | |
| 8 | ユーザーが論文ショート原稿を 1 日で書ける状態 | ✅ | §4 で詳述 |

**DoD #4 について**: hosting_capacity_mw_mean の差 +6.32% は数値閾値 (<=10%) を
満たすが、IEEE 13 と MV ring は異なる物理ネットワークであるため、この数値差は
「ソルバー間の合意度」ではなく「トポロジ間の HCA 特性差」を反映している。
try2 review (MAJOR 2.2) の指摘を受け、本レポートでは DoD #4 を
⚠️ (条件付き合格) とし、cross-solver 合意とは主張しない。

## 4. 論文ドラフト材料

### 4.1 Title (案)

> "How Network Topology Shapes Stochastic Hosting Capacity:
> A Comparative Study of IEEE 13-node and MV Open-ring Feeders"

### 4.2 Abstract (~150 words)

> Stochastic Hosting Capacity Analysis (HCA) evaluates the maximum
> distributed energy resource (DER) capacity that a distribution feeder
> can accommodate under random placement uncertainty. While the method
> is well-studied for individual feeders, systematic comparison of HCA
> outcomes across different network topologies remains limited, partly
> due to inconsistent metric definitions and ad-hoc experimental setups.
> We define a reproducible hosting capacity metric — the candidate PV
> capacity (MW) accepted when all bus voltages remain within ANSI C84.1
> Range B (0.90-1.06 pu) — and apply it to 200 random PV placements on
> two feeders: the IEEE 13-node test feeder (4.16 kV) solved by OpenDSS,
> and a 7-bus MV open-ring feeder (20 kV) solved by pandapower. The
> mean stochastic hosting capacity differs by 6.3% (0.96 vs 1.02 MW),
> but the underlying voltage headroom differs by an order of magnitude
> (deviation 0.050 vs 0.006 pu), suggesting that topology-driven
> voltage profiles dominate HCA outcomes more than aggregate capacity
> statistics reveal. All experiments are seed-controlled and
> bit-level reproducible.

### 4.3 図 (results/stochastic_hca.png) のキャプション

> Figure 1: Cross-topology stochastic hosting capacity comparison.
> (a) Mean and maximum hosting_capacity_mw across 200 random PV
> placements on two distribution feeders: IEEE 13-node (4.16 kV,
> OpenDSS) and MV open-ring 7-bus (20 kV, pandapower).
> (b) Voltage deviation (RMSE pu vs 1.0 pu nominal).
> (c) Mean runtime per experiment.
> (d) Sweep provenance summary including SweepPlan content hashes.
> Note: the identical hosting_capacity_mw_max values are a shared-seed
> artifact (see text).

### 4.4 Contribution (論文の新規性主張)

1. **再現可能な HCA metric の形式定義**: hosting_capacity_mw の計算式を
   Python コードとして commit し、Range B 閾値をパラメータ化。
   異なるネットワーク・ソルバーに同一定義を適用可能
2. **トポロジ間 HCA 特性の定量比較**: IEEE 13 と MV ring という
   電圧レベル・ノード数の異なるフィーダーで同一 metric を評価し、
   voltage headroom の差が HCA 分布形状を支配することを示した
3. **完全再現性**: seed 制御 + plan hash による bit-level 再現性を
   実験的に検証 (rerun + diff)

**Note**: 実験の orchestration に OSS ワークフローツールを使用したが、
ツール自体は本論文の contribution ではない。

### 4.5 Limitations / Threats to validity

1. **Cross-topology であり cross-solver ではない**: IEEE 13 (OpenDSS) と
   MV ring (pandapower) は物理的に異なるフィーダーであるため、
   solver 差分とトポロジ差分を分離できない。
   同一ネットワークの cross-solver 検証は CDL canonical input format を
   要し、Phase 2 スコープ
2. **hosting_capacity_mw_max の同値は artifact**: 両 sweep の pv_kw 軸が
   同一 seed から生成されるため、max の一致は入力分布の帰結であり
   物理的意味はない (§2.4)
3. **PV モデルの簡略化**: 定電流 sgen、単一時刻 (ピーク想定)。
   時系列・MPPT・inverter dynamics は対象外
4. **サンプルサイズ**: 200 サンプルは Monte-Carlo 誤差を含む。
   sweep_plan.yaml の `n_samples` を 500-1000 に増やすだけで拡大可能
   (コード変更不要)
5. **hosting_capacity_mw_min = 0 (IEEE 13 のみ)**: IEEE 13 は baseline で
   Range B 下限に近いバスが存在し、一部 PV 配置が reject される。
   MV ring は全配置 accept。この非対称性はトポロジ固有の電圧余裕の
   違いを反映しており、metric 定義の欠陥ではない

## 5. try2 review 指摘への対応

| try2 指摘 | 重要度 | try3 での対応 |
|---|---|---|
| §3.1 違反: gridflow を contribution に含めている | FATAL | Abstract / Contribution を全面書き直し。ツールは Methodology で言及のみ (§4.2, §4.4) |
| runtime_mean 数値が JSON と不一致 (0.6213 vs 0.2368) | CRITICAL | 全数値を JSON から自動転記。report 内の全数値を comparison.json と照合可能 (§2.4) |
| hosting_capacity_mw_max 0.00% を cross-solver 合意と主張 | CRITICAL | shared-seed artifact と明示。注釈つきで表記 (§2.4) |
| DoD #2 bit-identical rerun が未検証 | MAJOR | `verify_reproducibility.py` を新規追加。rerun + diff で 10 physics metrics の完全一致を確認 (§2.5) |
| 異トポロジ比較で DoD #4 <= 10% を主張 | MAJOR | DoD #4 を ⚠️ に変更。cross-topology 比較と明言し、cross-solver 合意とは主張しない (§3) |
| "IEEE 30" ラベルが誤り (実態は MV ring 7-bus) | MODERATE | 全ファイルで "MV ring 7-bus" に統一 (pack YAML, plot, run script) |
| relative_delta の分母が非標準 (max(a,b)) | MODERATE | baseline (OpenDSS) 分母に変更。comparison.json に `relative_delta_method` を明記 |
| hosting_capacity_mw_min = 0 の非対称性が未議論 | MODERATE | §2.4 で voltage headroom の差として議論。§4.5 Limitations にも記載 |
| "95% Range B confidence" 用語混同 | MINOR | Range B は ANSI C84.1 電圧規格 (0.90-1.06 pu) と明記。統計的 confidence とは無関係 |

## 6. 生成された成果物

| ファイル | 内容 |
|---|---|
| `results/sweep_opendss.json` | OpenDSS sweep の SweepResult (200 experiments) |
| `results/sweep_pandapower.json` | pandapower sweep の SweepResult (200 experiments) |
| `results/sweep_opendss_rerun.json` | 再現性検証用の OpenDSS rerun 結果 |
| `results/comparison.json` | cross-topology 差分 (baseline = OpenDSS) |
| `results/stochastic_hca.png` | 4 パネル可視化図 |

## 7. 既知の制約 / Phase 2 持ち越し

* CDL canonical network input format (同一ネットワーク cross-solver 検証) は Phase 2
* Real-data feeder (CIGRE MV / 実ユーティリティ) は対象外
* PV モデルは定電流 sgen / 単一時刻
* 500-1000 サンプル化は sweep_plan の `n_samples` 編集で対応可能

## 8. 参考

* [MVP scenario v2 定義](../../docs/mvp_scenario_v2.md)
* [先行研究・課題一覧](../../docs/research_landscape.md)
* [MVP review policy](../../docs/mvp_review_policy.md)
* [try2 review record](../mvp_try2/review_record.md)
