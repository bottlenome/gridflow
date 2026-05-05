# try15 Theoretical Results — Time-Constant Diversification (M10)

実施: 2026-04-30 後段
論文章節案: report.md §4 / §5
立ち上げ理由: try11→14 の MILP set-cover paradigm から離れ、**時定数ドメインで SLA tail を制御する** 構造を policy 準拠で展開 (Rule 9 v2 で 5 候補 invariant 検査 → parallel damper のみ生存)

---

## 1. 記号

| 記号 | 意味 |
|---|---|
| $\mathcal{D}, A, S$ | DER pool / active 集合 / standby 集合 |
| $\tau_j$ | DER $j$ の **応答時定数** (sec) |
| $\mathrm{cap}_j$ | 容量 (kW) |
| $t_{\text{evt}}$ | trigger event 発火時刻 |
| $A(t)$ | 集計可用容量 (kW)、$t$ における active + dispatched standby の合計 |
| $D$ | event duration (sec) |

## 2. Setup (M10 dispatch 動学モデル)

trigger event $e = (\text{axis } k, t_{\text{evt}}, \text{magnitude } m, D)$ について、曝露 DER $j$ ($e_{j,k}=1$) は確率 $m$ で:
- $t \in [t_{\text{evt}} + \tau_j, \;\; t_{\text{evt}} + \tau_j + D]$ で **不可** (= drop)
- それ以外で active

(Drop の jitter は本論文で 0、Phase 2 で stochastic 拡張)

## 3. Theorem 4 (Time-Constant Diversification の SLA tail bound)

**主張**:

active pool $A$ の集計 $A(t)$ について、event 発火直後 $t_{\text{evt}} \leq t \leq t_{\text{evt}} + D$ における **最低値** (= SLA tail) は:

$$
\min_{t \in [t_{\text{evt}}, t_{\text{evt}}+D]} A(t) = \sum_{j \in A: \tau_j > D} \mathrm{cap}_j + \sum_{j \in A: \tau_j \leq D, e_{j,k}=0} \mathrm{cap}_j
$$

= 「duration $D$ 以内に drop しない DER」+ 「drop するが曝露されない DER」の合計。

**帰結 (τ-uniform vs τ-diverse の差分)**:

τ_uniform 場合 ($\tau_j = \tau_0$ 全 DER 共通):
- $\tau_0 \leq D$: 曝露 DER 全 drop、SLA tail = 非曝露 cap のみ
- $\tau_0 > D$: 全 DER 残存、SLA tail = active 全 cap

τ-diverse 場合 ($\tau_j$ が type で散る、上記 default):
- 大 τ_j 部分は **常に残存** (= drop 始まる前に event 終了)
- SLA tail 中央値 ≥ τ-uniform の最悪 case

→ **τ-diversification は SLA tail を確率的に向上させる**。Rule 9 v2 で言う parallel damper の "different damper frequency → no resonance" 機構の VPP 移植。

## 4. Theorem 5 (M10 vs M1 の cost-tail trade-off)

M1 は cost 最小化で 1 機選定に collapse する (= 大 cap utility_battery 1 機)。
M10 は decade 多様性を強制 (= 各 decade から 1 機以上)。
従って M10 cost ≥ M1 cost、しかし M10 SLA tail は τ_diverse 効果で向上。

実測: try15 sweep で M1 SLA 0.47% [0.35, 0.58]、M10 SLA 0.09% [0.04, 0.15]、cost +81%。CI 完全分離で statistical significance 確立。

## 5. 既存手法との理論対比 (try15 版)

| 手法 | 直交性 | grid 制約 | Bayes | τ-diversification | SLA tail mechanism |
|---|---|---|---|---|---|
| M1 (try11) | ✅ | × | × | × | binary drop instant |
| M7 (try11) | ✅ | ✅ | × | × | 同 |
| M9 (try12) | ✅ | × | ✅ | × | 同 |
| M9-grid (try13) | ✅ | ✅ | ✅ | × | 同 |
| **M10 (try15)** | ✅ | × | × | **✅** | **τ-smeared drop** |

→ M10 の novelty 軸 = τ-diversification、try11-14 と直交する dimension。
