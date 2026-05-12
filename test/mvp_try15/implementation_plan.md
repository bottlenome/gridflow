# try15 — Implementation Plan (Phase 1)

実施開始: 2026-04-30 後段
ideation: `ideation_record.md` (Phase 0.5、policy §2.5.2 Rule 1-9 v2 完了)
採用案: **M10 = Time-Constant Diversified VPP Pool** (response time constant τ_j 並列)

---

## 0. 設計の幹

M10 の核は「DER の応答時定数 τ_j を陽にモデル化し、active drop を **時間方向に分散** する」こと。`τ_j` は DER type に紐づく **物理的時間スケール**:

| DER type | τ_drop (s) | 物理的根拠 |
|---|---|---|
| utility_battery | 5 | 制御命令で即時応答 (BMS) |
| industrial_battery | 30 | 産業設備の operation override |
| commercial_fleet | 180 (3 min) | フリートマネージャーの judgment latency |
| residential_ev | 300 (5 min) | 所有者が出発を決める判断時間 |
| heat_pump | 60 | 気象センサーの応答 + thermostat lag |

trigger 発火 → 曝露 DER は **t_event + τ_j** (ジッタなし simple model) で active 状態を失う。τ_j が type で散っているため、aggregate output は **rectangular drop でなく階段状 decay** を示す。

## 1. M10 選定 algorithm (MILP-free)

```
Input: pool, active_ids, burst, K basis, target SLA tail
Heuristic: greedy with τ-diversification
  1. 候補 = pool \ active で trigger-orthogonal な DER 集合
  2. τ histogram を 5 bin (= 5 type) に分割
  3. 各 bin から少なくとも 1 機選定するよう制約
  4. capacity coverage Σ cap ≥ B_k を満たすよう greedy 追加
  5. 結果として τ 分散 (= 標準偏差) が最大化される
Output: standby_ids
```

これは **MILP 不要、O(N log N) sort のみ**。

## 2. Theorem 4 (M10 の analytical SLA tail bound)

active pool 集計 capacity に共通 trigger が発火、各 DER の drop delay が τ_j のとき、aggregate capacity の時間関数 A(t):

$$
A(t) = \sum_{j \in \text{active, exposed}} \mathrm{cap}_j \cdot \mathbf{1}[t < \tau_j] + \sum_{j \in \text{active, not exposed}} \mathrm{cap}_j
$$

τ_j が **distinct** な場合、A(t) は階段状で **最小値 = max_t A(t) over burst window**。一様 τ (try11 等価) の場合、A(t) は cliff drop で min A = nonexposed cap のみ。

**主張**: τ-diversified pool の SLA tail (= P(A < target)) は uniform τ より低い、bound は τ 分布の percentile 関数で書ける。

## 3. Milestone

| MS | 内容 | 完了基準 |
|---|---|---|
| MS-1 | DER pool に τ_drop_s 拡張、try11 pool との **後方互換** layer | tau_pool.make_default_pool が τ 付き、try11 互換 caller は無視可能 |
| MS-2 | τ-aware simulator: trigger event を τ_j で smear | 同 trace で M1 (try11) と M10 が **異なる aggregate trajectory** を返す |
| MS-3 | M10 selection algorithm + smoke test | M10 が pool 内で τ 分散 ≥ 既存平均 + 1σ を達成 |
| MS-4 | M1 (try11) vs M10 比較 sweep | 同 trace 上で SLA tail を bootstrap CI で比較 |
| MS-5 | Theorem 4 解析的 bound + 実測値の整合 | 解析値 vs 実測 SLA tail の R² ≥ 0.8 |
| MS-6 | report.md + Phase 2 self-review | Q1/Q2 + try15 published readiness |

---

## 4. 実装方針

- 新規モジュールは `test/mvp_try15/tools15/` 配下のみ
- try11 から `make_default_pool`, `feeder_active_pool`, `simulate_vpp` 等を import で再利用
- ただし τ-aware simulator は新規実装 (try11 simulator は τ を持たない)
- データは try11 の ACN fixture を再利用 (= ACN session の workplace pattern を trigger event source に)

---

## 5. 完了 DoD

- ✅ M10 が同 ACN trace 上で M1 と **異なる** SLA tail を出す (= simulator 差異)
- ✅ τ-diversification が SLA tail に効く方向に作用 (= bootstrap CI で確認)
- ✅ Theorem 4 の解析値が実測 ±20% 以内
- ✅ §3.1 適合 (gridflow framework を contribution として claim しない)
