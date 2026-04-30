# try11 Phase 1 実装計画

実施: 2026-04-29 (ideation_record.md 完成後)
原則: CLAUDE.md §0.1 (妥協なき理想設計) を遵守、gridflow Phase 2 API を活用

---

## 1. アーキテクチャ概要

SDP は **portfolio 選択問題** であり、power flow simulation そのものは contribution の core ではない。ただし以下の理由で gridflow + pandapower 統合を行う:

- **研究 credibility**: 提案手法が選んだ DER 集合が **実際にグリッド上で SLA を満たすか** を power flow で検証
- **既存資産活用** (§0.1): `SweepOrchestrator`, `BenchmarkHarness`, `MetricCalculator`, `ScenarioPack` を再利用、独立 script 化を回避
- **再現性**: `SweepResult` の deterministic な child_pack_id 生成を継承

### 1.1 役割分担

```
   SDP optimizer (新規 portfolio MILP)
            ↓ produces (active, standby) DER set
   gridflow Orchestrator (既存 pandapower simulator)
            ↓ produces ExperimentResult per timestep
   gridflow BenchmarkHarness (既存 metric calculator)
            ↓ produces SLA tail / cost / OOD gap metrics
   gridflow SweepOrchestrator (既存 sweep)
            ↓ runs 12 conditions × 6 trace types matrix
   results.json (try11 specific aggregation)
```

---

## 2. モジュール構成

```
test/mvp_try11/
├── ideation_record.md                # 完成済み
├── implementation_plan.md            # 本書
├── packs/
│   └── try11_base_pack/              # base ScenarioPack
│       ├── pack.json
│       ├── network.json              # CIGRE LV (try10 流用) + DER aggregator bus
│       ├── der_pool.csv              # DER pool 定義 (id, type, capacity, trigger 曝露)
│       └── triggers.csv              # K=4 トリガー基底 (commute / weather / market / comm)
├── sweep_plans/
│   └── try11_full_sweep.yaml         # 12 条件 × 6 trace の SweepPlan 定義
├── tools/
│   ├── der_pool.py                   # DER pool dataclass + CSV loader
│   ├── trigger_basis.py              # トリガー基底 + DER 曝露ベクトル
│   ├── trace_synthesizer.py          # C1-C6 trace 合成
│   ├── sdp_optimizer.py              # SDP MILP (M1-M6 各 variant)
│   ├── baselines/
│   │   ├── b1_static_overprov.py     # +30% 静的過剰契約
│   │   ├── b2_stochastic_program.py  # SP (PuLP, シナリオ N=200)
│   │   ├── b3_wasserstein_dro.py     # Wasserstein-ball DRO
│   │   ├── b4_markowitz.py           # 相関 portfolio
│   │   ├── b5_financial_causal.py    # 金融 causal portfolio (PC アルゴリズム, causal-learn)
│   │   └── b6_naive_nn.py            # naive NN reactive (PyTorch lightweight)
│   ├── vpp_metrics.py                # SLA tail / cost / OOD gap MetricCalculator
│   └── run_phase1.py                 # SweepOrchestrator entry point
├── results/
│   ├── try11_results.json
│   ├── per_condition_metrics.csv
│   └── plots/                        # SLA-cost Pareto / OOD degradation
├── report.md                          # 論文ドラフト
└── review_record.md                   # Phase 2 査読記録
```

---

## 3. データ構造

### 3.1 DER

```python
@dataclass(frozen=True)
class DER:
    der_id: str
    der_type: str                # 'residential_ev' / 'commercial_fleet' / 'industrial_battery' / 'heat_pump' / 'utility_battery'
    capacity_kw: float           # active power capacity
    contract_cost_active: float  # ¥/month if in active pool
    contract_cost_standby: float # ¥/month if in standby pool
    trigger_exposure: tuple[bool, ...]  # K-dim binary, e.g. (True, False, True, False) for commute=Y, weather=N, market=Y, comm=N
```

### 3.2 トリガー基底

```python
TRIGGER_BASIS_K4 = ('commute', 'weather', 'market', 'comm_fault')
TRIGGER_BASIS_K3 = ('commute', 'weather', 'market')
TRIGGER_BASIS_K2 = ('commute', 'weather')
TRIGGER_BASIS_K5 = TRIGGER_BASIS_K4 + ('regulatory',)  # for OOD test trace C4
```

### 3.3 Trace

```python
@dataclass(frozen=True)
class ChurnTrace:
    timesteps: tuple[float, ...]              # minutes from start
    trigger_events: tuple[tuple[str, float, float], ...]  # (trigger_name, start_t, end_t)
    der_active_status: tuple[tuple[bool, ...], ...]       # [t][j] = j-th DER active at time t
    sla_target_kw: float                       # contracted ancillary level
```

---

## 4. SDP optimizer (新規実装の core)

### 4.1 MILP 定式 (M1 canonical, K=3, strict)

```
変数:
  x_j ∈ {0,1}       j ∈ pool (standby に入れるか)
  (active 集合 A は trace 入力で固定、最適化対象外)

目的:
  min Σ_j c_j^standby x_j

制約:
  (a) trigger-orthogonality:
      ∀k ∈ K: ( Σ_{j∈A} e_{j,k} ≥ 1 ) ⇒ ( Σ_j e_{j,k} x_j = 0 )
        # active 側で k が曝露されている軸では、standby は k 曝露ゼロ
  (b) capacity coverage:
      ∀k: Σ_j (1 - e_{j,k}) cap_j x_j  ≥  B_k
        # k 失効時の補償容量 ≥ 想定 burst B_k
  (c) pool 無重複: x_j = 0 ∀ j ∈ A
```

実装: PuLP + CBC。M3 (soft) は (a) を penalty 項に変換、M3 (tolerant) は overlap ≤ ε に緩和。

### 4.2 variant 切替 (M1-M6)

| variant | 切替点 |
|---|---|
| **M1** strict-MILP-K3 | base config |
| **M2a/b/c** K=2/3/4 | TRIGGER_BASIS 切替 |
| **M3a/b/c** strict / soft / tolerant | 制約 (a) の形式切替 |
| **M4a/b** MILP / greedy | solver 切替 (greedy = O(N log N) heuristic) |
| **M5** MILP + NN 動員 | (a) は MILP、動員時刻は NN 検出器が指示 (B6 と一部共有) |
| **M6** with label noise | DER の trigger_exposure を 5/10/20% 反転して入力 |

---

## 5. baseline 実装 (B1-B6)

| # | 実装方針 | 主要 lib |
|---|---|---|
| **B1** 静的過剰 | active capacity の 1.3 倍を確保するように standby を greedy 選択 | numpy |
| **B2** SP | 過去 trace から N=200 シナリオ生成、PuLP で 2-stage SP | PuLP |
| **B3** Wasserstein DRO | Wasserstein-ball 内最悪ケース、convex 双対化で LP に | PuLP, cvxpy |
| **B4** Markowitz | 過去 trace 相関行列で min variance portfolio (continuous → 上位 K 個 binary 化) | numpy |
| **B5** 金融 causal | causal-learn で PC アルゴリズム → causal DAG → DAG 上で min variance | causal-learn, PuLP |
| **B6** naive NN | LSTM で trace から churn rate 予測、threshold で動員 | PyTorch |

---

## 6. trace synthesizer (C1-C6)

### 6.1 共通フォーマット
- 期間: 30 日 (= train 14 日 + test 16 日)
- 1 timestep = 5 分 → 30 日で 8640 steps
- DER pool: ~200 機器 (residential EV ×80, commercial fleet ×30, industrial battery ×30, heat pump ×30, utility battery ×30)
- 名目契約 SLA: 5 MW / 30秒応答

### 6.2 各 trace の特徴

| trace | 中身 | 期待結果 |
|---|---|---|
| **C1** 単一既知トリガー | commute / weather / market 各々のみ trigger を 1 日 1-2 回発火 | SDP > B1-B4, ≈ B5 |
| **C2** 既知軸過去最大 | train 期 max の 1.5 倍規模の burst を test 期に注入 | SDP の構造的優位が顕在化 |
| **C3** 複数既知同時 | "厳冬朝 + 通勤" など 2 trigger 同時発火 | SDP-strict は infeasible 増、SDP-soft が救う |
| **C4** 基底外新軸 | "regulatory mandate" を train 期不在 / test 期出現 (OOD) | SDP も崩れるが detection 容易性で勝負 |
| **C5** OOD 頻度 | market trigger が train 期稀 / test 期頻発 | SDP の構造保証で robustness 顕在化 |
| **C6** label noise | DER の trigger_exposure を 5/10/20% 反転 | SDP の実用閾値を確定 |

---

## 7. gridflow 統合点

### 7.1 ScenarioPack 拡張

`pack.json` に新規 metadata key を追加:

```json
{
  "metadata": {
    "parameters": [
      ["der_pool_csv", "der_pool.csv"],
      ["trigger_basis_csv", "triggers.csv"],
      ["sla_target_kw", 5000.0],
      ["trace_id", "C1"]
    ],
    "properties": [["mvp_try", "11"]]
  }
}
```

### 7.2 SweepPlan 構成

12 条件 (M1-M6 + B1-B6) × 6 trace (C1-C6) = 72 child experiments を 1 SweepPlan で expand。axes:
- `method`: ChoiceAxis ['M1', 'M2a', ..., 'B6']
- `trace_id`: ChoiceAxis ['C1', 'C2', ..., 'C6']

Aggregator は `vpp_metrics.SLATailAggregator` を新規実装 (mean / 95-percentile / OOD gap)。

### 7.3 MetricCalculator 新規

`tools/vpp_metrics.py`:

```python
class SLATailViolationRatio(MetricCalculator):
    """trace 全期間で aggregate < SLA target となる timestep 比率"""

class TotalContractCost(MetricCalculator):
    """active + standby 月額契約コスト合計"""

class BurstCompensationRate(MetricCalculator):
    """trigger 発火時の standby 補償 / burst 規模"""

class OODGap(MetricCalculator):
    """train 期 SLA - test 期 SLA"""
```

これらは `BUILTIN_METRICS` に register。

### 7.4 Orchestrator の使い方

各 child experiment は:
1. SDP/baseline optimizer が standby DER 集合を出力
2. trace を timestep 順に walk、active+standby DER の aggregate output を計算
3. pandapower で aggregate output を VPP 接続バスに inject、PF 実行で voltage / loss を取得
4. ExperimentResult として保存

→ pandapower 部分は gridflow が standard で扱う。SDP 固有部分は **standby 選択** のみ。

---

## 8. 実装順序 (milestone)

| ms | 内容 | 完了基準 |
|---|---|---|
| **MS-1** | DER pool / trigger basis / trace synthesizer | C1 trace を 1 日分生成、可視化で正常確認 |
| **MS-2** | SDP M1 (strict-MILP-K3) optimizer | 5-DER pool で feasible 解を出す unit test 通過 |
| **MS-3** | gridflow 統合 (ScenarioPack 拡張 + SLATailViolationRatio) | C1 trace + M1 で 1 child experiment が end-to-end 完走 |
| **MS-4** | SDP M2-M6 variant 実装 | 各 variant が unit test 通過 |
| **MS-5** | baseline B1-B6 実装 | 各 baseline が C1 trace で動作 |
| **MS-6** | C2-C6 trace 完成 | 全 trace が visualization で意図通り |
| **MS-7** | 12×6 sweep 全件実行 | results.json + per_condition_metrics.csv 出力 |
| **MS-8** | report.md (論文ドラフト) | §0-§11 完成 |
| **MS-9** | review_record.md (Phase 2 査読) | 査読記録完成 |

進捗は逐次 commit + push。失敗時は MS-N 単位で問題切り出し。

---

## 9. 成功基準 (定量)

### 9.1 主要主張の検証

| 主張 | 成功条件 |
|---|---|
| M1 が C1, C2, C5 で B1-B6 全てに **明確に優位** | SLA違反率が SDP < min(baselines) で statistical significance |
| M3 (soft) が C3 で M1 (strict) より優位 | infeasibility rate が strict > soft |
| M5 が NN を動員に使い設計に使わないことで M1 と同等 SLA | M5.SLA ≈ M1.SLA、M6 の label noise 5-10% で M1 が劣化しても M5 が安定 |
| M6 で label noise 20% まで M1 > B1-B4 | robustness band が他手法より広い |

### 9.2 反証可能性

| 反証 | 対応 |
|---|---|
| C4 で SDP が崩れる | 想定通り。崩壊検出シグナル (label-unexplained churn) を可視化、NN の silent failure と対比 |
| 計算量 | M4 greedy が MILP に近い品質を保つことで scalability を主張 |

---

## 10. 期間と着手

CLAUDE.md §0.1 一撃適用: 期間は事前 cap せず、必要なだけ投資。milestone を順次達成、各 MS ごと commit + push で透明性を担保。

直近着手: **MS-1 (DER pool / trigger basis / trace synthesizer)** から。
