# try12 — Phase 0.5 Ideation Record

実施: 2026-04-30
シナリオ: try11 から継続。`docs/mvp_problem_candidates.md` 候補 2 (VPP の補助サービス提供 — 機器流出入 churn ロバスト性)
立ち上げ理由: try11 ゼロベース査読 (round 2) で発見した **N-2 (MILP selection bias)** を **設計で解決する手法を提案** するため

---

## 0. 起点 — try11 が発見したこと

### try11 の真の貢献 (= 残るもの)

- Trigger-orthogonal capacity-coverage MILP の定式化 (`tools/sdp_optimizer.py`)
- DistFlow 線形化 + per-bus voltage / per-line loading constraint との組合せ (M7、`tools/sdp_grid_aware.py`)
- 実 EV 個別 churn データ (Caltech ACN-Data) を `commute` trigger 軸の物理実体として取得・integrate する pipeline (`tools/fetch_acn.py` + `tools/real_data_trace.py`)
- Bayes-corrected Theorem 1 (= try11 N-1 で訂正済): per-axis × per-DER-type の orthogonality tightening factor が `ρ_orth(j,k) = ε / (ε p_jk + (1-ε)(1-p_jk))` で書ける

### try11 の根本欠陥 (= try12 が解決対象)

**N-2: Cost-minimising MILP は label noise outliers を exploit する selection bias を持つ**。

実例 (try11 §8.7.5):
- kerber_landnetz, α=0.70 の MILP (M1) は cost ¥1,800 で 3 機選定:
  - residential_ev_028: K4=(F,F,F,T)、default (T,F,F,T) から commute axis flip
  - residential_ev_043: 同上
  - industrial_battery_006: K4=(F,F,F,T)、default (F,F,T,T) から market axis flip
- 全機が **label perturbation で flip された統計的外れ値**
- Bayes posterior $\pi_{j,k} = \varepsilon p / (\varepsilon p + (1-\varepsilon)(1-p))$:
  - 各 EV: $\pi_{\text{commute}} = 0.5$ (= 真値で commute 曝露の確率 50%)
  - industrial: $\pi_{\text{market}} = 0.5$
- **真の expected market loss = $100 \times 0.5 = 50$ kW > SLA target 33.6 kW**
- ACN 実データで 144-cell sweep の SLA 違反 59-77% は**この predictably な失敗を実測**

つまり try11 の MILP は **observation-orthogonal** (= 観測上 e=0) を達成するが、**behavioral-orthogonal** (= 真値 e=0) は達成しない。論文が主張した「構造的 robustness」は数学的に成立しない。

---

## 1. 課題深掘り (S0-S8、policy §2.5 Rule 8)

### S0: 何の問題か?
**Cost-minimising MILP が label noise を exploit して "ニセの直交性" を選ぶ**。これは VPP / DER siting / portfolio 一般に発生する **設計欠陥**。

### S1: なぜ失敗するか?
- MILP の objective = cost minimisation
- Constraint = **observed** $\tilde{e}_{j,k}=0$
- 観測上 0 でも真値 1 の確率 = Bayes posterior $\pi$
- $\pi$ は prior $p$ に依存し、high-prior axis (residential_ev × commute) で $\pi \approx 0.5$
- MILP は cheaper な outlier を preferentially picks → 高 prior axis で集中

### S2: 既存手法は?
- DRO (B3, Esfahani-Kuhn 2018): ball 内 worst-case 最適。symmetric label noise の prior 依存性は明示的にハンドルしない
- Robust MILP (Bertsimas-Sim 2004): uncertainty set 設計依存。Bayes posterior を入力にする formulation はない
- Posterior-aware MILP は Chemical Engineering / Production Planning 分野で散見されるが、VPP context への適用例は確認できない (要 literature search、Phase 1 で実施)

### S3: 物理的に何が起きているか?
- Pool perturbation = 真の DER の heterogeneity (= 全 residential EV が完全に commute 曝露ではない、地域・所有者で variation)
- 観測 (= label) は perfect でない (= 設計時の不完全な情報)
- MILP は incomplete information 下で最適化するが、**posterior の non-uniformity を無視**

### S4: 他分野で同型問題は?
- **Bayesian DRO** (Bertsimas et al. 2018+): posterior を MILP/LP に組み込む系
- **Stochastic constraint programming**: chance constraint with belief update
- **Group testing under noisy labels**: Bayes-aware item selection

### S5: 数学的構造?
- 元の MILP: `min c'x s.t. observed-orthogonal(x), capacity-coverage(x)`
- 提案 MILP: `min c'x s.t. expected-loss(x; π) ≤ θ, capacity-coverage(x)`
  - ここで `expected-loss(x; π) = max_k Σ_j π_{j,k} cap_j x_j`
- これは **chance constraint の deterministic counterpart**

### S6: 実装可能性?
- π は ε と prior の関数。prior は DER type ごとに既知 (or estimable)。ε は noise rate (or estimable)
- Bayes-aware MILP は依然 binary linear program、PuLP + CBC で解ける
- 計算量は M1 と同オーダー (= 制約数が constant 倍増えるのみ)

### S7: 提案手法は?
**M9: Bayes-Robust Trigger-Orthogonal Portfolio (BR-CTOP)**

```
変数: x_j ∈ {0,1}
目的: min Σ c_j x_j
制約:
  (orth-obs)      ∀k ∈ E(A): Σ_{j: tilde_e_jk=0} (1 - tilde_e_jk) x_j ≥ |S|  
                  (= observation orthogonality, M1 と同じ)
  (expected-loss) ∀k ∈ E(A): Σ_j π_{j,k} cap_j x_j ≤ θ_k  
                  (= 真の期待損失を threshold 以下に)
  (capacity)      ∀k: Σ_{j: tilde_e_jk=0} cap_j x_j ≥ B_k  (M1 と同じ)
```

ここで $\theta_k$ は per-axis allowed expected loss (例: $0.05 \cdot B_k$ で SLA tail 5%)。

**Theorem 2 (M9 の保証)**: M9 が feasible なら、$\mathbb{E}[\max_k W(S^*, k)] \leq \max_k \theta_k \leq 0.05 \cdot \max_k B_k$。これは **prior に依存しない** uniform な bound (= try11 Theorem 1 で問題だった prior 依存を解決)。

### S8: 検証戦略?
1. M9 の MILP を実装、try11 と同じ pool / trace で smoke test
2. M1 (try11) vs M9 (try12) を以下で比較:
   - **Synthetic sweep (= F-M2 360 cells)**: SLA 違反、cost、selection された DER の Bayes posterior 分布
   - **Real ACN sweep (= 144 cells)**: 同様 + multi-week CI
   - **Bayes posterior 分布の比較**: M1 が picks する DER の $\pi$ vs M9 の $\pi$
3. **Headline 期待**: M9 は M1 より cost が +α 高いが、SLA 違反が **prior に依存せず uniform に低い**

---

## 2. Rule 9 v2 (TRIZ 遠隔ドメイン候補) の整理

try11 で sentinel mechanism を選定したが、try12 の motivating finding (label noise + cost-min MILP は信頼できない) に対しては別 analogy が要る。

### 候補 (5 個並列抽象化、policy §2.5.2 準拠)

| # | 候補 | 抽象化 | invariant 検査 |
|---|---|---|---|
| 1 | **品質保証統計学 (acceptance sampling)** | サンプル検査の posterior に基づく合否判定 | ✅ Bayes posterior + decision threshold が直接対応 |
| 2 | 医療診断 (Bayes net) | 検査結果から疾患確率を推定し閾値判断 | ✅ posterior + threshold 同型 (intervention 不要) |
| 3 | 偽造紙幣検出 | 観測特徴 → 真贋 posterior → 受領閾値 | ✅ 同型 |
| 4 | スパムフィルタ | 単語特徴 → spam posterior → block 閾値 | △ adversarial 性が異なる (label noise 対 active adversary) |
| 5 | 投資ポートフォリオの信頼区間 (Markowitz-Bayes) | 予想 return の posterior に robust な配分 | ✅ continuous 版で類似 |

**Rule 9 v2 機械的選定**: 5 候補すべて Bayes posterior を decision threshold で扱う構造で **invariant 保存度ほぼ同等**。最も発祥が早く mature なのは #1 (acceptance sampling, Dodge & Romig 1929)。VPP との **distance** (= 物理 vs 抽象意思決定) も他より大きい。

→ **#1 acceptance sampling を analogy に採用**。「ロット内の defect rate を posterior で推定し、threshold 以下なら受領」と「standby pool の expected loss を Bayes posterior で評価し、threshold 以下なら採用」が直接対応。

---

## 3. CPCM (Rodriguez Dominguez 2025) との 5 軸構造差分 — try12 版

try11 で M1 vs CPCM の 5 軸差分を立てたが、try12 の M9 は以下で位置づける:

| 軸 | CPCM | M9 (try12) |
|---|---|---|
| (a) Driver 同定 | nonlinear filtering | 物理事前知識 (try11 と同じ) |
| (b) Allocation 形式 | 連続 weight + PDE | **離散 binary + Bayes-aware MILP** |
| (c) 制約形式 | projection-divergence (連続) | **expected-loss threshold (離散 chance constraint)** |
| (d) 目的関数 | Sharpe / utility | **cost (¥) under Bayes-robust expected loss bound** |
| (e) 動学設定 | continuous-time PDE | **discrete-event jump + label noise observation model** |

→ M9 は **try11 M1 の "label noise" 軸での自然な拡張**であり、CPCM とは依然構造的に独立。

---

## 4. try11 N-2 finding の論文的位置づけ

try11 §8.7.5 の SLA 違反 52-77% (= MILP selection bias の実証) は **try12 の motivation** として central。

論文 (try12 report.md) では:
- §1 Introduction で「観測 e=0 と behavioral e=0 の乖離」を problem として立てる
- §2 Background で try11 (citation) の N-2 finding を motivating empirical evidence として引用
- §4 Method で M9 (Bayes-Robust SDP) を提案
- §6 Results で M1 vs M9 の比較
- M9 が M1 を **複数の operating point で statistically significant に勝つ** ことを示せれば PWRS 候補

---

## 5. 既存手法との理論対比 (try11 表 § 4.7.4 を update)

| 手法 | worst-case 違反保証 | コスト最適性 | label-noise selection bias |
|---|---|---|---|
| B1 静的 +30% | なし | 過大 | × (orthogonality 制約なし) |
| B3 Wasserstein DRO | ball 内最悪 | DRO 最適 | △ (ball 半径で部分対応) |
| **M1 (try11)** | $\rho_{\text{orth}} \cdot \sum p \cdot \mathrm{cap}$、prior 依存 | MILP 最適 | **× (high-prior axis で exploit される)** |
| **M9 (try12 提案)** | $\theta_k$ で **prior-independent uniform bound** | MILP cost 最適 under expected-loss constraint | ✅ **構造的に防止** |

---

## 6. Phase 1 への引継

- 実装 milestone は `implementation_plan.md` に明記
- try11 の `tools/sdp_optimizer.py` `tools/sdp_grid_aware.py` `tools/real_data_trace.py` `tools/fetch_acn.py` を **import で再利用** (= try12 の tools/ には新規変種のみ実装)
- 同 ACN data fixture (`test/mvp_try11/data/acn_caltech_sessions_2019_01.csv`、sha256 pin) を再利用
- try11 と同 pool seed=0 で M1 vs M9 の差を pure に測る

---

## 7. 期待される try12 のリスクと plan B

### 主要リスク

- **R1**: Bayes-Robust constraint で MILP が常に infeasible になる (= θ を厳しくしすぎ)。Plan B: θ を slack 化 (M9-soft) し sensitivity を見る
- **R2**: M9 が M1 と statistically 区別できない (= label noise rate ε が小さく実測差が CI 内)。Plan B: ε=0.10, 0.20 等で sensitivity sweep、effect size を増幅
- **R3**: prior $p$ の推定誤差で M9 の bound が崩れる。Plan B: prior estimation の robustness analysis (= sensitivity to misspecified $p$) を §6 に組み込む

### Plan B 確定: M9 が M1 を beat できなかった場合
- **try13** へ移行。設計をさらに変える (例: posterior を solver 内で動的に推定する MAP-MILP)

### Phase 2 review 観点 (= Phase 0 で確定)
- §6 で **CI 完全分離** の M9 vs M1 比較が出るか
- §4.7 で M9 の theoretical guarantee が **prior-independent uniform** に立つか
- 実 ACN data で M9 が **multi-week × multi-pairing CI** で win を維持するか

---

## 8. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-30 | 初版。try11 N-2 を起点に M9 (Bayes-Robust CTOP) を提案、Phase 1 implementation_plan.md に引継 |
