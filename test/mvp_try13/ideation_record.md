# try13 — Phase 0.5 Ideation Record

実施: 2026-04-30
シナリオ: VPP の補助サービス契約 — 機器流出入 churn ロバスト性 (try11 → try12 → try13 継続)
立ち上げ理由: try12 self-review (review_record.md §6) で確定した残課題:
- ❌ 1 feeder (kerber_landnetz) でしか clean win なし
- ❌ M9 vs B1-B6 の multi-method 比較未実施
- ❌ ACN 1 site / 1 month のみ
- ❌ Grid 制約の問題 (kerber_dorf V_disp 100%) を M9 単独では解消不能 → M9-grid 必要

---

## 0. 起点 — try11 / try12 が確立したもの

| try | 貢献 | 残った問題 |
|---|---|---|
| **try11** | Trigger-orthogonal MILP (M1)、grid-aware extension (M7)、ACN per-EV pipeline、Bayes-corrected Theorem 1 | N-2 selection bias 露呈 |
| **try12** | Bayes-Robust constraint (M9)、Theorem 2 (prior-independent bound)、kerber_landnetz θ=0.01 で SLA 71% → 0% | Single feeder clean win、M9-grid 未統合、B1-B6 比較欠落、ACN 1 site / 1 month |

try13 はこれらを **構造的に解決**:

1. **M9-grid** (技術): M9 (Bayes-Robust) + M7 (DistFlow grid-aware) を **単一 MILP に統合**、kerber_dorf の V_disp 100% 問題と kerber_landnetz の SLA 0% 達成を **同時に** 実現
2. **Multi-method comparison breadth** (実証): M1, M7, M9, M9-grid, B1 (静的+30%), B4 (Markowitz), B5 (簡易 causal) の 7 方法を同 trace 上で比較
3. **Multi-month ACN** (実証): 2019-01 に加え 02 / 03 を追加取得、季節間 variance を CI で計測
4. **Multi-site ACN** (実証): caltech + jpl + office001 の 3 site で workplace pattern variation を計測

---

## 1. 課題深掘り (S0-S8)

### S0: 何の問題?
try12 の M9 は Bayes-Robust だが grid 制約を持たず、kerber_dorf で V_disp 100% は解消できない。M7 (grid-aware) は grid 制約を持つが Bayes-Robust ではないため selection bias を持つ。**両者を統合した MILP が必要**。

### S1: 統合の難しさ?
- M7: per-bus voltage 制約 + per-line loading 制約 (DistFlow 線形化)
- M9: per-axis Bayes posterior expected-loss 制約
- 両者は **constraint 種別が直交** (= 一方が他方を block しない)
- 従って M9-grid = M7 の constraints + M9 の expected-loss constraint を MILP に同時に追加

### S2: 既存手法?
DER siting (M7) と Bayes-Robust portfolio (M9) を結合した先行研究は確認できない。本研究 try13 が initial offer。

### S3: 物理的に何が起きているか?
- M7: voltage / line 制約により feeder topology を尊重する DER 配置を picks
- M9: Bayes posterior 制約により label uncertainty 下の真の expected loss を制御
- 両者統合: feeder safety AND statistical robustness の **両立**

### S4: 他分野で同型問題?
- Bayesian DR-OPF (Distributionally Robust OPF, Cao et al. 2020): 連続 portfolio の Bayes-aware OPF
- 本研究 = discrete (binary) MILP 版

### S5: 数学的構造?
M9-grid MILP:
```
min Σ c_j x_j
s.t. orth (M1):    ∀k ∈ E(A): Σ_{j: tilde_e_jk=1} x_j = 0
     cap (M1):    ∀k:        Σ_{j: tilde_e_jk=0} cap_j x_j ≥ B_k
     bayes (M9):  ∀k ∈ E(A): Σ_j π_jk cap_j x_j ≤ θ_k
     v_max (M7):  ∀i:        V_baseline_i + active_term_i + Σ_j cap_j V_imp[i,j] x_j ≤ V_max
     l_max (M7):  ∀k:        L_baseline_k + active_term_k + Σ_j cap_j L_imp[k,j] x_j ≤ L_max
```

5 constraint family、binary x_j ∈ {0,1}、PuLP + CBC で解ける。

### S6: 実装可能性?
- 既存実装 (try11 sdp_grid_aware.py + try12 sdp_bayes_robust.py) を **重ね合わせる** 形で実装可
- Constraint 数: M1 の K + N_bus + N_line + K + N_bus + N_line ≈ M7 + K (M9 の追加 K constraints)
- 計算量増加は constant 倍、N=200 で sub-second 維持

### S7: 提案手法?
**M9-grid: Bayes-Robust Trigger-Orthogonal Grid-Aware Portfolio**

3 つの貢献を統合:
- (a) Trigger orthogonality (try11 M1)
- (b) DistFlow grid awareness (try11 M7)
- (c) Bayes posterior expected-loss bound (try12 M9)

### S8: 検証戦略?
1. M9-grid MILP 実装 (`m9_grid_tools/sdp_full.py`)
2. 7-method synthetic sweep (M1, M7, M9, **M9-grid**, B1, B4, B5)
3. Multi-month × Multi-site ACN sweep
4. Cost-loss-grid trade-off Pareto

---

## 2. Multi-method comparison のための baseline 拡張

try11 / try12 は M1 / M7 / M9 のみを真剣に比較。try13 では:

- **B1**: 静的 +30% over-provision (try11 既実装)
- **B4**: Markowitz portfolio (try11 既実装)
- **B5**: 簡易 causal portfolio (try11 既実装、CPCM 簡易版)
- **M1, M7, M9, M9-grid**: 内部メソッド

→ 7 methods を **同 trace 上**で比較し、統計有意な順位付けを bootstrap CI で確立。

---

## 3. Multi-data empirical breadth

### 3.1 ACN 多月

`tools/fetch_acn.py` (try11 既実装) で 2019-01 (取得済) に加えて:
- 2019-02 (Feb): 4 weeks
- 2019-03 (Mar): 4 weeks
- 計 12 weeks of caltech data

### 3.2 ACN 多 site

ACN-Data の 3 サイト:
- caltech: 50 stations (try11 取得済)
- jpl: NASA Jet Propulsion Lab、別 workplace pattern
- office001: anonymous office、別 workplace pattern

3 サイトを取得し、**site 間の variance** が controller 性能に影響するかを計測。

### 3.3 Sweep 規模

- multi-method (7) × multi-feeder (3) × multi-month (3) × multi-site (3) × multi-pairing (3) = **567 cells** (理論上)
- 実用域: 5 method × 3 feeder × 3 month × 3 site × 2 seed = **270 cells**

---

## 4. 期待される結果と Plan B

### 期待 (= best case)
- M9-grid が kerber_dorf の V_disp 100% を **0%** に解消
- M9-grid が kerber_landnetz の SLA を **CI 完全分離で 0%** に
- 7-method 比較で **M9-grid が統計有意に Pareto-dominant** (cost-SLA-grid 3 軸で他全て劣位)
- 3 site × 3 month の variance を CI で計測 (= reviewer の "sample size 1" 懸念解消)

### Plan B (= 部分的成功)
- M9-grid が cigre_lv で infeasible (= θ_k で feasibility 域が縮む)
- → M9-grid-soft (slack-penalised expected-loss) を導入

### Plan C (= 全敗)
- 7-method 比較で M9-grid が他に negligible 差
- → "honest negative finding paper" として workshop 級で publish

---

## 5. 既存手法との理論対比 (final form)

| 手法 | trigger 直交 | grid 制約 | Bayes posterior | 期待 worst-case 保証 | コスト |
|---|---|---|---|---|---|
| B1 静的 +30% | × | × | × | なし | ¥6,000 |
| B4 Markowitz | × | × | × | なし | ¥6,000 |
| B5 簡易 causal | × | × | × | なし (correlation 仮定) | ¥5,823 |
| M1 (try11) | ✅ | × | × | $\max_k \sum \pi cap$ (prior 依存) | ¥3,500 |
| M7 (try11) | ✅ | ✅ | × | 同上 + grid feasibility | ¥3,500-8,700 |
| M9 (try12) | ✅ | × | ✅ | $\max_k \theta_k$ (prior-independent) | ¥3,532+ |
| **M9-grid (try13)** | ✅ | ✅ | ✅ | $\max_k \theta_k$ + grid feasibility | TBD |

→ M9-grid は **3 軸 (orth + grid + Bayes) すべて** を満たす **唯一** のメソッド。これが try13 の central novelty claim。

---

## 6. Phase 1 への引継

詳細は `implementation_plan.md` 参照。要点:
- MS-1: M9-grid MILP 実装
- MS-2: ACN 多月 + 多 site 取得
- MS-3: 7-method synthetic sweep
- MS-4: 7-method ACN multi-data sweep
- MS-5: report + self-review
