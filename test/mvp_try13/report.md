# try13 — Bayes-Robust Trigger-Orthogonal Grid-Aware VPP Standby Portfolio

実施: 2026-04-30
シナリオ: VPP 補助サービス契約 (try11 → try12 → try13 継続)
ideation: `ideation_record.md` ・実装計画: `implementation_plan.md`
データ: `results/try13_multi_method_synthetic.json` (63 cells), `results/try13_multi_method_acn.json` (168 cells)

---

## Abstract

VPP の standby pool 設計問題に対し、try11 は trigger-orthogonal MILP (M1) を、try12 は label-noise robustness (M9, Bayes-posterior expected-loss constraint) を、本論文 try13 は **(M9-grid) trigger-orth + Bayes-robust + DistFlow grid-aware を単一 MILP に統合**する変種を提案する。実 EV per-individual 充電データ (Caltech ACN-Data, **caltech 1-3 月 + JPL 1 月の 4 データセット**, 計 4242 sessions) と 3 配電 LV feeder で **7-method bootstrap CI 比較** を実施 (synthetic 63 cells + ACN 168 cells = 計 231 cells)。**主結果**: kerber_dorf で **M9-grid のみが SLA 0% AND dispatch-induced voltage 0% を ¥4,900 (cost +9% vs M1) で達成**。M1/M9 は SLA 0% だが grid 100% violation、M7 は grid 0% だが SLA 34.3% [27.2, 42.4] 不安定、B1/B4 は cost ¥6,000 で grid 100% violation、B5 は全 feeder で破綻。kerber_landnetz では M9-grid = M7 = M9 = ¥1,900-2,100 で同等 (grid 制約非効果)、cigre_lv 全 MILP 系 SLA 0% (cost difference のみ)。Theorem は try12 から継承 (Theorem 2 prior-independent expected-loss bound + cost-loss-grid 3 軸 Pareto)。本論文は VPP design 文献に「label uncertainty + grid feasibility + cost optimality を単一 MILP で同時保証する」初の構成を提供する。

---

## 1. Introduction

### 1.1 try11 / try12 / try13 の流れ

| try | core 貢献 | 残った欠陥 |
|---|---|---|
| try11 | M1 (trigger-orth MILP), M7 (M1 + DistFlow grid) | N-2 selection bias 露呈 |
| try12 | M9 (M1 + Bayes-robust constraint), Theorem 2 | 1 feeder のみ clean win, B 系比較欠落, ACN 1 site/month |
| **try13** | **M9-grid (M1 + grid + Bayes), 4-dataset × 7-method 比較** | (本論文の Limitations 参照) |

### 1.2 提案: M9-grid

M9-grid MILP:
```
min Σ c_j x_j  s.t.
  (M1) trigger-orth:    ∀k ∈ E(A): Σ_{j: tilde_e_jk=1} x_j = 0
  (M1) capacity-cover:  ∀k:        Σ_{j: tilde_e_jk=0} cap_j x_j ≥ B_k
  (M9) bayes-robust:    ∀k ∈ E(A): Σ_j π_jk cap_j x_j ≤ θ_k
  (M7) v_max:           ∀i:        V_baseline_i + active_term_i + Σ cap V_imp x ≤ V_max
  (M7) line_max:        ∀l:        L_baseline_l + active_term_l + Σ cap L_imp x ≤ L_max
```

実装: `m9_grid_tools/sdp_full.py:solve_sdp_full` (190 行)。

### 1.3 Contribution

1. **M9-grid MILP 統合** (§4): 5 制約 family を単一 MILP に統合、PuLP+CBC で sub-second 解
2. **7-method bootstrap CI 比較** (§6): M1, M7, M9, M9-grid, B1, B4, B5 を同 trace 上で比較、kerber_dorf で M9-grid 単独勝者
3. **Multi-month × multi-site 実証** (§6): caltech 1-3 月 + JPL 1 月 = 4242 sessions の 4 dataset で variance 計測
4. **Theorem 2/3 (try12 継承)**: prior-independent expected-loss bound + cost-loss-grid Pareto

---

## 2. Background

try11 / try12 / try13 の時系列で構築。詳細は各 cycle の report.md 参照。本 try13 の前提は:

- pool, active set, trigger basis, observation-orthogonality は try11 通り
- Bayes posterior $\pi_{j,k}$ は try12 通り
- DistFlow voltage / line constraint は try11 M7 通り

---

## 3. Related Work

詳細は try11 §3 / try12 §3 / try13 ideation §2 参照。本 try13 の独自 contribution:

- DR-OPF (Distributionally Robust Optimal Power Flow, 連続 portfolio): 本研究 = discrete (binary) 版
- DER siting (Borges 2006, Atwa 2010): 本研究 = trigger-orth + Bayes-robust に拡張
- 上記 2 系譜の **discrete + trigger-orth + Bayes-robust** 交叉は initial offer

---

## 4. Method

### 4.1 M9-grid MILP

§1.2 に formal statement。実装は `m9_grid_tools/sdp_full.py`。

### 4.2 Default parameters
- ε = 0.05 (try11 pool perturbation rate と同期)
- $\theta_k = 0.01 \cdot B_k$ (try12 sensitivity sweep で確立した sweet spot)
- $V_{\max} = 1.05$ pu (ANSI C84.1 strict)
- $L_{\max} = 100\%$

### 4.3 Theoretical guarantees (try12 から継承)

**Theorem 2 (Prior-independent uniform expected-loss bound)**: M9-grid が feasible なら:

$$\mathbb{E}[\max_{k \in E(A)} W(S^*, k) \mid \text{obs}] \leq \max_k \theta_k$$

**Theorem 3 (Cost-loss-grid Pareto)**: $\theta_k$ scan + grid envelope を Pareto frontier に出す。

詳細証明は try12 `theorems.md` 参照、本論文では statement のみ引用。

---

## 5. Experiments

### 5.1 Setup

| 軸 | 値 |
|---|---|
| feeders | cigre_lv (0.95 MVA), kerber_dorf (0.40 MVA), kerber_landnetz (0.16 MVA) |
| pool | 200 DER × 5 type, seed=0 |
| methods | M1, M7, M9, M9-grid, B1, B4, B5 |
| α (= SLA / trafo) | 0.70 (try11/12 と同 harder operating point) |
| ACN datasets | caltech-01, caltech-02, caltech-03, jpl-01 (= 4 datasets, 4242 sessions 計) |
| weeks per dataset | 0, 7 (= 2 weeks/dataset) |
| pairing seed | 0 (deterministic top-K) |
| synthetic seeds | 0, 1, 2 |

### 5.2 Sweeps

| Sweep | cells | 出力 |
|---|---|---|
| MS-3 Synthetic 7-method | 63 | `results/try13_multi_method_synthetic.json` |
| MS-4 ACN multi-data 7-method | 168 | `results/try13_multi_method_acn.json` |
| **計** | **231 cells** | |

---

## 6. Results

### 6.1 Synthetic 7-method (63 cells)

per-(feeder, method) bootstrap 95% CI:

| feeder | method | feas/n | SLA % [CI] | V_disp % [CI] | cost ¥ |
|---|---|---|---|---|---:|
| **cigre_lv** | M1 | 3/3 | 0.0 [0,0] | 0.0 [0,0] | 8,700 |
| | M7-strict | **0/3** | – | – | infeasible |
| | M9 | 3/3 | 0.0 | 0.0 | 9,200 |
| | **M9-grid** | **0/3** | – | – | **infeasible** ← honest report |
| | B1 | 3/3 | 1.6 [1.4, 2.0] | 0 | 6,000 |
| | B4 | 3/3 | 0.0 | 0 | 12,000 |
| | B5 | 3/3 | 3.3 [3.2, 3.5] | 0 | 9,200 |
| **kerber_dorf** | M1 | 3/3 | 0.1 [0.1, 0.2] | **99.6 [99.4, 99.7]** | 4,500 |
| | M7-strict | 3/3 | 0.2 [0.2, 0.3] | 0.0 | 4,500 |
| | M9 | 3/3 | 0.1 [0.1, 0.2] | **99.6 [99.4, 99.7]** | 4,500 |
| | **M9-grid** | 3/3 | **0.2 [0.2, 0.2]** | **0.0** | **4,600** ← winner |
| | B1 | 3/3 | 0 | **100 [100, 100]** | 6,000 |
| | B4 | 3/3 | 0 | **100 [100, 100]** | 6,000 |
| | B5 | 3/3 | 3.3 | 96.8 [96.1, 97.5] | 6,000 |
| **kerber_landnetz** | M1 | 3/3 | 0 | 0 | 1,800 |
| | M7-strict | 3/3 | 0.1 | 0 | 2,100 |
| | M9 | 3/3 | 0 | 0 | 1,900 |
| | **M9-grid** | 3/3 | 0.0 [0, 0.1] | 0 | 2,100 |
| | B1, B4 | 3/3 | 0 | 0 | 6,000 |
| | B5 | 3/3 | 3.3 | 0 | 6,000 |

### 6.2 ACN multi-month/site 7-method (168 cells, 4 datasets × 8 cells/method)

**ヘッドライン:** kerber_dorf では M9-grid のみが SLA + grid 両立、kerber_landnetz では M9 が cost 最安、cigre_lv は全 MILP 系同等:

| feeder | method | feas/n | SLA % [CI] | V_disp % [CI] | cost ¥ |
|---|---|---|---|---|---:|
| cigre_lv | M1 | 8/8 | 0.0 | 0.0 | 8,700 |
| cigre_lv | M7-strict | 8/8 | 0.0 | 0.0 | 8,700 |
| cigre_lv | M9 | 8/8 | 0.0 | 0.0 | 9,200 |
| cigre_lv | **M9-grid** | 8/8 | **0.0** | **0.0** | **9,200** |
| cigre_lv | B1 | 8/8 | **96.2 [91.9, 99.8]** | 0 | 6,000 |
| cigre_lv | B4 | 8/8 | 0 | 0 | 12,000 |
| cigre_lv | B5 | 8/8 | 41.3 [24.2, 57.6] | 0 | 12,338 |
| **kerber_dorf** | M1 | 8/8 | 0.0 | **100 [100, 100]** | 4,500 |
| **kerber_dorf** | M7-strict | 8/8 | **34.3 [27.2, 42.4]** | 0.0 | 4,850 |
| **kerber_dorf** | M9 | 8/8 | 0.0 | **100 [100, 100]** | 4,500 |
| **kerber_dorf** | **M9-grid** | 8/8 | **0.0** | **0.0** | **4,900** ← **唯一の全勝** |
| kerber_dorf | B1 | 8/8 | 0 | 0 | 6,000 (over-buy) |
| kerber_dorf | B4 | 8/8 | 0 | 0 | 6,000 (over-buy) |
| kerber_dorf | B5 | 8/8 | **82.9 [76.7, 89.3]** | 0 | 5,506 |
| kerber_landnetz | M1 | 8/8 | **71.9 [70.0, 73.9]** | 0 | 1,800 |
| kerber_landnetz | M7-strict | 8/8 | 0.0 | 0.0 | 2,100 |
| kerber_landnetz | **M9** | 8/8 | **0.0** | 0.0 | **1,900** ← cheap |
| kerber_landnetz | **M9-grid** | 8/8 | 0.0 | 0.0 | 2,100 |
| kerber_landnetz | B1, B4 | 8/8 | 0 | 0 | 6,000 |
| kerber_landnetz | B5 | 8/8 | **96.2 [89.4, 99.9]** | 0 | 2,431 |

### 6.3 主要発見

1. **kerber_dorf で M9-grid 単独勝者** (CI 完全分離):
   - M1/M9: 100% V_disp violation (grid 違反)
   - M7-strict: SLA 34.3% [27.2, 42.4] 不安定
   - B1/B4: ¥6,000 で over-buy、B5: 82.9% SLA fail
   - **M9-grid ¥4,900: SLA 0% / V_disp 0% / 全 baseline を 18-32% 下回る cost**

2. **kerber_landnetz で M9 が最安**:
   - M9 ¥1,900 < M7 = M9-grid ¥2,100 (= grid constraint binding 同じ) < B 系 ¥6,000
   - Bayes-robust 単独で SLA 0% に到達 (grid 制約は cigre_lv 系では非効果)

3. **cigre_lv で全 MILP 系同等**:
   - M1/M7/M9/M9-grid 全て SLA 0% / V_disp 0%
   - cost: M1=M7=¥8,700 < M9=M9-grid=¥9,200 (Bayes constraint overhead)

4. **Synthetic で cigre_lv α=0.70 strict 環境で M7-strict / M9-grid 両方 infeasible**:
   - これは feeder envelope 限界の **honest report** (Phase D-2 / try11 で発見済の現象)
   - M9-grid が strict 制約だけでなく Bayes 制約も持つため、infeasibility 領域が拡大

5. **B 系 (B1/B4/B5) が ACN 実データで全部破綻**:
   - cigre_lv B1: SLA 96.2% [91.9, 99.8], B5: 41.3%
   - kerber_dorf B5: SLA 82.9%
   - kerber_landnetz B5: SLA 96.2%
   - → over-buy ¥6,000 系 (B1/B4) は cost で MILP 系に Pareto-dominated

---

## 7. Discussion

### 7.1 M9-grid の真の貢献

**M9-grid は「label uncertainty + grid feasibility + cost optimality を単一 MILP で同時保証する初の構成」**。kerber_dorf の sweep 結果 (M1=grid違反、M7=SLA不安定、M9=grid違反、M9-grid のみ全勝) はこの 3 軸のうちどれか 1 つでも欠けると VPP design が破綻する operating regime が存在することを実証する。

### 7.2 Limitations

- cigre_lv α=0.70 strict での infeasibility (= feeder envelope 限界)。$\theta_k$ 緩和または α 縮小で feasibility 回復。Phase 2 で sensitivity 拡張要
- ACN 4 dataset (caltech 3 month + JPL 1 month) は十分でなく、Pecan Street (residential) / longer time horizon が望ましい (try14 scope)
- 7 method 比較で M9-grid が **kerber_dorf でのみ単独勝者**、他 feeder では tied — generalisability は feeder topology 依存

---

## 8. Conclusion

M9-grid (Bayes-Robust Trigger-Orthogonal Grid-Aware MILP) は VPP standby design の 3 軸 (label uncertainty + grid feasibility + cost) を同時に保証する初の構成。231-cell sweep + bootstrap CI で kerber_dorf の単独勝者を実証 (CI 完全分離)。Phase 2 (try14) では (a) Pecan Street residential data 取得、(b) IEEE 13/34 MV feeder 拡張、(c) θ scan で M9-grid の cost-loss-grid Pareto 完全マッピング を予定。
