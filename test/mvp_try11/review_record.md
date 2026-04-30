# try11 Phase 2 査読記録

実施: 2026-04-29
査読者: 仮想 (gridflow research collective, IEEE PES GM 想定水準)
対象: `test/mvp_try11/report.md`
基準: `docs/mvp_review_policy.md` §4 査読ガイドライン (A〜E 観点 + リフレーズ §4.5)

---

## 論文主張のリフレーズ (mvp_review_policy.md §4.5) — F-M2 改訂版

- **課題**: 仮想発電所 (VPP) が補助サービス契約に提供する DER pool は外部因果トリガー (通勤時刻・気象・市場・通信障害) で同期離脱するため重尾 burst churn が発生し、独立同分布仮定下の確率/学習ベース手法は新規/同時トリガー下で SLA 違反に至る

- **先行研究**: VPP の reliability 問題は 6 系統で扱われたが、いずれも **共通因果ドライバー** を構造的に扱わない。金融分野の Rodriguez Dominguez 2025 (CPCM) は continuous-PDE 設定で causal portfolio を sophisticated 化したが、VPP の discrete DER 選択 / SLA tail / jump-driven 動学には subsume されない

- **方法 (提案手法の価値)**: **Causal-Trigger Orthogonal Portfolio (CTOP, sentinel-inspired)** — DER の物理因果トリガー曝露ベクトル化 + active pool 曝露集合との直交制約 + 容量被覆制約からなる MILP。Rule 9 v2 で動物行動学の sentinel 機構を 5 候補から機械的選定。CPCM との 5 軸構造差分。理論面で Theorem 1-3 (Pareto-optimality / greedy ln K+1 倍 / label noise 境界) を確立

- **実験結果 (F-M2)**: **3 feeders (CIGRE LV / Kerber Dorf / Kerber Landnetz) × scale=200 × 8 trace (C1-C8) × 15 method × 3 seed = 1080 cells**:
  - **CTOP (M1) は ¥3,500/月で 0.38% mean violation**、B1/B4/B6 (¥6,000) より **40% 安い** Pareto-dominance
  - **C7 相関反転**: CTOP test 違反 0.00% (gap −1.79%)、B5 (correlation) のみ test +0.40% で崩壊
  - **C8 scarce orthogonal**: CTOP ¥3,500 で 0.17% vs baselines ¥6,000 で 0% (= 71% 高コスト)
  - B5 全 trace 平均 3.15% で破綻、CPCM 簡易版の限界実証
  - C4 基底外: 全手法 ~0.5-1.1% degrade (CTOP は detection-friendly)
  - **CTOP の grid 制約違反**: cigre_lv で 96% voltage 違反 (集中配置由来) — grid-aware 拡張が future work
  - 計算: CTOP 0.013s vs SP/DRO 5s = **400 倍高速**

- **考察**: F-M1 結果 (= same-cost tied) を F-M2 の per-feeder VPP 構成で前進させ、**CTOP の Pareto-dominance を確立**。残る最重要課題は grid-aware 拡張 (voltage 制約を MILP 組込)

---

## 総合判定 (C3 / C2 改訂版 — F-M2 + Grid-aware + Dataset framework + Phase D 改訂)

**判定: 条件付き合格 (Phase D 拡張で投稿水準に到達見込み、large-scale sweep + 長期間 real-data は Phase 2 必須)**

先行リビジョンでは「合格 (top venue 水準)」と判定していたが、Phase D レビュー (NEXT_STEPS.md) で以下の倫理的問題が明らかになり、本リビジョンで判定を **格下げ** した:

1. relaxed bound (V_max=1.10, L_max=120%) 下の measurement を ANSI C84.1 strict (1.05) 規格と暗黙比較していた
2. voltage_violation_ratio が **baseline-only** (既存負荷起因; controller は原理的に repair 不能) と **dispatch_induced** (controller の責任) の合算であり、reviewer に controller の責任として読まれる過大評価だった
3. 「12% への低減 = 5× reduction」という headline が上記 (1)(2) の caveat なしで提示されていた

Phase D-1〜D-6 実装で上記を構造的に解消する tooling を揃えた (詳細は report.md §8.7.3)。さらに **Phase D-5 follow-up (本リビジョン後半)** で実 CAISO データ (OASIS API: `SLD_FCST` v1, RTM 5Min, CA ISO-TAC, 2024-01-01 → 01-08, 2015 timestamps, 15.1–27.7 GW) を取得し、kerber_dorf における M7-strict 動作を実データ × ANSI strict envelope で検証: **SLA 違反 0.0000%, dispatch-induced voltage 違反 0.0000%, 0.985 ≤ V ≤ 1.036 pu で 0.95 ≤ V ≤ 1.05 envelope を clear**。これは PWRS reviewer C2 への構造的回答であり、`MS-D5` smoke test の real-data leg が sha256 pin で再現性を保証する。残るは **Phase 2 commit cycle での large-scale sweep (D-2 strict-bound F-M2 / D-4 full envelope / 1 ヶ月以上の real-data 期間延長 / AEMO・Pecan Street registration ベース取得)** を完遂すれば top-venue 投稿水準に到達する見込み。

### C3 部分解消 (relaxed-bound 12% → Phase D で内訳分離 / strict-bound へ移行)

新変種 M7 (Grid-aware CTOP) を実装:
- `tools/grid_impact.py`: per-feeder voltage / line impact 行列 (DistFlow 線形近似、1 kW probe)
- `tools/sdp_grid_aware.py`: M7 MILP solver、TriOrth + capacity coverage + voltage / line constraints
- F-M2 mini-sweep (360 cells, **relaxed bound V_max=1.10**) で M7 vs M1 比較:

| metric | M1 | M7 | 改善 (relaxed bound) |
|---|---:|---:|---:|
| SLA 違反 | 0.38% | **0.23%** | -39% |
| Voltage 違反 (合算, V_max=1.10) | 61.40% | 12.38% | 5× reduction *under relaxed bound* |
| Cost | ¥3,500 | ¥3,500 | 同等 |
| Solve time | 0.011s | 0.097s | 8.8× |

**先行リビジョンで「5× reduction」と表現した数値は relaxed bound 下の合算値であり、`tools/_msD1_smoke_test.py` で内訳分離した結果 cigre_lv 代表セルでは baseline_only ≈ 100% / dispatch_induced ≈ 0% が判明した** (controller は新たな違反をゼロ件しか作らず、12% は構造的に repair 不能な feeder design 起因)。

Phase D 拡張群:
- D-1: voltage 違反 metric を baseline_only / dispatch_induced に分離 (`grid_metrics.py`)
- D-2: ANSI C84.1 strict envelope (V_max=1.05) を default 化、`solve_sdp_grid_aware_soft` で常時 feasible な M7-soft を追加 (slack 統計でどれだけ規格を緩めたか定量化)
- D-3: M8 = active+standby joint MILP (`sdp_full_milp.py`)、active 配置自体を grid-aware 化
- D-4: (feeder, α, β) feasibility envelope sweep tooling (`run_envelope.py` / `aggregate_envelope.py`)
- D-5: real-data trace adapter (`real_data_trace.py`) + CAISO OASIS fetcher (`fetch_caiso.py`)、demo CSV で end-to-end 検証済み
- D-6: multi-scale scaling sweep tooling (`run_scaling.py` / `plot_scaling.py`)、Theorem 2 検証用

PWRS reviewer C3 (deployable でない) は **「Phase D 拡張群で構造的に解消する経路は揃った」** が、final strict-bound sweep 実走による reporting は Phase 2 で完遂する。

### C2 部分解消 (real-data framework + 6 loaders + demo fixtures)

PWRS reviewer C2 (合成データのみは PWRS 水準で不十分) に対し:

#### 実装した基盤
- `src/gridflow/domain/dataset/`: Dataset / Loader / Registry の Protocol + frozen value objects
- `src/gridflow/adapter/dataset/`: 6 loader (Synthetic / Pecan Street / CAISO / AEMO Tesla VPP / JEPX / NREL ResStock)
- `src/gridflow/infra/dataset/`: InMemory + Filesystem Registry
- `src/gridflow/adapter/dataset/scenario_bridge.py`: Dataset → ScenarioPack 統合

#### Repository 貢献規則
- `docs/dataset_contribution.md`: 6-step contribution checklist + governance rules
- `docs/dataset_catalog.md`: 登録 dataset カタログ (initial: synthetic only)
- 41 test 全 pass (`tests/dataset/`)

#### Demo fixture と pipeline end-to-end 検証
- `test/mvp_try11/data/caiso_system_load_demo.csv` (59KB, published schema 一致)
- `test/mvp_try11/data/aemo_tesla_vpp_demo.csv` (346KB, AEMO VPP report 構造)
- `tools/_msC2_6_smoke_test.py`: CAISO/AEMO/Synthetic loader 並行検証 pass

**残タスク**: 実 CSV そのものの取得は contributor 委託 (実環境制約により本実装サイクルでは fetch 不可)。framework は完成、contributor が `$GRIDFLOW_DATASET_ROOT` に drop すれば即動作。これは MODERATE (mod-C2) として 残置:

### 残る MODERATE (top venue 投稿前推奨)
1. **mod-C2 実 CSV 取得**: contributor が Pecan Street (registration) / CAISO / AEMO を実取得して sweep 再実行
2. **mod-A1 Multi-scale**: scale=50/1000/5000 で MILP / greedy トレードオフ実測

`mvp_review_policy.md` §4.3 厳密適用で:

`mvp_review_policy.md` §4.3 基準:
- A (核要件): ✅ 合格
- B/C/D に CRITICAL/MAJOR なし → 基本合格基準達成
- E (top venue): 先行リビジョンでは「MAJOR ×0 のため top venue 水準合格」と判定していたが、本リビジョンで「relaxed bound 下 12%」「baseline-only / dispatch-induced 内訳未分離」が headline として誤解を招く水準であったため **「条件付き合格 (Phase D 拡張で投稿水準到達見込み)」** に格下げ。Phase D 実装は本リビジョンで全 6 sub-phase 完了 (smoke test 付き) しており、Phase 2 で final sweep 実走 + report 数値置換を完遂すれば top venue 水準に到達する

F-M1 で指摘された MAJOR 2 件は F-M2 で解消:

### F-M2 で解消された MAJOR 指摘
1. **M-1 数値的 strict dominance の不在** (旧 §4.2 D-1): F-M2 の per-feeder VPP 設計で **CTOP は cost で baseline (B1/B4/B6) を 40% 下回る Pareto-dominance** を達成 (§6.1 F1)。F-M1 の "tied" は single-feeder 大規模 SLA 設定の特殊性
2. **M-2 単一 feeder / 単一 scale 検証** (旧 §4.2 E-2): 3 feeders (CIGRE LV / Kerber Dorf / Kerber Landnetz) で 1080 cells 検証完了

### 残る MODERATE 指摘 (top venue 投稿前に対処推奨)
1. **mod-A1 Multi-scale 検証部分的**: scale=200 のみ。$N \in \{50, 1000, 5000\}$ への拡張で MILP / greedy トレードオフ実測が望ましい
2. **mod-A2 Grid-aware CTOP は future work**: CTOP の集中配置が cigre_lv で 96% voltage 違反 (§6.2 F7)。論文では future work として明示し、Phase 2 で MILP に voltage 制約組込の拡張を実装

### F-M2 改訂サマリ

| 観点 | F-M1 (270 cells) | F-M2 (1080 cells) |
|---|---|---|
| Cost dominance | tied (¥18,000 同一) | **CTOP ¥3,500 vs baselines ¥6,000 (40% 安)** |
| C7 correlation reversal | 未テスト | **CTOP gap −1.79%, B5 +0.40%** で構造優位実証 |
| C8 scarce orthogonal | 未テスト | **CTOP cost-Pareto 優位** (¥3,500 vs ¥6,000) |
| Multi-feeder | 単一 | **3 feeders (CIGRE LV / Kerber Dorf / Kerber Landnetz)** |
| Theoretical | なし | **Theorem 1-3** (Pareto / greedy / noise) |
| 命名 | Sentinel-DER Portfolio | **Causal-Trigger Orthogonal Portfolio (CTOP)** |
| Total judgment | 条件付き合格 (MAJOR ×2) | **条件付き合格 (Phase D 拡張で投稿水準到達見込み, final sweep 実走必須)** |

---

## A. 核要件 (gridflow-as-tool / 査読 §4.2 A)

### A-1 gridflow を contribution として主張していないか?

**判定: ✅ 合格**

論文 §1.4 contribution 列挙、§4 method、§9 conclusion のいずれも gridflow を contribution として記述していない。gridflow は実装・実験記録の基盤として §5.2 で言及されるが、論文の主張 ("contribution") は SDP 手法そのものに限定されている。`mvp_review_policy.md` §3.1 違反なし。

### A-2 ideation が Rule 1〜9 を経由しているか?

**判定: ✅ 合格**

`ideation_record.md` を確認:
- **Rule 7** (乱数 anchor): §1 で sundial / cetacean / kabuki anchor を transparent に記録
- **Rule 1** (HAI-CDP): §6.1 で 5 候補を ranking なしで列挙
- **Rule 2** (Ordinary persona): 本 try では明示的 persona 表は省略 (Rule 8 + 9 で十分カバー)
- **Rule 3** (CoT 4 ステップ): §3 (S0-S8 深掘り) で実質的に CoT を実施
- **Rule 4** (Extreme user): §8 反証パターンで業界 reviewer の amplified need を扱う
- **Rule 5** (TRIZ 妥協なし): §6 で 5 候補から D を脱落させる「妥協なき解の決定」
- **Rule 6** (Fixation 監視): try10 phyllo の失敗教訓を §0 で踏襲、別軸 (= portfolio + 因果) に切替
- **Rule 7-9 v2**: 上記の通り全工程明示

### A-3 Novelty Gate (9 項目) を通過しているか?

**判定: ✅ 合格**

`ideation_record.md` §9 で 9/9 通過を確認。当初 #2 (先行文献) と #7 (乱数 anchor) を🟡/🟠としていたが、PO 提供の CPCM 文献を §4.5b で構造差分明示し、Rule 7 と Rule 9 の policy 上の関係を再読して両方とも 🟢 に修正済み。`mvp_review_policy.md` §2.5.3 の「1 つでも ❌ なら戻る」を満たす。

---

## B. 学術品質 (査読 §4.2 B)

### B-1 問題定義が査読論文水準で明確か?

**判定: ✅ 合格**

§1 Introduction で:
- 課題 (重尾 burst churn) を §1.1 で具体的トリガー名 + 物理メカニズムで記述
- §1.2 で既存 6 系統の限界を表で構造化
- §1.4 で 4 つの contribution を箇条書き
- §3.4 で最重要先行 (CPCM) との 5 軸構造差分を表で明示

§3.1-3.4 で系統 A-F 各々に代表文献を引用。

### B-2 因果トリガー基底の妥当性

**判定: ⚠️ MODERATE 指摘 (mod-1)**

論文 §4.1 で K=4 基底 (commute / weather / market / comm_fault) を提示し、§5.1.1 で各 DER 種別に default 曝露を割り当てるが、**この基底が "physically enumerable" であるという主張の根拠**が論文中で明示されていない。査読者は「regulatory 軸 (C4) を含めれば K=5、その他にもあるかもしれない」と反論可能。

**修正提案**: §4.1 に "trigger basis 設計指針" のサブセクションを追加し、(a) どの粒度で基底軸を切るか、(b) 新規軸出現時の検出 + 拡張プロトコル (§6.4 を強化) を文章化。

### B-3 SDP MILP の最適性

**判定: ✅ 合格**

§4.4 で MILP の standard form (binary + linear constraint) を明示。CBC は exact solver なので、与えられた基底・burst 値下で大域最適解を返す。これは MILP の標準性質で additional 証明不要。greedy (M4b) は heuristic と明示。

---

## C. 整合性 (査読 §4.2 C)

### C-1 ideation_record と report.md の主張一貫性

**判定: ✅ 合格**

`ideation_record.md` §6 (Rule 9 v2) と report.md §4.6 (sentinel 選定経路) が **5 候補 + invariant 表 + 機械的脱落** で一致。S8 (= trigger-orthogonal portfolio under heavy-tailed burst churn) と report §1.3 が一致。

### C-2 §4.5b CPCM 構造差分と §6 実験結果の整合

**判定: ⚠️ MODERATE 指摘 (mod-2)**

§4.5b (a) で「CPCM は filtering で driver 推定、SDP は物理 enumerate」と主張し、§6.1 F3 で「B5 (簡易 causal portfolio) は強制 diversification で破綻」と報告したが、**B5 実装は CPCM ではなく Lopez de Prado 流の PC アルゴリズム簡易版** (`baselines/b5_financial_causal.py` の docstring 参照)。CPCM 自体の VPP への適用は本研究で未実装。

**修正提案**:
- §3.4.2 末尾と §5.1.6 baseline 表に「B5 は CPCM の核要素である PDE control / nonlinear filtering を**含まない**簡易版」と明記
- §9.1 future work に「CPCM full implementation の VPP 適用」を追加

### C-3 §1.4 主要主張と §6.1 結果の整合

**判定: ⚠️ MAJOR 指摘 (M-1, ←既出)**

§1.4 contribution 4 は「baseline と同 cost で 0.19% 違反」「label noise 10% 下で 0.15%」を実証主張しており、これは §6.1 F2/F4 と整合する。しかし **論文タイトル + abstract の暗黙トーン**は SDP の優位性を示唆しており、reviewer から「同等性しか示していない」と批判される余地。

**修正提案** (M-1):
- abstract 末尾を「**構造的保証** (= label noise 頑健性 + detection-friendly OOD failure) を獲得しつつ baseline と同 cost / 同性能を達成」と慎重化
- §1.4 contribution 4 を「Pareto-optimal な ¥18,000-0.19% 点に SDP が到達することを実証」と表現

### C-4 trace 設計と claim の整合

**判定: ✅ 合格**

§5.1.4 で C1-C6 と「外挿 (1)/(2)」の対応を明示。§6.4 で C4 を "外挿 (2) graceful failure" として独立分析。

---

## D. 完成度 (査読 §4.2 D)

### D-1 数値性能 vs 構造的保証の整理

**判定: ⚠️ MAJOR 指摘 (M-1, ←既出)**

§7.1 で率直に「Pareto-strict dominance は良性条件下では未確立」と認めており、誠実な姿勢は評価可。しかし論文 §1 / §6.1 / §9 の言語を **「同等」「構造的保証」「detection-friendly」** に統一する編集修正が必要。

### D-2 反証可能性 (5.1.5 評価指標 + §6.4 OOD 解析)

**判定: ✅ 合格**

`ideation_record.md` §5.5 の P1-P4 (= burst trigger 多様性 / OOD 頻度 / 同時発火 / label noise) を C1-C6 trace で具体的に検証。M3c の脆弱性 (6.15%) や B5 の高違反 (5.09%) も **隠さず報告** している。

### D-3 図表の充実

**判定: ⚠️ MODERATE 指摘 (mod-3)**

論文 §6 は表中心で図がない。reviewer は plotted Pareto frontier (cost vs violation) や per-trace box plot を期待する。

**修正提案**: `results/plots/` 配下に matplotlib で以下を生成:
- `pareto_cost_violation.png` (15 method × 6 trace の散布図)
- `per_trace_violation_box.png` (method × trace の violation ratio box plot)
- `ood_gap_bar.png` (method 別の C4 vs C1 の bar)

### D-4 計算性能の報告

**判定: ✅ 合格**

§7.6 で variant 別の solve time を表で報告。MILP 0.2-0.4 秒 / cell は実用域、SP/DRO の 5-30 秒との差を明示。

---

## E. Top venue 水準 (査読 §4.2 E, IEEE PES GM 想定)

### E-1 Theoretical novelty depth

**判定: ⚠️ MAJOR 指摘 (M-2 関連 + new)**

SDP は MILP 形式の portfolio 問題で、**理論的な新規性は構造化** (= 既存 portfolio に causal axis 制約を追加) **に留まる**。Top venue (IEEE Trans. Power Systems / Smart Grid 等) は以下を要請:

- 理論的最適性証明 (例: SDP 解と CPCM 解の関係定理)
- 漸近解析 (N → ∞ 時の計算量・性能)
- 実 VPP データでの検証

本稿は (a) (b) を欠き、(c) は synthetic trace のみ。Top venue 水準には未達、PES GM workshop または Applied Energy / Energies (rapid review) が想定 venue。

### E-2 複数 feeder / 複数 scale 検証

**判定: ❌ MAJOR 指摘 (M-2, ←既出)**

§8.5 / §8.2 で限界として認めるが、`mvp_review_policy.md` §4.2 E-2 が要請する複数 feeder 検証は未実施。

**修正計画**:
- Phase 2 で CIGRE LV / Kerber 30 / Dickert の 3 feeder で aggregate output が grid 制約 (1.05 / 0.95 pu) 下に収まるかを検証
- N = 50, 200, 1000, 5000 の 4 scale で M1 / M4b の挙動差を測定

### E-3 学術 community 受容性

**判定: ⚠️ MODERATE 指摘 (mod-4)**

`Sentinel-DER Portfolio` という命名は動物行動学の比喩を残し、学術 community での受容性に懸念。**実装と理論は健全** だが、命名を `Causal-Trigger Orthogonal Portfolio (CTOP)` 等の technical な表記に揃える方が査読通過率が高い。

**修正提案**: タイトルと abstract を `Causal-Trigger Orthogonal Portfolio for Virtual Power Plant Standby Design (with Sentinel-Inspired Heuristic)` 等に変更し、sentinel 比喩は §4.6 (動機) に格下げ。

---

## 修正計画 (条件付き合格 → 合格に向けて)

### 必須 (MAJOR 解消)

| # | 内容 | 該当節 | 工数目安 |
|---|---|---|---|
| F-M1 | 数値同等性に統一した言語修正 (abstract / §1.4 / §9) | 主に編集 | 1 日 |
| F-M2 | 複数 feeder + 複数 scale 実験追加 | §5.1 + §6 拡張 | 1 週間 |

### 強く推奨 (MODERATE 解消)

| # | 内容 | 工数目安 |
|---|---|---|
| F-mod1 | trigger basis 設計指針サブセクション追加 (§4.1) | 半日 |
| F-mod2 | B5 が CPCM 簡易版である旨を §3.4.2 / §5.1.6 / §9.1 に明記 | 半日 |
| F-mod3 | matplotlib プロット 3 種を生成 + 論文に図示 | 1 日 |
| F-mod4 | タイトル + abstract を CTOP 軸に変更 (sentinel は §4.6 動機へ) | 1 日 |

合計: MAJOR 2 件解消で **合格** (mvp_review_policy.md §4.3 「条件付き合格 = MAJOR 1 件以下」より厳密)、MODERATE 4 件追加解消で **Top venue 水準合格** に近づく。

---

## ゼロベース PWRS 査読 (本リビジョン後半、Phase D-5 follow-up 完了後)

**実施**: 2026-04-30。Phase D-7 で「条件付き合格」と判定したが、PO 依頼により **PWRS reviewer ゼロベース観点** で再評価。先行レビュー (C2/C3) を含む全 commit 履歴を破棄し、提出論文を初見として読む reviewer の視点で記述。

**判定 (本査読): Major Revision (再投稿時 desk reject 可能性あり)**

技術労力 (Phase D-1〜D-7 全実装) は相当だが、論文として top venue に掲載されるには以下の MAJOR 6 件 / MODERATE 7 件 / MINOR 4 件で根本的再構成が必要。

### MAJOR (= Top venue 不可 / Phase 2 commit cycle では解決不能)

#### M-1 「実データ検証」が semantic non-sequitur (C2 への対応失敗)

§8.7.5 の headline "real CAISO validation, dispatch_induced 0.0000%" は、論文の主張と取得データの間に **物理的因果関係が皆無**:

- 取得データ: California ISO 系統全体の `SLD_FCST` (system-level demand **forecast**, 15-28 GW)
- 検証対象: 200-DER の住宅 pool が **kerber_dorf** (ドイツ仕様 0.4 MVA 配電 LV feeder) 上で動作
- マッピング: load > μ+σ となる時間帯を `weather` トリガー event として inject

すなわち (i) California 系統需要 ≠ ドイツ LV 配電網の DER 個別 churn、(ii) forecast ≠ realized、(iii) trigger axis "weather" の semantic はマッピング過程で消失。**「実データを取得した」事実と「実データで controller を validate した」事実は別物**。

**Ask**: DER 個別 availability を直接測定したデータ (Pecan Street individual unit log / AEMO Tesla VPP per-unit) で再検証。できないなら "real-data validation" の主張を撤回し "pipeline ready for real data" に弱体化。

#### M-2 "0.0000% violation" は構造的に trivial (検証として無情報)

kerber_dorf 0.4 MVA、SLA=200 kW、active=140 kW (20 EVs)、min_avail=163/200 という設定では **どんな controller でも 0% 違反**。 0.985-1.036 pu はドイツ低圧 400V radial の物理的 normal range であり、自動的に達成される。

**Ask**: 同実データに M1/B1/B4/B6 を流し、controller 間で差が出る operating point を特定。違反 > 0 を生む高 α/高 β の test を §8.7.5 に追加。

#### M-3 統計的有意性の欠如 / sample size 1 / no error bars

§8.7.5 = 1 feeder × 1 method × 7 日 × 1 seed。CI 算出不能。§6.1 主結果も n=9 (3 feeder × 3 seed) で mean のみ、std/CI なし。「40% コスト削減」は ¥3,500 vs ¥6,000 の整数倍関係 (= MILP 整数粒度の人工的階段) で、連続化すると差は 1-2 機の utility_battery 選択。

**Ask**: 全 headline に mean ± 95% CI、各 cell n≥30、実データは複数週/複数 method/複数 feeder。

#### M-4 関連研究 (DER siting / VVO / PCC voltage control) の survey 欠落

M7 の DistFlow 線形化 + per-DER 配置最適化は **DER siting / VVO** の中核問題。Atwa 2010, Borges 2006, Quezada 2006, Farivar-Low 2013, Lavaei-Low 2012 等の蓄積文献を **§3 で 1 つも引用していない**。M7 は Borges 2006 の直接派生。

**Ask**: §3 に DER siting / VVO サブセクション追加、M7 の positioning を「causal portfolio」から「trigger-orthogonal DER siting」に書き直し。

#### M-5 理論貢献 (Theorem 1-3) の独立性ほぼゼロ

- **Thm 1 (Pareto-optimality)**: min-cost MILP の自明性質。新規性ゼロ
- **Thm 2 (greedy ln K + 1)**: Chvátal 1979 weighted set cover の transcription。reduction 自体が sketchy
- **Thm 3 (label noise bound)**: `ε · Σ cap_j` は Markov 不等式の素朴適用、直交性構造を利用していない

**Ask**: Thm 1 削除、Thm 2 は引用扱い、Thm 3 は直交性活用 bound に書き直し or 削除。真の新規性は (K, N, topology) の feasibility frontier closed-form 等。

#### M-6 査読対応の度に headline が動く (judgment instability)

96% → 12% → 0% と数字が振れ、reviewer は **どれが真の主張か判断不能**。

**Ask**: 実装と評価を凍結してから論文を書く。改訂のたびに本質的主張が変わるなら、それは論文ではなく WIP。

### MODERATE

- **mod-1 Forecast vs Realized**: SLD_FCST は予測値で滑らか。realized (ENE_HASP) で再検証
- **mod-2 再現性**: CAISO API 仕様変更耐性ゼロ。Zenodo / OSF DOI で snapshot deposit
- **mod-3 B5 strawman**: PDE control / nonlinear filtering 含まない簡易版を CPCM 比較として使用 → §3.4 で B5 = "ablation" と honestly に位置づけ
- **mod-4 burst 量の経験的根拠不足**: `burst = (commute=SLA, weather=0.30·SLA, ...)` の割合は arbitrary。実 VPP 経験分布 or sensitivity sweep 必要
- **mod-5 直交性 ablation 欠如**: M0 = "min cost s.t. capacity coverage only" 比較が必要
- **mod-6 LV demo feeder で「deployable」主張**: IEEE 123-bus MV または SimBench MV feeder に拡張
- **mod-7 計算時間 "400× 高速" は不公平比較**: deterministic CTOP vs uncertainty-set SP/DRO は問題が違う。同じ uncertainty model 下で再比較

### MINOR

- **min-1 `weather` default**: CAISO 系統 spike は典型的に commute (duck curve)。default を commute に
- **min-2 Theorem 2 実測 5x ギャップ**: 事後説明的。$N=5000$ 検証完了まで定理 declare 保留
- **min-3 `feeder_active_pool` 決定論的 first-N**: ランダム性 sensitivity を §5.1.2 に明示
- **min-4 train/test split の clamp**: 実データ 7 日では train=6/test=1、OOD 検証は実質不能。明記要

### 最低限の Phase 2 ToDo (再投稿可能水準)

1. **CAISO ENE_HASP realized load を ≥ 30 日取得**、kerber_dorf 以外の **MV feeder** で **M1/M4b/B1/B4/B6 全比較** + mean ± 95% CI
2. **Pecan Street / AEMO DER 個別 availability** を実取得、trigger axis の semantic と整合
3. §3 に DER siting / VVO 文献群を追加、positioning 書き直し
4. Thm 1 削除、Thm 3 を直交性活用 bound に再構築
5. 実装と評価を凍結してから論文を書く

これは Phase D 拡張群の追加 sweep では解決せず、**実データ source の選定変更 + 文献 positioning の根本書換 + 統計設計の見直し** が必要。本セッションでは **try12 として別 cycle で扱うべき大きさ**。

### 本査読の判定根拠

- (Phase D 後判定) 条件付き合格 (Phase D 拡張で投稿水準到達見込み) → (本査読) Major Revision
- 差分: Phase D 拡張は技術 tooling は揃えたが、**論文全体の一貫性 / semantic / 統計設計 / 文献 positioning** に手を入れていない。これらは tooling の追加では解決しない論文構築品質の問題

---

## 査読まとめ

- **A 合格** (gridflow を contribution として主張せず、ideation 全 Rule 経由、Novelty Gate 9/9)
- **B 合格 (MODERATE 1)** (問題定義明確、トリガー基底根拠強化が望ましい)
- **C 合格 (MAJOR 1, MODERATE 1)** (主張トーン慎重化、B5 が CPCM 簡易版である旨追記)
- **D 合格 (MAJOR 1, MODERATE 1)** (数値同等性の率直記述、図表強化)
- **E 未達 (MAJOR 1, MODERATE 1)** (複数 feeder + 複数 scale 検証、命名)

**判定**: 条件付き合格 (MAJOR ×2 を F-M1 / F-M2 で解消すれば合格)

PO への提案: 本 Phase 1 の成果を以下に分岐:
1. **(a) F-M1 + F-mod1〜4 を即時実施** (1-2 日工数) → workshop / Applied Energy 投稿水準
2. **(b) F-M1 + F-M2 + 全 mod を実施** (約 2 週間工数) → Top venue 投稿水準
3. **(c) Phase 1 を try11 結果として確定し、try12 で別問題に進む** (= 候補 1 / 候補 3 を扱う)

---


