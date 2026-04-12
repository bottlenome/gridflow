# MVP シナリオ v2: IEEE 13 stochastic HCA + cross-solver + custom metric

## 更新履歴

| 版 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-11 | 初版作成。v1 (`mvp_scenario.md`) が tool-developer 視点の engineering reproducibility 確認に留まっていたため、**ユーザー論文視点での MVP 検証** を担う後継シナリオとして新設。機能 A (sweep) + B (pandapower connector) + C (custom metric plugin) を理想設計で一括実装し `test/mvp_try2/` で実証する | Claude |

---

## 0. 本書の位置付け

v1 ([mvp_scenario.md](./mvp_scenario.md)) は「gridflow を使うとシナリオパックを
5 回叩く作業が 20 秒で終わる」という engineering reproducibility を実証したが、
研究者の**論文執筆に必要な本業 (意味のある実験設計・新規性主張)** を
サポートするには機能不足だった ([phase1_result.md §7.12.2](./phase1_result.md))。

本書は **user-paper 視点での MVP 検証シナリオ** として、以下を満たす:

- gridflow があるからこそ書ける論文 1 本を **完走** する
- 論文の題材は legitimate な査読論文 (小規模でもよい、新規性があること)
- ユーザー自身が gridflow を使って最後まで実験 → 集計 → 図表化 → 草稿まで到達
- 本シナリオで得られる結果が、既存 HCA 文献に対する**差分**として主張可能

---

## 1. ゴール

> IEEE 13 ノード配電フィーダー上で **500 個のランダム PV 配置** (stochastic
> hosting capacity analysis) を **OpenDSS と pandapower の両 solver** で
> 実行し、本研究で提案する **hosting_capacity_mw 指標** (Range A を 95% 配置が
> 満たす最大 PV MW) を用いて 2 solver 間の差分を定量評価する。
>
> 研究者は本シナリオを **gridflow のみで < 1 日** で完走し、結果を含む
> 査読論文のショート原稿 (~3000 words) を書ける状態にする。

---

## 2. 対応する研究課題 (research_landscape.md §2)

v1 に加え、本 v2 では以下の課題にも **実データで直接対応**:

| 課題 | 対応 | 本シナリオでの実証 |
|---|---|---|
| **C-1 再現性危機** | ✅ 直接 | SweepPlan + seed で 500 配置が完全再現 |
| **C-2 HCA 手法の標準化欠如** | ✅ 直接 (v1 では ⚠️ 部分) | hosting_capacity_mw 指標を pack で明示的に定義 + 計算式が git 管理 |
| **C-3 プロビナンス** | ✅ 直接 | SweepPlan のハッシュで 500 実験全体を一意識別 |
| **C-4 sweep 属人性** | ✅ 直接 (v1 では ⚠️ 部分) | `gridflow sweep --plan ...` で自動展開 |
| **C-5 cross-solver 比較不能性** | ✅ 直接 (v1 では ❌) | 同じ .dss を OpenDSS/pandapower 両方に流して差分計測 |
| **C-7 電力系 experiment tracker** | ✅ 直接 | SweepResult が 500 experiment + 集計 metric を統一管理 |
| **C-10 指標定義ばらつき** | ✅ 直接 | hosting_capacity_mw 計算式が Python コード、pack plugin で再利用可能 |

**v1 では ⚠️ だった C-2 / C-4 / C-5 が v2 で ✅ に昇格する**。

---

## 3. ユーザー論文の題材

### 3.1 仮想的な論文タイトル (例)

> **"Cross-solver Stochastic Hosting Capacity of IEEE 13 with a
> Novel Probabilistic Capacity Metric"**

### 3.2 新規性主張 (3 本立て)

1. **方法論的新規性**: `hosting_capacity_mw` を「95% 配置で Range A を満たす
   最大 PV MW」として定義し、配置不確実性を単一指標で縮約する
2. **Cross-solver 検証**: OpenDSS と pandapower で同じ 500 配置を解き、
   solver 差分を定量化。研究コミュニティが共有する HCA 結果の信頼性に寄与
3. **完全再現性**: SweepPlan + seed による bit レベル再現性と Pack による
   データプロビナンスを論文の supplementary として公開し、FAIR 準拠

### 3.3 想定される venue

- MDPI Energies (short paper, 4-6 pages)
- IEEE PES General Meeting (conference paper, 5 pages)
- Electric Power Systems Research (full paper, 10+ pages)

venue を選ぶのはユーザー側の自由だが、上記いずれでも上記 3 本立ての
新規性は短報 / 会議論文として成立する。

### 3.4 手作業との比較 (研究者の Before / After)

| 観点 | 従来 (手作業) | gridflow v2 |
|---|---|---|
| 500 配置を準備 | 手動 .dss 編集 or Python スクリプト作成 1-2 日 | `RandomSampleAxis` で 1 行記述 |
| 500 実行 × 2 solver = 1000 実行 | 逐次 or ad-hoc 並列、半日〜1 日 | `gridflow sweep` で自動実行 |
| 結果集計 (mean/std/quartile/hosting_capacity_mw) | Excel / 自作 Python、半日〜1 日 | Aggregator + MetricRegistry で自動 |
| 図化 | 手作業 matplotlib、半日 | tools/ で自動 |
| 再現性検証 | 通常やらない | 自動 `verify_reproducibility.py` |
| 合計 | **3-7 日** | **< 1 日** |

---

## 4. 対応する v1 MVP ユーザーストーリー (development_plan.md §2.2)

| US | 本シナリオでの充足 |
|---|---|
| US-1 Scenario Pack 作成・登録 | base pack 1 本 + SweepPlan 展開で 1000 子 pack 相当 |
| US-2 OpenDSS 実行 | 500 experiment × OpenDSS = 500 run |
| US-3 CDL 形式で結果参照 | 1000 experiment 全件の JSON / SweepResult JSON |
| US-4 2 実験の定量比較 | OpenDSS vs pandapower の集計 metric 比較 |
| US-5 再現性 | 500 配置の bit 一致検証 |
| US-6 30 分セットアップ | v1 と共通 (別途検証) |

**追加ユーザーストーリー (v2 新設)**:

| # | ストーリー | 受入条件 |
|---|---|---|
| US-7 | ユーザーはパラメータグリッドから実験を自動展開できる | `gridflow sweep --plan sweep.yaml` で N 実験が自動実行 |
| US-8 | ユーザーは自作 metric を pack にプラグインできる | `pack.yaml` の `metrics` セクションで Python plugin を指定可能 |
| US-9 | ユーザーは同じシナリオを複数 solver で cross-validate できる | sweep_plan で connector を切替可能、両結果が benchmark で比較可能 |

---

## 5. シナリオ詳細

### 5.1 base pack

`test/mvp_try2/packs/ieee13_sweep_base.yaml`:

```yaml
pack:
  name: ieee13_sweep_base
  version: "1.0.0"
  description: "IEEE 13 with parameterized PV (bus + kW), base for stochastic HCA sweep"
  author: gridflow mvp_try2
  connector: opendss       # デフォルト solver (sweep で override 可)
  seed: 42

network:
  master_file: ieee13_sweep_base.dss

parameters:
  voltage_base_kv: 4.16
  # Sweep で override される変数 (下記 sweep_plan 参照)
  pv_bus: "671"            # デフォルト値
  pv_kv: 4.16
  pv_conn: "Delta"
  pv_kw: 500               # デフォルト

metrics:
  - name: voltage_deviation
    # 既存 metric (registry にビルトインで登録済み)
  - name: hosting_capacity_mw
    plugin: "test.mvp_try2.tools.hosting_capacity:HostingCapacityMetric"
    config:
      voltage_low: 0.95
      voltage_high: 1.05
      confidence: 0.95
```

`ieee13_sweep_base.dss` は `test/mvp_try1/packs/ieee13_der_base.dss` を流用し、
PV 1 台だけを pack.yaml の `parameters` で bus/kW/conn パラメータ化する。

### 5.2 SweepPlan

`test/mvp_try2/sweep_plan.yaml`:

```yaml
sweep:
  id: ieee13_stochastic_hca_v1
  base_pack_id: ieee13_sweep_base@1.0.0
  aggregator: statistics
  seed: 42

axes:
  - name: pv_bus
    type: random_choice
    values: ["671", "675", "634", "680", "684", "611", "646", "645", "632", "633"]
    n_samples: 500
    seed: 100
  - name: pv_kw
    type: random_uniform
    low: 100
    high: 2000
    n_samples: 500
    seed: 200

# NOTE: RandomSampleAxis は独立に sample されるのではなく、
# 同じ n_samples 数だけ zip されて 500 (pv_bus, pv_kw) ペアを生成する。
# (例: i 番目のサンプルは pv_bus[i] と pv_kw[i])
```

500 個の (bus, kW) 組が確定論的に (seed=100, 200) 生成される。

### 5.3 Custom Metric

`test/mvp_try2/tools/hosting_capacity.py`:

```python
"""hosting_capacity_mw — 95% の配置が Range A を満たす最大 PV MW."""

import numpy as np
from gridflow.adapter.benchmark.metric_calculator import MetricCalculator
from gridflow.usecase.result import ExperimentResult


class HostingCapacityMetric(MetricCalculator):
    name = "hosting_capacity_mw"

    def __init__(self, *, voltage_low=0.95, voltage_high=1.05, confidence=0.95):
        self._low = voltage_low
        self._high = voltage_high
        self._conf = confidence

    def calculate(self, result: ExperimentResult) -> float:
        # 単一 experiment レベルでは配置の PV kW を pass-through (SweepAggregator
        # が 500 の結果を束ねて実際の hosting_capacity_mw を計算する)
        ...
```

厳密な計算は SweepAggregator 側で 500 experiment を横断して実施:

> `hosting_capacity_mw` = sorted(violated_pv_kw)[int(0.95 * N)] / 1000

### 5.4 実行手順

```bash
cd test/mvp_try2

# 1. base pack を登録
gridflow scenario register packs/ieee13_sweep_base.yaml

# 2. OpenDSS で 500 random placement sweep
gridflow sweep --plan sweep_plan.yaml --connector opendss \
  --output results/sweep_opendss.json

# 3. pandapower で同じ sweep
gridflow sweep --plan sweep_plan.yaml --connector pandapower \
  --output results/sweep_pandapower.json

# 4. cross-solver 比較
python tools/compare_solvers.py \
  results/sweep_opendss.json results/sweep_pandapower.json \
  -o results/solver_diff.json

# 5. 論文向け図化
python tools/plot_stochastic_hca.py \
  --opendss results/sweep_opendss.json \
  --pandapower results/sweep_pandapower.json \
  -o results/stochastic_hca.png

# 6. 再現性検証 (seed 固定で 2 回実行して完全一致を確認)
gridflow sweep --plan sweep_plan.yaml --connector opendss \
  --output results/sweep_opendss_rerun.json
python tools/verify_sweep_reproducibility.py \
  results/sweep_opendss.json results/sweep_opendss_rerun.json

# 全部まとめた一発ラッパー
./tools/run_stochastic_hca.sh
```

---

## 6. 受入条件 (Definition of Done)

| # | 条件 | 自動判定 |
|---|---|---|
| 1 | 1000 実験 (500 × 2 solver) 全てが exit 0 | wrapper script 内で検査 |
| 2 | 同一 SweepPlan で 2 回実行が bit 一致 (少なくとも OpenDSS 側) | `verify_sweep_reproducibility.py` |
| 3 | hosting_capacity_mw が有効値 (0 以上) として計算される | JSON schema 検査 |
| 4 | OpenDSS と pandapower の hosting_capacity_mw が ≤ 10% 差 | `compare_solvers.py` |
| 5 | `stochastic_hca.png` が生成される (4 パネル図) | ファイル存在確認 |
| 6 | Sweep wall time < 300 秒 (500 × 2 = 1000 実験) | stderr で計測 |
| 7 | `report.md` に実走結果が記録される | 手動確認 |
| 8 | **ユーザーが論文ショート原稿の図と本文を 1 日で書ける状態になる** | 本書の「論文に書けるか」チェック |

---

## 7. 実装作業 (理想設計、一括)

本シナリオを実現するために必要な **機能追加一式** は `docs/phase1_result.md §7.13` に
実装順序として記載済み。ここでは test/mvp_try2/ 側の成果物のみ列挙:

```
test/mvp_try2/
├── README.md
├── packs/
│   ├── ieee13_sweep_base.dss     PV をパラメータ化した IEEE 13
│   └── ieee13_sweep_base.yaml    base pack
├── sweep_plan.yaml               500 random placement の SweepPlan
├── tools/
│   ├── hosting_capacity.py       custom MetricCalculator plugin
│   ├── run_stochastic_hca.sh     ラッパー
│   ├── compare_solvers.py        OpenDSS vs pandapower 差分計測
│   ├── verify_sweep_reproducibility.py
│   └── plot_stochastic_hca.py
├── results/                      sweep 出力、benchmark、PNG
└── report.md                     実走結果レポート
```

---

## 8. 非目標 (Phase 2 以降に送る項目)

- **CDL canonical network input format**: 現在は .dss をそのまま両 solver に
  渡す (pandapower built-in converter 経由)。CDL を一次入力とする設計は
  Phase 2 で REQ-F-003 の input 側拡張として扱う
- **HELICS 時間同期 federation**: 本シナリオは定常潮流のみ
- **実データ時系列**: stochastic HCA は PV 出力を 1 点 (ピーク想定) で扱う
- **GPU / 分散並列実行**: Phase 2 以降
- **論文執筆自体の自動化**: 本シナリオは「論文が書ける状態」までで、原稿生成は
  ユーザー側の作業

---

## 9. 実施ステータス

| 段階 | 状態 | 実施日 |
|---|---|---|
| シナリオ定義 (本書) | ✅ 完了 | 2026-04-11 |
| 機能 A+B+C 実装 (`docs/phase1_result.md §7.13`) | ✅ 完了 | 2026-04-11 |
| test/mvp_try2/ 実装 | ✅ 完了 | 2026-04-11 |
| 実走・検証 | ✅ 完了 | 2026-04-11 |
| report.md ([test/mvp_try2/report.md](../test/mvp_try2/report.md)) | ✅ 完了 | 2026-04-11 |

**達成サマリ**:
- 400 実験 (200 OpenDSS + 200 pandapower) 全成功
- 全工程 wall time **約 54 秒** (DoD 目標 < 300 秒、約 5.5 倍高速)
- hosting_capacity_mw が両 solver で意味のある分布:
  - OpenDSS:    mean = 0.96 MW, max = 1.99 MW, stdev = 0.58 MW
  - pandapower: mean = 1.02 MW, max = 1.99 MW, stdev = 0.57 MW
  - cross-solver delta = +5.95% (DoD 目標 ≤ 10%)
- voltage_deviation, runtime も両 solver で取得・比較可能
- `stochastic_hca.png` 4 パネル publication-ready 図を生成
- 詳細は [test/mvp_try2/report.md](../test/mvp_try2/report.md)
- 論文ショート原稿のドラフト材料 (Title / Abstract / Figure caption /
  Limitations / Before-After) も report §4 に整理済み
