# try12 — Phase 2 Self-Review (= MS-7) + Self-Assessment

実施: 2026-04-30
評価対象: `report.md` (try12) ・`theorems.md` (try12) ・`m9_tools/*.py` ・`results/try12_*.json`
review 観点: `docs/mvp_review_policy.md` §4.2 適用 (zero-base、ゼロベース査読者視点で本 try12 を初見扱い)

---

## 1. PO からの宿題 (= self-assessment 義務)

ユーザーが MS-2 開始前に投げた 2 質問:
- **Q1**: 新規性はあるか?
- **Q2**: 定量的に評価できているか?

以下、本 try12 が両方に honest に答える。

---

## 2. Q1 — 新規性の自己評価

### 2.1 ✅ 残る (= 主張可能な) 新規性

| 要素 | 評価 | 根拠 |
|---|---|---|
| **per-axis Bayes posterior expected-loss constraint を MILP に組込** | ◯ 中程度 | DRO や Robust LP 系で「posterior を constraint に直接入れる」formulation は VPP / DER siting 文献に確認できない。Acceptance sampling (Dodge 1929) の MILP 拡張として位置づけ |
| **Theorem 2 (prior-independent uniform expected-loss bound)** | ◯ 中程度 | try11 Theorem 1 の Bayes posterior 形式 (= prior 依存) を超える uniform bound。設計者が θ で直接制御できるという形式は構成的 |
| **Selection bias 現象の発見 + 構造的解決の対比** | ◯ 中程度 | try11 で empirical 発見 + try12 で設計的解消、という 2 paper の組合せで論理が完結 |
| **per-EV 実データでの統計有意な実証** | ◯ 弱〜中 | ACN-Data 72-cell sweep で kerber_landnetz の SLA 違反 71% → 47% を CI 完全分離で実証、Sensitivity sweep で θ=0.01 → 0% を実測 |

### 2.2 ❌ 新規性なし (= 撤回 or 修辞のみ)

| 要素 | 理由 |
|---|---|
| Trigger-orthogonal MILP 自体 | try11 の貢献、try12 では reuse |
| Sentinel mechanism analogy | try11 の修辞、try12 での load-bearing なし |
| Acceptance sampling との analogy | 説明上の助けだが、技術的 contribution の中身 (= MILP 拡張) は独立 |

### 2.3 PWRS reviewer 視点での評価

**PWRS / IEEE T-SG 投稿 ready 観点**:

- **Methodology** (= core MILP 拡張): ✅ 立つ
- **Theorem** (= Theorem 2 の prior-independent bound): ✅ 立つ、Bernstein 拡張で深化可能
- **Empirical** (= 単一 feeder で statistical significance): △ kerber_landnetz でしか clean win が出ていない、cigre_lv は両者同等、kerber_dorf は両者 V_disp 100%
- **Generalisability**: △ 1 dataset (ACN), 1 month, 1 site (caltech) のみ
- **Comparison breadth**: △ M9 vs M1 のみ、M3b/M3c/M4b/M5/M6/B1-B6 との比較は未実施

→ **MAJOR REVISION で再投稿水準** (PWRS の novelty bar は超えるが empirical breadth と comparison が不足)

---

## 3. Q2 — 定量効果の自己評価

### 3.1 ✅ Statistical significance で立つ findings

| Finding | データ | 評価 |
|---|---|---|
| **kerber_landnetz default θ=0.05: M9 SLA 71% → 47% (24.5pt 低減)** | ACN 72-cell, multi-week × multi-pairing, bootstrap 95% CI [39.49, 53.72] vs M1 [67.12, 74.72] | **CI 完全分離** → ◯ |
| **kerber_landnetz θ=0.01-0.02: M9 SLA 71% → 0.00%** | Sensitivity 348-cell, M9 [0.00, 0.00] vs M1 [67.13, 74.61] | **CI 完全分離** → ◎ |
| **Cost overhead +2.8% (default θ) / +5.6% (sweet spot θ)** | 同上 | 決定論的、運用上 negligible |
| **ε mis-spec robustness**: θ=0.01-0.02 で ε ∈ [0.01, 0.10] 全範囲 SLA 0% | MS-5 grid sweep | ◯ |

### 3.2 ⚠️ 定量効果が出なかった findings (= scope の限界)

| 期待した finding | 実態 |
|---|---|
| Synthetic sweep (MS-3) で M9 統計有意に勝つ | M9 [0.16, 0.34] vs M1 [0.28, 0.49]、CI 端で 0.06pt 重なる = **境界** (= statistically not significant at 0.05 level) |
| cigre_lv で M9 vs M1 差別化 | 両者 SLA 0% / V_disp 0% (= operating regime が easy) |
| kerber_dorf で M9 が grid 違反を解消 | 両者 V_disp 100% (= M9 は grid 制約を持たない、M9-grid 必要) |
| OOD gap での差 | 両者 0.14-0.15% で同等 (= OOD 性能は M1 と区別できず) |

### 3.3 PWRS reviewer 視点での評価 (定量編)

**期待: M9 が複数 (feeder, operating point) で M1 を CI 分離で beat**:
- ✅ kerber_landnetz default: 24.5pt 低減、CI 完全分離
- ✅ kerber_landnetz sweet spot θ=0.01: **71pt 低減 (71% → 0%)**、CI 完全分離
- △ Synthetic overall: 14pt 低減だが CI 端で重なる
- × cigre_lv / kerber_dorf: 効果なし

**Headline 定量 effect**: kerber_landnetz の SLA 71% → 0% (sweet spot θ) が論文の central finding。これは **single feeder × single operating point** だが、CI 完全分離で empirical 主張は立つ。

---

## 4. mvp_review_policy §4.2 観点別

### A. 方針適合性 (= 前提、これが NG なら他不問)

| 項目 | 判定 |
|---|---|
| gridflow 自体を contribution として主張していないか | ✅ **適合**。Abstract / §1 / §3 / §4 / §8 で gridflow framework を contribution として一切主張していない (§5 Methodology で "implementation" として言及のみ) |
| 課題出典が査読論文の Future Work か | ✅ try11 (前 cycle) の N-2 finding を出典、それ自体は research_landscape に紐づく |

### B. 数値の信頼性

| 項目 | 判定 |
|---|---|
| 全数値が JSON / CSV から転記 | ✅ `results/try12_m1_vs_m9_synthetic.json` `try12_m1_vs_m9_acn.json` `try12_sensitivity.json` から全数値を引いている |
| Bootstrap CI 算出方法明示 | ✅ percentile bootstrap, n_boot=2000、`run_*.py` 各 _bootstrap_ci 関数で実装 |
| 再現性 | ✅ ACN data sha256 pin、pool seed=0 固定、week × pairing 軸明示 |

### C. 整合性

| 項目 | 判定 |
|---|---|
| ideation_record / report.md の主張一貫性 | ✅ ideation S7 で提案した M9 を §4 で formal、§6 で empirical、§4.7 で theoretical で展開 |
| Theorem と sweep 結果の整合 | ✅ Theorem 2 が予測する「θ_k で expected loss 制御可」を MS-5 で実測確認 (θ=0.01 → SLA 0%) |
| try11 N-2 finding の引用 | ✅ §1.1 / §2.4 で empirical motivation として引用 |

### D. 完成度

| 項目 | 判定 |
|---|---|
| 実装 (sdp_bayes_robust.py) が動作 | ✅ smoke test pass、3 sweep 完走 (564 cells 計) |
| Limitations 明示 | ✅ §7.4 で prior 推定誤差 / multi-axis correlated noise / grid 複合 を明記 |
| Future Work 明示 | ✅ §8.2 で M9-grid / Pecan Street / multi-axis correlated 列挙 |

### E. Top venue 水準 (PWRS / IEEE T-SG)

| 項目 | 判定 |
|---|---|
| Theory contribution | ✅ Theorem 2 (prior-independent bound) は独立貢献 |
| Empirical breadth | △ 1 dataset / 1 month / 1 site / 1 feeder で clean win |
| Comparison breadth | △ M9 vs M1 のみ、B 群との multi-method 比較は未実施 |
| Reproducibility | ✅ sha256 pin + git history |
| Headline stability | ✅ 本 cycle 内で数値 freeze、try13 へ revision 委ね (FROZEN rule の自己懲戒は try11 で学習済み、try12 では適用しない方針) |

---

## 5. 総合判定

**Recommendation: 条件付き合格 (Major Revision で PWRS / IEEE T-SG 投稿可能性あり)**

**強み**:
- ✅ Theorem 2 (prior-independent bound) は構造的独立貢献
- ✅ kerber_landnetz θ=0.01 で SLA 71% → 0% は CI 完全分離で立つ headline finding
- ✅ Selection bias を try11 で発見 → try12 で設計的解消、という論理構造が完結
- ✅ 564-cell sweep で empirical 主張が CI 付きで再現可能

**弱み (= Phase 2 = try13 で対応すべき)**:
- ❌ 1 feeder (kerber_landnetz) でのみ clean win、cigre_lv / kerber_dorf では効果なし
- ❌ Synthetic sweep の 14pt 改善は CI 境界 (statistically not significant)
- ❌ B1-B6 baseline との multi-method 比較未実施
- ❌ ACN は 1 month / 1 site (caltech) のみ、Pecan Street registration / multi-month 拡張要

**total: 「PWRS 論文の単独貢献 candidate」としては立つが、「published 可能水準」には empirical breadth が不足**。

→ **Plan**: try13 で (a) M9-grid + (b) multi-feeder × multi-method × Pecan Street で empirical breadth を確立、PWRS revision 投稿 readiness を完成。

---

## 6. ユーザー (PO) への report

- **新規性**: ◯ あり。Theorem 2 (prior-independent bound) + per-axis Bayes posterior MILP constraint は VPP / DER siting 文献に independent contribution
- **定量効果**: ◯ 出ている。kerber_landnetz θ=0.01 で **SLA 71% → 0% (CI [0,0] 完全分離)、cost +5.6% のみ**。M9 の core claim (= MILP selection bias を構造的に防ぐ) を empirical に確認
- **published readiness**: △ Major Revision 級。Theorem は publish 水準、empirical breadth は不足 → try13 で拡張要

**try12 は MVP cycle として成功**: try11 で発見した design 欠陥を (理論 + 実装 + 実証) で構造的に解消する筋を完成し、PWRS 投稿 readiness の半分 (theory + 1 cell empirical) を達成した。残り半分 (multi-feeder × multi-method × multi-data empirical) は try13 で扱う。

---

## 7. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-30 | 初版。Phase 2 self-review + 新規性 / 定量効果の自己評価。総合判定: 条件付き合格、try13 で empirical 拡張継続 |
