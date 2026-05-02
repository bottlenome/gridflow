# try12 — Implementation Plan (Phase 1)

実施開始: 2026-04-30
ideation: `ideation_record.md` (Phase 0.5 完了)
立ち上げ理由: try11 N-2 (MILP selection bias) を **設計で解決する** 手法 M9 (Bayes-Robust CTOP) を提案・検証

---

## 0. 設計原則 (CLAUDE.md §0 適合)

- **§0.1 妥協なき理想設計**: M9 の Bayes-aware MILP は posterior $\pi_{j,k}$ を陽に入力する形で書く。実装の都合で「近似」を入れない
- **§0.5.2 自分で判断する**: 技術判断 (MILP 定式化、constraint 形式、threshold $\theta$ の設計) は実装者で確定。product judgment (= "PWRS を狙うか別 venue か") のみ PO 判断
- **§3.1 (mvp_review_policy)**: gridflow 自体を contribution として主張しない

---

## 1. Milestone 構成

| MS | 内容 | 完了基準 | 想定工数 |
|---|---|---|---|
| **MS-1** | M9 (Bayes-Robust SDP) MILP の実装 + smoke test | `tools/sdp_bayes_robust.py` で M9 が小規模 case (N=5, K=3) で feasible 解を返す。期待損失 ≤ θ が constraint として効いていることを smoke test で確認 | 半日 |
| **MS-2** | Theorem 2 の証明 + theorems.md / report §4.7 への組込 | M9 の expected loss bound が **prior-independent** に立つ証明完了 | 半日 |
| **MS-3** | M1 vs M9 の synthetic sweep (F-M2 360 cells) | per-method 95% CI で M9 が M1 を **statistically significant に勝つ** か実測 | 1 日 |
| **MS-4** | M1 vs M9 の real ACN sweep (144 cells, multi-week × multi-pairing) | 同上で multi-week CI 取得、M9 が SLA 違反を低減するか実測 | 1 日 |
| **MS-5** | Theorem 2 の sensitivity analysis (prior misspec, $\theta$ scan, $\varepsilon$ scan) | prior 誤差 ±20% / θ ∈ [0.01, 0.20] / ε ∈ [0.05, 0.20] で M9 の robustness を実測 | 1 日 |
| **MS-6** | report.md 全章ドラフト | Abstract / §1-9 / 図 / Limitations 完成、§3.1 適合確認 (gridflow contribution claim なし) | 1 日 |
| **MS-7** | Phase 2 review (review_record.md) + 修正 | 仮想査読者 review pass → 指摘対応 | 半日 |

**合計**: 5-6 日 (CLAUDE.md §0 の妥協なし設計 + 統計的有意性確立を含む)

---

## 2. MS-1 詳細: M9 MILP の実装

### 2.1 仕様

`tools/sdp_bayes_robust.py`:

```python
@dataclass(frozen=True)
class BayesRobustSDPSolution:
    standby_ids: tuple[str, ...]
    objective_cost: float
    expected_loss_per_axis: tuple[tuple[str, float], ...]  # (axis, μ_k = Σ π_jk cap_j)
    feasible: bool
    mode: str
    trigger_basis: tuple[str, ...]
    overlap_per_trigger: tuple[tuple[str, int], ...]
    coverage_per_trigger: tuple[tuple[str, float], ...]


def solve_sdp_bayes_robust(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    epsilon: float = 0.05,
    prior_by_type_axis: dict[tuple[str, str], float] | None = None,
    expected_loss_threshold_kw: dict[str, float] | None = None,
    enforce_orthogonality: bool = True,
    mode: str = "M9-bayes-robust",
) -> BayesRobustSDPSolution:
    """
    M9: Bayes-Robust trigger-orthogonal CTOP.

    Adds a per-axis expected-loss constraint to the M1 MILP:
        ∀ k ∈ E(A): Σ_j π_{j,k} cap_j x_j ≤ θ_k

    where π_{j,k} = ε p_{τ(j),k} / (ε p + (1-ε)(1-p)) is the Bayes
    posterior of true exposure given observed e_jk = 0.
    """
    ...
```

### 2.2 prior_by_type_axis のデフォルト

`make_default_pool` の DEFAULT_EXPOSURE_K4 を ground truth として、5% per-axis flip 後の prior を計算:

```python
DEFAULT_PRIOR = {
    ('residential_ev', 'commute'): 0.95,    # default 1, 5% flip
    ('residential_ev', 'weather'): 0.05,
    ('residential_ev', 'market'): 0.05,
    ('commercial_fleet', 'commute'): 0.05,
    ('commercial_fleet', 'weather'): 0.05,
    ('commercial_fleet', 'market'): 0.05,
    ('industrial_battery', 'commute'): 0.05,
    ('industrial_battery', 'weather'): 0.05,
    ('industrial_battery', 'market'): 0.95,
    ('heat_pump', 'commute'): 0.05,
    ('heat_pump', 'weather'): 0.95,
    ('heat_pump', 'market'): 0.05,
    ('utility_battery', 'commute'): 0.05,
    ('utility_battery', 'weather'): 0.05,
    ('utility_battery', 'market'): 0.05,
}
```

### 2.3 Smoke test

`tools/_msT12_1_smoke_test.py`:
- 小規模 pool (N=15, K=3) で M9 を solve
- 期待: M9 が cost cheaper but **真の expected loss > θ** な解を出さないことを確認
- 同 pool で M1 と比較し、M9 が strictly different (Bayes posterior 高い outlier を picks しない) ことを確認

### 2.4 完了基準

- ✅ `solve_sdp_bayes_robust` が PuLP + CBC で sub-second 解
- ✅ 全 axis で `Σ π_jk cap_j x_j ≤ θ_k` 制約が active
- ✅ Smoke test pass (5 観点)
- ✅ ruff / mypy strict / pytest 全 green

---

## 3. MS-2 詳細: Theorem 2 (M9 の保証) 確立

### 3.1 主張

**Theorem 2 (M9 の prior-independent expected loss bound)**:
M9 が feasible なら、選定 standby $S^*$ について:

$$
\mathbb{E}\left[\max_{k \in E(A)} W(S^*, k) \;\Big|\; \tilde{e}_{j,k}=0 \;\forall j \in S^*, k \in E(A)\right] \leq \max_{k \in E(A)} \theta_k
$$

これは **prior $p$ にも $\varepsilon$ にも依存しない uniform bound** (= try11 Theorem 1 の prior 依存性を解決)。

### 3.2 証明スケッチ

M9 の制約: $\forall k: \sum_j \pi_{j,k} \mathrm{cap}_j x_j \leq \theta_k$

選定 $S^* = \{j : x_j^* = 1\}$ について、$\sum_{j \in S^*} \pi_{j,k} \mathrm{cap}_j \leq \theta_k$。

期待 worst-case loss:

$$
\mathbb{E}[W(S^*, k) \mid \text{obs}] = \sum_{j \in S^*} \mathrm{cap}_j \cdot \pi_{j,k} \leq \theta_k
$$

$\max_k$ をとっても各 $k$ で $\leq \theta_k$、union で $\leq \max_k \theta_k$ $\Box$

### 3.3 try11 Theorem 1 との比較

| 項目 | try11 Theorem 1 | try12 Theorem 2 |
|---|---|---|
| Bound 形式 | $\max_k \sum \mathrm{cap}_j \pi_{j,k}$ | $\max_k \theta_k$ (定数) |
| Prior 依存 | あり (per-(type, axis) で大きく異なる) | **なし** (uniform) |
| MILP の selection bias | exploit される | **構造的に防止** |
| 設計者の制御 | indirect (ε のみ) | **direct (θ で直接設計)** |

### 3.4 完了基準

- ✅ `theorems.md` に Theorem 2 を追加
- ✅ 証明完備
- ✅ `report.md §4.7` に sync

---

## 4. MS-3 詳細: M1 vs M9 synthetic sweep

### 4.1 sweep 設計

`tools/run_phase1_try12.py`:
- methods: M1 (try11 import), M9 (try12 new)
- feeders: cigre_lv, kerber_dorf, kerber_landnetz
- traces: C1-C8 (try11 import)
- seeds: 0, 1, 2
- = 2 × 3 × 8 × 3 = **144 cells**

### 4.2 評価指標

各 cell:
- design_cost
- sla_violation_ratio
- expected_loss_per_axis (M9 のみ)
- selected DER の Bayes posterior 分布 (= MILP がどんな DER を picks しているか)

### 4.3 完了基準

- ✅ M9 vs M1 の per-method bootstrap 95% CI を算出
- ✅ M9 が M1 と CI 重ならない (= statistically significant 区別) ことを実測
- ✅ M9 の cost overhead を定量化 (M1 の何 % 増しか)

---

## 5. MS-4 詳細: ACN real-data sweep

### 5.1 sweep 設計

`tools/run_acn_try12.py` (try11 `run_acn_real_validation.py` の M9 拡張):
- 144 cells (3 feeders × 2 methods × 4 weeks × 3 pairings × 2 seeds)
- α=0.70 (try11 と同 harder operating point)
- ACN fixture: `test/mvp_try11/data/acn_caltech_sessions_2019_01.csv` (sha256 pin)

### 5.2 完了基準

- ✅ M9 が ACN real data で SLA 違反 [CI] を try11 M1 より小さくする
- ✅ MILP 選定 DER の posterior 分布を比較 (M1 outlier exploit vs M9 防止)

---

## 6. MS-5 詳細: Sensitivity analysis

### 6.1 軸

- prior misspec: $\hat{p}_{j,k} = p_{j,k} \pm \delta$、$\delta \in \{0.05, 0.10, 0.20\}$
- threshold scan: $\theta = 0.05 B_k, 0.10 B_k, 0.20 B_k$
- noise rate: $\varepsilon \in \{0.01, 0.05, 0.10, 0.20\}$

### 6.2 完了基準

- ✅ M9 が prior $\pm 20\%$ 誤差下で M1 より良い性能を維持する境界を実測
- ✅ θ の effect size を Pareto 図で可視化

---

## 7. 共有依存 (try11 import)

try12 の tools/ は **新規モジュールのみ** 実装。以下は try11 から import:

- `tools.der_pool` (try11) → `make_default_pool`, `TRIGGER_BASIS_K3`, `project_exposure`
- `tools.feeder_config` (try11) → `FeederVppConfig`, `feeder_active_pool`
- `tools.feeders` (try11) → `map_pool_to_feeder`
- `tools.grid_simulator` (try11) → `grid_simulate`, `to_grid_experiment_result`
- `tools.grid_metrics` (try11) → `GRID_METRICS`
- `tools.vpp_metrics` (try11) → `VPP_METRICS`
- `tools.vpp_simulator` (try11) → `all_standby_dispatch_policy`
- `tools.trace_synthesizer` (try11) → 全 synth_c* 関数
- `tools.real_data_trace` (try11) → `build_trace_from_acn_sessions`
- `tools.sdp_optimizer` (try11) → `solve_sdp_strict` (= M1)、`SDPSolution`

import path は実行時 `sys.path.insert` で `test/mvp_try11/` を追加。

---

## 8. 完了 DoD (Definition of Done)

try12 全体の成功基準:

1. ✅ M9 MILP 実装、smoke test pass
2. ✅ Theorem 2 確立 (prior-independent bound)
3. ✅ Synthetic 144-cell sweep で M9 vs M1 の statistically significant 差を実測
4. ✅ Real ACN 144-cell sweep で同上
5. ✅ Sensitivity analysis で M9 の robustness 境界を確定
6. ✅ Report.md 全章完成、§3.1 適合 (gridflow contribution claim なし)
7. ✅ Phase 2 review pass

→ これらを満たせば **PWRS / IEEE T-SG 候補**として review_record で「条件付き合格」以上を狙う。

→ 満たせない場合は **try13** へ Plan B 移行。

---

## 9. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-30 | 初版。MS-1〜MS-7 の milestone と DoD を確定 |
