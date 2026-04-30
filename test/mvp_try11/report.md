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
