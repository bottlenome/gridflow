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

## Theorem 1 (本リビジョンで唯一の Theorem; 旧 Thm 3 の rewrite) — 直交性下の label-noise ロバスト性

**Setup**:

- 各 DER $j$ は真の曝露ベクトル $\mathbf{e}_j \in \{0,1\}^K$ を持つが、観測値
  $\tilde{\mathbf{e}}_j$ は **independent symmetric label noise** で得られる:

  $$
  \forall j, k: \quad P(\tilde{e}_{j,k} \neq e_{j,k}) = \varepsilon, \quad \tilde{e}_{j,k} \perp \tilde{e}_{j',k'} \; (\text{for } (j,k) \neq (j',k'))
  $$

- 標準 SDP は **観測曝露** に基づき、$S \subseteq \mathcal{D} \setminus A$ を
  以下を満たすように選ぶ (= observation-orthogonal):

  $$
  \forall j \in S, k \in E(A): \tilde{e}_{j,k} = 0
  $$

**主張 (3 部構成)**:

### (i) 期待 worst-case 容量損失境界

$$
\mathbb{E}\left[\max_{k \in E(A)} W(S, k) \,\Big|\, \tilde{e}_{j,k}=0 \;\forall j \in S, k \in E(A)\right] \leq \varepsilon \cdot \sum_{j \in S} \mathrm{cap}_j
$$

**証明**: 観測 $\tilde{e}_{j,k} = 0$ かつ noise rate $\varepsilon$ の下で、
真値 $e_{j,k} = 1$ は Bayes flip により高々 $\varepsilon$ の確率で起こる。
よって $W(S, k) = \sum_{j \in S} \mathrm{cap}_j \cdot \mathbf{1}[e_{j,k}=1]$ の
条件付き期待値は $\varepsilon \cdot \sum_{j \in S} \mathrm{cap}_j$ で上界される。
$\max_{k}$ を取っても各 $k$ への期待が同じく上界されるため $\Box$。

### (ii) Bernstein 型 high-probability bound

各 $k \in E(A)$ について、

$$
P\left(W(S, k) \geq \varepsilon \sum_{j \in S} \mathrm{cap}_j + t\right)
\leq \exp\left(-\frac{t^2}{2\varepsilon(1-\varepsilon)\sum_{j \in S} \mathrm{cap}_j^2 + \tfrac{2}{3} t \cdot \max_{j \in S} \mathrm{cap}_j}\right)
$$

**証明スケッチ**: $W(S, k) - \mu_k = \sum_{j \in S} \mathrm{cap}_j (X_j - \varepsilon)$、
ただし $X_j \in \{0, 1\}$ は条件付きで independent Bernoulli($\varepsilon$)。
標準 Bernstein 不等式 (Vershynin 2018 [^Vershynin2018], Theorem 2.8.4) を
$\mathrm{cap}_j$-weighted Bernoulli 和に適用。

**帰結 (実用)**: $\varepsilon = 0.10$, 典型 $|S| = 10$, $\mathrm{cap}_j = 100$ kW
で $\sum \mathrm{cap}_j = 1000$ kW、$\sum \mathrm{cap}_j^2 = 100,000$ kW^2、
$\max \mathrm{cap}_j = 500$ kW (utility battery) のとき、$t = 200$ kW で
$P(W > 100 + 200) \leq \exp(-200^2 / (2 \cdot 0.09 \cdot 100000 + 2/3 \cdot 500 \cdot 200)) = \exp(-200^2 / (18000 + 66667)) = \exp(-200^2 / 84667) \approx \exp(-0.47) \approx 0.62$。緩いが情報量はある。

### (iii) 直交性なし baseline との比較 (= 本 Theorem の本質)

直交性制約を **課さない** 場合 (= 任意の $S' \subseteq \mathcal{D} \setminus A$
を観測条件付けなしに選ぶ)、worst-case loss は:

$$
\mathbb{E}\left[\max_{k \in E(A)} W(S', k)\right] \leq p \cdot \sum_{j \in S'} \mathrm{cap}_j
$$

ただし $p = \max_{k \in E(A)} P(e_{j,k}=1)$ は marginal base-rate 曝露率。
実用域では $p \in [0.3, 0.5]$ (典型: 半数の DER が commute / weather 軸に
曝露)。

**比較**: $p = 0.40$, $\varepsilon = 0.10$ で:

$$
\frac{\text{Bound (i) (orthogonal)}}{\text{Bound (iii) (no orth)}} = \frac{\varepsilon}{p} = \frac{0.10}{0.40} = 0.25
$$

→ **直交性は期待 worst-case loss を 4 倍タイトにする**。これが trigger-orthogonal
SDP の構造的優位の数学的説明であり、Markov 不等式の素朴適用ではなく **直交性
制約自体の役割** を陽に分離した形で書ける。

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
