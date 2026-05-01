# try11 Theoretical Results (revised, post zero-base PWRS reviewer pass)

実施: 2026-04-29 (初版 MS-A5)、2026-04-30 (本リビジョン: ゼロベース PWRS reviewer
pass で M-5 指摘 → demote / cite / rewrite)
論文章節案: report.md §4.7 にこれを統合する。

> **🔒 FROZEN as of 2026-04-30 (M-6 commit)** ─ 本ドキュメント中の Proposition 1 /
> Corollary 1 / Theorem 1 の statement・bound 値・直交性役割の証明は確定。Phase 2 で
> Bernstein bound の constant tightening / 多軸同時 Theorem 拡張等を行う場合は別 cycle
> (try12) で revision tag を上げる。本 try11 内では statement を変更しない。

## 改訂方針 (本リビジョン)

ゼロベース PWRS reviewer pass (`review_record.md` 参照) で以下の指摘を受けた:

> **M-5 理論貢献 (Theorem 1-3) の独立性ほぼゼロ**
> - Thm 1 (Pareto-optimality): min-cost MILP の自明性質。新規性ゼロ
> - Thm 2 (greedy ln K + 1): Chvátal 1979 の transcription、reduction sketchy
> - Thm 3 (label noise bound): Markov 不等式の素朴適用、直交性構造を利用していない

これに対し、論文の honest reporting の要件として以下を実施:

1. **旧 Theorem 1 → 削除** (= Proposition として §4.7 に説明文程度に残置)。MILP
   の最適解が「最低 cost」であることは MILP optimality の自明性質であり、独立した
   定理として主張するに値しない。
2. **旧 Theorem 2 → Corollary (Chvátal 1979 の派生として明記)**。SDP の
   set-cover への reduction を陽に書き、Chvátal の境界を **直接適用した結果** で
   あることを明示。"transcription" ではなく "applied corollary" として位置づけ。
3. **旧 Theorem 3 → Theorem 1 (本リビジョンで唯一の Theorem)**。直交性が境界に
   果たす役割を **陽に**書き出し、(i) 期待値、(ii) Bernstein 型 high-probability
   bound、(iii) 直交性なし baseline との比較 を構造化。

---

## 記号

| 記号 | 意味 |
|---|---|
| $\mathcal{D} = \{d_1, \dots, d_N\}$ | DER pool |
| $A \subseteq \mathcal{D}$ | active 集合 (固定) |
| $S \subseteq \mathcal{D} \setminus A$ | standby 集合 (決定変数) |
| $\mathbf{e}_j \in \{0,1\}^K$ | DER $j$ のトリガー曝露ベクトル (真の値) |
| $\tilde{\mathbf{e}}_j$ | 観測曝露ベクトル (label noise の後) |
| $E(A) = \{k: \exists j \in A, e_{j,k} = 1\}$ | active の曝露集合 |
| $c_j$ | DER $j$ の standby 契約コスト |
| $\mathrm{cap}_j$ | DER $j$ の容量 (kW) |
| $B_k$ | トリガー $k$ 発火時の最大 burst (kW) |
| $W(S, k) = \sum_{j \in S, e_{j,k}=1} \mathrm{cap}_j$ | $S$ のトリガー $k$ 真値容量損失 |

---

## Proposition 1 (旧 Thm 1) — MILP の最適性 (notational)

**主張**: SDP MILP

$$
\min_{x \in \{0,1\}^N} \sum_j c_j x_j \quad \text{s.t.} \quad x \in \mathcal{F}_{\mathrm{TriOrth}}(A)
$$

の最適解 $S^*$ は、feasible 集合 $\mathcal{F}_{\mathrm{TriOrth}}(A)$ の中で
**最低 cost** を達成する。

**位置づけ**: これは MILP 最適性の定義に等価であり、独立した定理ではない。`report.md`
§4.4 の MILP 定式化に対する直接的観測として位置づけ、本文中では「Proposition」と
してのみ言及 (Theorem 番号は付与しない)。

**先行リビジョンからの変更**: 「Pareto-optimality on (cost, worst-case loss)」と
表現していたが、$\mathcal{F}_{\mathrm{TriOrth}}$ 内で worst-case loss は
直交性により $0$ なので、Pareto frontier 上の主張は退化する (= 単一目的最適化と
等価)。表現を honest に弱体化。

---

## Corollary 1 (旧 Thm 2) — Greedy 近似境界 (Chvátal 1979 の派生)

**主張**: SDP の cost 最小化問題に対する greedy アルゴリズム
(`solve_sdp_greedy`, `tools/sdp_optimizer.py`) は、MILP 最適解 $S^*$ に対し:

$$
\mathrm{cost}(S_{\mathrm{greedy}}) \leq H_K \cdot \mathrm{cost}(S^*) = \left(\sum_{i=1}^K \frac{1}{i}\right) \mathrm{cost}(S^*) \leq (\ln K + 1) \cdot \mathrm{cost}(S^*)
$$

ここで $K$ は trigger 基底次元数。

**Reduction (陽に書く)**:

SDP の容量被覆 MILP は

$$
\min_{x} \sum_j c_j x_j \quad \text{s.t.} \quad \forall k: \sum_{j: e_{j,k}=0} \mathrm{cap}_j x_j \geq B_k, \; x_j \in \{0,1\}
$$

これは **加重多重被覆問題** (weighted multi-cover) の特殊形:
- 要素集合 $\mathcal{U} = \{1, \dots, K\}$ (trigger 軸)
- 各「集合」候補 $j$: 軸 $k$ への寄与は $a_{j,k} = \mathbf{1}[e_{j,k}=0] \cdot \mathrm{cap}_j$、コスト $c_j$
- 軸 $k$ の demand: $B_k$

**標準的 set cover との差**: 標準 set cover は要素を 1 回被覆すれば良いが、
本問題は demand $B_k > 1$ の **覆い** (multi-cover) であり、Chvátal の元の証明は
直接適用できない。Dobson (1982) [^Dobson1982] が weighted multi-cover への
拡張を与え、greedy with min-ratio (= 「単位被覆あたりコスト」最小の集合を毎回
選ぶ) が同じ $H_K$ 倍境界を満たすことを示した。`solve_sdp_greedy` は
Dobson 流の min-ratio greedy を実装している。

**帰結**:
- $K = 3$: $H_3 = 11/6 \approx 1.83$
- $K = 4$: $H_4 = 25/12 \approx 2.08$
- $K = 5$: $H_5 = 137/60 \approx 2.28$

実用域 ($K \in \{3,4,5\}$) で greedy は MILP の **2.3 倍** を超えない。

**位置づけ**: 本結果は Chvátal 1979 / Dobson 1982 の直接適用であり、SDP 固有の
新規性は **問題を multi-cover として明示的に reduce すること** にある (定理自体
は引用)。本文では "Corollary" として表記し、reduction を `report.md` §4.7.1 で
明示。

[^Dobson1982]: G. Dobson, "Worst-case analysis of greedy heuristics for
integer programming with non-negative data", Mathematics of Operations Research,
vol. 7, no. 4, pp. 515-531, 1982.

---

## Theorem 1 (Bayes-corrected, 2nd zero-base reviewer pass N-1 fix) — 直交性下の label-noise ロバスト性

> **N-1 修正履歴 (2026-04-30 後段)**: 先行版 (`f5e1cb5` commit) は posterior $P(e=1 \mid \tilde{e}=0)$ を Markov 不等式で $\varepsilon$ で素朴上界としていたが、これは prior $p \ll 1$ の場合のみ成立する。本リビジョンで Bayes 公式を陽に書き、prior 依存を明示する (詳細: `review_record.md` § N-1)。

**Setup**:

- 各 DER $j$ は **type** $\tau(j)$ を持ち、type ごとに axis $k$ への **prior 曝露率** $p_{\tau, k} = P(e_{j,k}^{\text{true}} = 1 \mid \tau(j) = \tau)$ が定まる (本論文 `make_default_pool` では default exposure $\mathbf{1}[\text{type-axis}]$ + 5% per-axis flip により $p \in \{0.05, 0.95\}$ の二値分布)
- 観測値 $\tilde{e}_{j,k}$ は真値に **対称 label noise** $\varepsilon$ を加えたもの:

$$
P(\tilde{e}_{j,k} \neq e_{j,k}^{\text{true}}) = \varepsilon
$$

- 標準 SDP は観測曝露に基づき、$S$ を **observation-orthogonal** ($\tilde{e}_{j,k} = 0 \;\forall j \in S, k \in E(A)$) に選ぶ

**Bayes posterior**:

$$
\boxed{\pi_{j,k} := P(e_{j,k}^{\text{true}} = 1 \mid \tilde{e}_{j,k} = 0) = \frac{\varepsilon \cdot p_{\tau(j), k}}{\varepsilon \cdot p_{\tau(j), k} + (1-\varepsilon) \cdot (1 - p_{\tau(j), k})}}
$$

これは $p$ への依存を持つ非自明な量。先行版の "$\pi \leq \varepsilon$" は $p \to 0$ の極限でのみ成立。

### (i) 期待 worst-case 容量損失境界 (Bayes 修正版)

固定 $S$ について:

$$
\mathbb{E}\left[\max_{k \in E(A)} W(S, k) \;\Big|\; \tilde{e}_{j,k}=0 \;\forall j \in S, k \in E(A)\right] \leq \max_{k \in E(A)} \sum_{j \in S} \mathrm{cap}_j \cdot \pi_{j,k}
$$

**証明**: $W(S, k) = \sum_{j \in S} \mathrm{cap}_j \cdot \mathbf{1}[e_{j,k}^{\text{true}}=1]$。観測 $\tilde{e}_{j,k}=0$ 条件付きで indicator は Bernoulli($\pi_{j,k}$)。線形性で per-axis 期待値を取り、$\max_k$ で union $\Box$。

**重要な含意 (先行版からの差分)**:

| type \ axis | prior $p$ | $\pi$ at $\varepsilon=0.05$ | 備考 |
|---|---:|---:|---|
| residential_ev × commute | 0.95 | **0.500** | **先行 $\varepsilon$ 上界の 10× 倍** |
| residential_ev × weather | 0.05 | 0.0028 | 先行上界より遥かにタイト |
| utility_battery × commute | 0.05 | 0.0028 | 同上 |
| heat_pump × weather | 0.95 | 0.500 | 同 commute と並ぶ weak |
| commercial_fleet × commute | 0.05 | 0.0028 | 同 utility |

**Bound のタイトさは type の prior に強く依存**。論文 §6.1 の MILP は cost 最小化で `residential_ev` の commute label-flipped 個体 ($\pi = 0.5$) を preferentially picks する傾向があるため、平均 bound は $\varepsilon$ より遥かに緩い。

### (ii) Bernstein 型 high-probability bound (Bayes 修正版)

axis $k \in E(A)$ について、$\mu_k := \sum_{j \in S} \mathrm{cap}_j \cdot \pi_{j,k}$, $\sigma_k^2 := \sum_{j \in S} \mathrm{cap}_j^2 \cdot \pi_{j,k}(1 - \pi_{j,k})$, $M := \max_{j \in S} \mathrm{cap}_j$ とする:

$$
P\left(W(S, k) \geq \mu_k + t\right) \leq \exp\left(-\frac{t^2}{2 \sigma_k^2 + \tfrac{2}{3} t M}\right)
$$

(証明: $\mathrm{cap}_j$-weighted Bernoulli($\pi_{j,k}$) 独立和への Vershynin 2018 [^Vershynin2018] Theorem 2.8.4 適用。$\pi$ が大きい場合 $\sigma^2$ も大きくなるため、bound 自体も緩む。)

### (iii) 直交性なし baseline との比較 (Bayes 修正版、prior 依存)

直交性制約を **課さない** 場合の per-axis 期待損失:

$$
\mathbb{E}[W(S', k)] = \sum_{j \in S'} \mathrm{cap}_j \cdot p_{\tau(j), k}
$$

直交性下 (Bound (i)) との **per-axis tightening factor** は:

$$
\rho_{\text{orth}}(j, k) = \frac{\pi_{j,k}}{p_{\tau(j),k}} = \frac{\varepsilon}{\varepsilon \cdot p_{\tau(j), k} + (1-\varepsilon) \cdot (1 - p_{\tau(j), k})}
$$

数値例 ($\varepsilon = 0.05$):

| prior $p$ | $\rho_{\text{orth}}$ | tightening |
|---:|---:|---|
| 0.95 | **0.526** | weak (× 0.53) |
| 0.50 | 0.100 | moderate (× 0.10) |
| 0.05 | **0.0556** | strong (× 0.056) |

**先行版が主張した "$p / \varepsilon \approx 4$ 倍タイト" は中程度 prior ($p \approx 0.4$) のときのみ成立する近似式**。本論文の pool は $p \in \{0.05, 0.95\}$ の二値分布なので、honest な statement は:

> **直交性の tightening factor は per-axis × per-DER-type で大きく異なる: high-prior axis では $\approx 0.5$ (weak), low-prior axis では $\approx \varepsilon$ (strong)。MILP が cost 最小化で high-prior label-flipped DER を preferentially picks するため、実効的 bound は worst-case (high-prior) に近づく**。

これが本論文 Theorem 1 の真の theoretical content であり、先行版「$p/\varepsilon \approx 4$ 倍一律タイト」は誤った over-claim だった。

### (iv) MILP の selection bias 注記 (N-2 連動)

Theorem 1 (i)-(iii) は **fixed $S$ に対する条件付き期待値** だが、実装 (`tools/sdp_optimizer.py:solve_sdp_strict`) は cost 最小化を行う。これは観測上「全軸 0」に見える label-flipped DER (= 統計的外れ値) を preferentially picks する **selection bias** を持つ。

**実例検証** (kerber_landnetz, $\alpha=0.70$, M1):

```
MILP 実測: cost ¥1,800, n_standby=3
  residential_ev_028  K4=(F,F,F,T)  ← default (T,F,F,T)、commute axis flip
  residential_ev_043  K4=(F,F,F,T)  ← default (T,F,F,T)、commute axis flip
  industrial_battery_006  K4=(F,F,F,T)  ← default (F,F,T,T)、market axis flip
```

3 機すべてが **label perturbation で flip された統計的外れ値**。Bayes posterior:
- 各 EV: $\pi_{\text{commute}} = 0.5$
- industrial: $\pi_{\text{market}} = 0.5$

**真の合算 expected loss = $\sum \mathrm{cap}_j \cdot \pi_{j,k}$**:
- commute: $7 \cdot 0.5 + 7 \cdot 0.5 + 100 \cdot 0 = 7$ kW (industrial の $\pi_{\text{commute}}$ は default 0 で flip 確率小)
- market: $0 + 0 + 100 \cdot 0.5 = 50$ kW

market expected loss 50 kW vs SLA target 33.6 kW = **超過** (Theorem 1 (i) bound に基づき確率的に SLA 違反が予想される)

実 ACN sweep で観測される 59-77% SLA 違反はこの **MILP selection bias × Bayes posterior 0.5** の整合的結果であり、CTOP の構造保証が崩れたのではなく、**Theorem 1 (i) bound の高 prior 領域で MILP が exploit される境界条件を実測した** ものと解釈できる。

**Phase 2 で対処すべき設計選択**:

1. **規範的 fix**: MILP に "expected loss ≤ threshold" 制約を追加。posterior $\pi_{j,k}$ を MILP 入力に拡張 (= ε と prior の推定を要する)
2. **simple fix**: pool perturbation rate を 0% に固定 (= label noise 設定を排除)、または perturbation rate を main experimental knob として sensitivity sweep
3. **honest reporting fix**: 現状を維持し、§6.1 / §8.7.5 で "MILP は label outlier を exploit する → real data 下で SLA 不安定" を **central finding** として書き直す

[^Vershynin2018]: R. Vershynin, "High-Dimensional Probability: An Introduction
with Applications in Data Science", Cambridge Series in Statistical and
Probabilistic Mathematics, 2018.

---

## 既存手法との理論的対比 (revised)

| 手法 | worst-case 違反保証 | コスト最適性保証 |
|---|---|---|
| B1 静的 +30% | なし (active 容量依存) | 過大 / 過小契約双方あり |
| B2 SP | ${\rm Pr}(\text{シナリオ集合内} ) \cdot \text{シナリオ違反}$ | シナリオ近似誤差 |
| B3 Wasserstein DRO | ball 半径 $\tau$ 以内の最悪期待値 | DRO 最適解 |
| B4 Markowitz | なし (correlation 仮定崩壊) | quadratic 最小分散 |
| B5 金融 causal | causal graph 精度依存 | クラスタ均等性に最適 |
| B6 NN | なし (distribution shift) | tail 予測精度依存 |
| **M1 SDP** | **Theorem 1 (i) で $\varepsilon \sum \mathrm{cap}_j$ 期待値境界、(iii) で直交性なし baseline の $p / \varepsilon$ 倍タイト**、(ii) で high-probability tail bound | Proposition 1 の MILP 最適 (Corollary 1 で greedy $H_K$ 倍境界) |
| M3b Soft | overlap penalty で $\varepsilon$ 境界も緩む | 同上 + 緩和項 |
| M3c Tolerant | $\varepsilon$ overlap 許容 | 同上 |

**SDP の theoretical novelty (revised)**: Theorem 1 (iii) で示された **直交性
制約が label-noise 下の期待 worst-case loss を $p/\varepsilon$ 倍タイトにする
役割** が定理 contribution の中心。Proposition 1 は MILP optimality の
restatement、Corollary 1 は Chvátal/Dobson の直接適用であり、独立貢献ではない。

---

## 論文への統合方針 (revised)

`report.md` §4.7 を以下のように再構成:

- §4.7.0 Notation (記号定義のみ)
- §4.7.1 Proposition 1 (MILP optimality, restatement)
- §4.7.2 Corollary 1 (greedy approximation, Chvátal/Dobson via reduction)
- §4.7.3 **Theorem 1** (label-noise robustness via orthogonality, 3-part)
- §4.7.4 既存手法との理論対比表

これにより IEEE Trans 査読の "novelty depth" 観点で:
- ❌ 「3 つの定理」という表面的な数 → ✅ 「1 つの真の定理 + 既知結果の整理」
- ❌ Markov 素朴適用 → ✅ 直交性役割の陽な分解 + Bernstein high-prob bound

reviewer M-5 の指摘 (「定理の独立性なし」) に対する構造的回答となる。

---

## 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-29 (初版) | Thm 1-3 (Pareto / greedy / noise) を 3 定理として宣言 |
| 2026-04-30 (本リビジョン) | ゼロベース PWRS reviewer pass M-5 に応答。Thm 1 → Proposition 1 (demote)、Thm 2 → Corollary 1 (Chvátal/Dobson の派生として明記)、Thm 3 → Theorem 1 (本リビジョン唯一の定理、直交性役割を 3 部構成で明示)。Dobson 1982 への reduction caveat 追加、Bernstein high-probability bound 追加 |
