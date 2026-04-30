# try11 — Sentinel-DER Portfolio (SDP) for Trigger-Orthogonal Standby Design

実施: 2026-04-29
著者 (仮想): gridflow research collective
シナリオ: `docs/mvp_problem_candidates.md` 候補 2 (VPP の補助サービス提供 — 機器流出入 churn ロバスト性)
ideation: `test/mvp_try11/ideation_record.md`
実装計画: `test/mvp_try11/implementation_plan.md`
データ: `test/mvp_try11/results/try11_results.json` (270 cells)

---

## Abstract

仮想発電所 (Virtual Power Plant; VPP) が系統運用者へ補助サービスを提供する際、メンバー機器 (EV / 蓄電池 / エコキュート 等) の **流出入 (churn)** は重尾分布をもって発生する。共通の外部トリガー (通勤時刻、気象、市場価格、通信障害) が同期離脱を駆動するため、独立同分布仮定下で設計された予備容量 (relai 容量) や強化学習ベース動的補充は、新規トリガーや trigger-co-occurrence 下で SLA 違反に至る。本研究は **Sentinel-DER Portfolio (SDP)** を提案する: DER の **物理因果トリガー曝露** をベクトル化し、active pool の曝露集合と直交する standby pool を整数計画問題 (MILP) として定式化する。提案は (i) 動物行動学の歩哨 (sentinel) 機構を Rule 9 v2 の遠隔ドメイン候補 5 個から invariant 検査で機械的に絞り込んで導出し、(ii) 金融分野で先行する causal portfolio (Lopez de Prado 2019, Rodriguez Dominguez 2025) と 5 軸 (driver 同定 / allocation 連続-離散 / 制約形式 / 目的関数 / 動学設定) で構造的に異なる discrete-MILP-jump-tail 設定として独立 contribution する。実験は 200 機 DER pool × 6 trace 種 (C1 単一既知 / C2 既知極大 burst / C3 同時複数 / C4 基底外 / C5 頻度 shift / C6 label noise) × 15 method (SDP 9 variants + baseline 6) × 3 seed = 270 cells で実施した。主要結果として SDP が baseline B2 (Stochastic Programming), B3 (Wasserstein DRO), B4 (Markowitz 相関 portfolio), B6 (Naive NN reactive) と同等の cost = ¥18,000/月で 0.19% の SLA 違反率を達成した一方、業界 default の B1 (静的 +30% 過剰契約) は SLA 違反率 100% に至り、B5 (金融 causal portfolio 簡易版) は強制 diversification によりコスト ¥24,669/月かつ違反率 3.08% と高コスト・高違反両面で劣ることを示した。SDP の差分価値は **構造的保証** (= データ依存しない厳密直交性) にあり、label noise 10% 下でも違反率 0.15% に留まる頑健性を実証する。基底外 (C4) では SDP も他手法と同様の degrade (~1.1%) を示すが、failure mode は detection 容易な構造に留まり、NN 系の silent failure と異なる failure 形態を持つ。

---

## 1. Introduction

仮想発電所 (VPP) は数百〜数千の小規模分散型エネルギー資源 (DER; EV、住宅蓄電池、エコキュート等) を束ねて系統運用者に **補助サービス** (周波数調整 ancillary service) を契約供給する事業である [^1]。VPP 事業者は集約 SLA (例: 5 MW を 30 秒以内に出力) で契約し、個別 DER の出力変動を集合内で吸収して契約量を保証する。

### 1.1 課題: 重尾的 burst churn

実運用では DER メンバーが以下の理由で常時入れ替わる (churn):

- **時刻トリガー**: EV は朝出発・夜帰宅で運転モードに移行、VPP プールから一時離脱
- **気象トリガー**: 寒波で電気給湯機が一斉自動運転、VPP 余力消失
- **市場トリガー**: 卸電力市場価格 spike で DER 所有者が独自売電へ転用
- **通信トリガー**: セルラー網障害で広域 DER 群が制御不能に

独立同分布 (i.i.d.) 仮定下では平均 churn rate に基づく確率的予備容量で対処できるが、**現実は共通因果ドライバーで同期離脱する重尾分布**であり、bursty な時間帯 (夕方通勤・厳冬朝・市場 spike) に SLA 違反 → 規制ペナルティ・契約失効リスクが顕在化する。

### 1.2 既存手法の限界 (詳細は §3)

VPP / DER aggregation の reliability 問題に対する既存手法は概ね以下 6 系統:

| 系統 | 代表手法 | 限界 |
|---|---|---|
| A. Stochastic Programming | 二段階 SP, Sample Average Approximation | 重尾シナリオ網羅にシナリオ数 N が指数増 |
| B. Distributionally Robust | Wasserstein DRO, moment-based DRO | ball 内で暗黙の i.i.d.、causal 構造を扱わない |
| C. Robust Optimization | Bertsimas-Sim, LOLP-based reserve | uncertainty set 設計に causal 視点なし、保守的 |
| D. 強化学習 | DQN, PPO, multi-agent RL | ブラックボックス、SLA 保証なし、新規トリガー OOD で崩壊 |
| E. 相関 portfolio | CVaR-based, factor model | 過去相関は backward-looking、新規ドライバーに脆弱 |
| F. ゲーム理論 | Shapley value DER aggregation | reliability に踏み込まず |

**全系統が共通に欠く視座**: 「**何が**離脱するか」の確率モデル化はあるが、「**なぜ同時に**離脱するか」の **因果トリガー** を構造的に扱わない。

### 1.3 提案: Sentinel-DER Portfolio (SDP)

本研究は **動物行動学の歩哨機構** [^2] を遠隔ドメインから移植し、VPP の standby 設計に適用する:

```
鳥群の歩哨 (sentinel)         VPP の standby DER
  ─ 採餌者と異なる場所     ─ active pool と異なる外部トリガー曝露
  ─ 捕食者警報を共有しない    ─ active のトリガー曝露集合の補集合
  ─ 採餌時間損失とのコスト最小化 ─ standby 契約コストの最小化
```

数式化: DER j のトリガー曝露ベクトル $\mathbf{e}_j \in \{0,1\}^K$ を K 個の物理基底 (commute / weather / market / comm_fault) で記述し、standby 集合 $S$ を以下の MILP で選択する:

$$
\min_{S \subseteq \mathcal{D} \setminus A} \sum_{j \in S} c_j^{\mathrm{standby}} \quad \text{s.t.} \quad \mathrm{TriOrth}(A, S) \;\land\; \forall k: \mathrm{Cap}_S^{(\bar{k})} \geq B_k
$$

ここで $\mathrm{TriOrth}(A, S) := \forall k: (\sum_{j \in A} e_{j,k} > 0) \Rightarrow (\sum_{j \in S} e_{j,k} = 0)$ で active 側で曝露している全トリガー軸について standby 側は曝露ゼロを要求する。

### 1.4 Contribution

1. **問題の構造化** (§3-4): VPP churn 問題を「重尾 burst churn を駆動する外部トリガーに対して standby 集合を **trigger-orthogonal** に設計する portfolio 問題」として定式化、既存手法の暗黙 i.i.d. 仮定を明示破る
2. **遠隔ドメイン移植** (§4): Rule 9 v2 (`docs/mvp_review_policy.md` §2.5.2) に従い、生態学/動物行動学/免疫学の 5 候補から invariant 保存検査で sentinel 機構を機械的選定
3. **金融 causal portfolio との構造的差分** (§3.4): Rodriguez Dominguez 2025 [^3] の連続-PDE framework に subsume されない discrete-MILP-jump-tail 設定として独立 contribution
4. **実証** (§5-6): 200 機 DER pool × 6 trace × 15 method × 3 seed = 270 cells の比較実験で、業界 default (B1) が 100% 違反する条件下で SDP が baseline と同 cost で 0.19% 違反、label noise 10% 下で 0.15% を達成

---

## 2. Background

### 2.1 仮想発電所 (VPP) と補助サービス

VPP は分散型 DER を ICT 技術で統合管理するプラットフォームで、欧米では Tesla Powerwall fleet [^4]、日本では関西電力・東京電力の VPP 実証等が運用中。集約 DER は **補助サービス市場** (PJM の synchronized reserve、ENTSO-E の FCR/aFRR、日本の調整力公募) で予備力商品として取引される。契約は典型的に「アップ/ダウン X MW を 30 秒/15 分応答」など SLA tail 制約形式である。

### 2.2 集約 SLA 達成の不確実性

DER 個別の出力可用性は (a) 物理的能力 (蓄電池 SOC、EV 接続状態)、(b) 所有者の意思 (帰宅時間、給湯機運転時刻)、(c) 通信状態に依存する。VPP 事業者は集約 SLA を保証するため、active 集合の個別 churn を集合内で吸収する設計が必要となる。

### 2.3 重尾 burst churn の経験的特性

VPP 実運用ログを解析した Müller et al. 2023 [^5] は、residential EV pool の active 数が時間帯依存の cyclic shift と日付依存の rare deep shift を持つことを報告し、後者が SLA 違反の主因であると指摘した。同研究は churn を時間方向の 1 次マルコフ仮定でモデル化したが、**因果ドライバーの構造分解** には踏み込んでいない。

---

## 3. Related Work

### 3.1 Stochastic / Robust / DRO アプローチ

Conejo et al. 2010 [^6] は二段階 stochastic programming を電力システム scheduling 全般に適用、Wang et al. 2019 [^7] は VPP context での実装を提示した。これらはシナリオ集合の質に強く依存し、重尾分布では N が膨張する。

Bertsimas & Sim 2004 [^8] の robust optimization framework を VPP に適用した Zhang et al. 2017 [^9] は uncertainty set 設計の具体化を試みたが、**集合の選択基準** に causal 視点はない。Esfahani & Kuhn 2018 [^10] の Wasserstein DRO は「distribution の近傍」を扱うが、**何が変動するか** (どの因果軸か) を明示しない。

### 3.2 強化学習 / 深層学習

Yan et al. 2022 [^11] は multi-agent RL で VPP 内 DER 配分を学習。RL の本質的課題は (i) SLA 保証の明示性欠如、(ii) 訓練分布外 (OOD) でのブラックボックス崩壊。本研究は §6.3 で OOD 条件下の比較実験で具体的にこの問題を再現する。

### 3.3 相関 portfolio (Markowitz 系)

Mathieu et al. 2015 [^12] は CVaR-based DER portfolio で過去相関行列を使った最小分散選択を提案。**問題: 過去相関は backward-looking** で、市場ルール変更や新規気象パターン下では相関が破れる。

### 3.4 金融 causal portfolio との関係 (本研究の最重要先行)

#### 3.4.1 Lopez de Prado 2019 [^13]

Hierarchical risk parity に causal graph (PC アルゴリズム経由) を組み込んだ portfolio 構築。Causal direction を考慮するが、**graph は資産間** (asset-asset) の相関構造から data-driven に推定される。

#### 3.4.2 Rodriguez Dominguez 2025 [^3]

**Causal PDE-Control Models (CPCM)** は causal portfolio の最前線で、以下を統合:

- **Structural causal drivers** + **nonlinear filtering** で隠れドライバー推定
- **Forward-backward PDE control** で連続-time 動的最適化
- **Driver-conditional risk-neutral measure** で hedging/pricing 統一
- **Projection-divergence duality**: portfolio を causal driver span に restrict すると unconstrained optimum に最も近い feasible allocation が選ばれる
- **Causal completeness condition**: 有限 driver span が systematic premia を捕捉する条件
- **Markowitz / CAPM / APT / Black-Litterman は limiting case**, RL / deep hedging は unconstrained approximation

CPCM は U.S. equity panel × 300+ candidate drivers で Sharpe 比 / turnover / persistence の改善を実証。

#### 3.4.3 SDP との 5 軸構造差分

`ideation_record.md` §4.5b で詳細化した通り、SDP と CPCM は以下 5 軸で構造的に異なる:

| 軸 | CPCM (金融) | SDP (本研究, VPP) |
|---|---|---|
| (a) Driver 同定 | nonlinear filtering で観測過程から推定 | **物理事前知識から enumerate** (~5 軸) |
| (b) Allocation 形式 | 連続値 portfolio weight + PDE 制御 | **離散 (binary) DER 選択集合**; MILP |
| (c) 制約形式 | projection-divergence duality (連続) | **trigger-orthogonal set 制約** (離散) |
| (d) 目的関数 | Sharpe / utility / hedging error | **SLA tail 確率** (規制契約で外部固定) |
| (e) 動学設定 | continuous-time PDE 制御 | **discrete-event jump (heavy-tail burst)** |

特に (a) が決定的: CPCM は「**何が原因か分からない**まま因果構造を推定」する困難な問題を解くが、SDP は「**因果トリガーは枚挙可能**、各 DER の曝露を物理構造から導く」問題で、causal discovery 段階を bypass できる。

#### 3.4.4 Positioning ステートメント

> SDP は CPCM の連続-PDE framework に subsume されない **discrete structural causal portfolio** であり、power systems の物理計測可能性と離散 DER 選択の必然性を活用した独立 contribution である。

---

## 4. Method: Sentinel-DER Portfolio (SDP)

### 4.1 トリガー基底と DER 曝露ベクトル

DER pool $\mathcal{D} = \{d_1, \dots, d_N\}$ の各機器 $d_j$ に以下を割り当てる:

- 容量 $\mathrm{cap}_j \in \mathbb{R}_{>0}$ (kW)
- active 契約コスト $c_j^{\mathrm{a}}$ / standby 契約コスト $c_j^{\mathrm{s}} \in \mathbb{R}_{>0}$ (¥/月)
- **トリガー曝露ベクトル** $\mathbf{e}_j \in \{0,1\}^K$

ここで $\mathbf{T} = (T_1, \dots, T_K)$ は K 個の物理因果トリガーの基底:
- $T_1$ = commute (人の移動 / 帰宅時刻)
- $T_2$ = weather (寒波 / 猛暑等の熱負荷急増)
- $T_3$ = market (卸電力市場価格 spike)
- $T_4$ = comm_fault (通信網障害)

$e_{j,k} = 1$ は「DER $j$ はトリガー $T_k$ 発火時に高確率で churn する」ことを意味する。

### 4.2 提案: 直交性制約

active 集合 $A$ の **曝露集合** を $E(A) := \{k : \exists j \in A, e_{j,k}=1\}$ とする。standby 集合 $S$ への要求は:

**(直交性)** $\quad \forall k \in E(A): \forall j \in S: e_{j,k} = 0$

すなわち $A$ で曝露している全トリガー軸について $S$ は曝露ゼロ。これにより、任意のトリガー $T_k \in E(A)$ が単独で発火しても $S$ は構造的に影響を受けない。

### 4.3 容量被覆制約

$T_k$ 発火時の最大 burst 規模を $B_k$ (kW) とする。標準形:

**(被覆)** $\quad \forall k: \sum_{j \in S, e_{j,k}=0} \mathrm{cap}_j \geq B_k$

これは「$T_k$ 発火で失効しない standby 容量の合計」が想定 burst を上回ることを要求する。

### 4.4 SDP MILP

$x_j \in \{0,1\}$ を「DER $j$ を standby に含める」二値変数とする:

$$
\min_{x \in \{0,1\}^N} \; \sum_{j=1}^N c_j^{\mathrm{s}} x_j
$$

subject to:

$$
\begin{aligned}
& x_j = 0 && \forall j \in A \\
& \sum_{j: e_{j,k}=1} x_j = 0 && \forall k \in E(A) \quad \text{(直交)} \\
& \sum_{j: e_{j,k}=0} \mathrm{cap}_j \cdot x_j \geq B_k && \forall k \quad \text{(被覆)}
\end{aligned}
$$

実装: PuLP + CBC。N = 200, K = 3-4 の規模で sub-second 解 (実測 0.2-0.4s/cell)。

### 4.5 Variant 群 (M1-M6)

| variant | 切替点 | 主張 |
|---|---|---|
| **M1** | strict, K=3, MILP | canonical |
| M2a/b/c | K=2/3/4 | basis 次元数の影響 |
| M3a-c | strict / soft / tolerant | orthogonality 緩和の trade-off |
| M4a/b | MILP / greedy | 計算量と最適性 |
| M5 | M1 design + NN dispatch | NN は動員に使えるが設計には不可 |
| M6 | M1 on label-noise pool | label 誤りロバスト性 |

ソフト緩和 (M3b): 直交性を penalty 項 $\lambda \sum_{k \in E(A)} \sum_{j \in S} e_{j,k}$ に変換、容量制約は硬。
許容緩和 (M3c): $\sum_{j: e_{j,k}=1} x_j \leq \varepsilon$ で overlap 許容数を制限。

### 4.6 遠隔ドメイン候補からの選定経路

`ideation_record.md` §6 に従い、Rule 9 v2 で 5 候補を並列抽象化し invariant 検査:

| 候補 | invariant 保存 | S7 trigger-orthogonal 直結度 |
|---|---|---|
| **A. 鳥群 sentinel** | **5/5 ✅** | **直結 (mechanism そのもの)** |
| B. 種子バンク dormancy | 4.5/5 | 間接 (latency tranche) |
| C. 免疫メモリ細胞 | 4/5 (memory 不在) | 間接 (broad coverage) |
| D. 真社会性昆虫 | 2/5 ❌ | 完全脱落 |
| E. 雪崩 anchor | 4/5 (cascade 不在) | 間接 (universal coverage) |

**A (sentinel) のみが** trigger-orthogonal を直接 captures し、5/5 invariant 保存で **機械的に唯一の生存候補** となる。

---


