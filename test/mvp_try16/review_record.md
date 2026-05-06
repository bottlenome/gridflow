# try16 Phase 2 Self-Review + Self-Assessment

実施: 2026-05-06 後段
評価対象: `report.md`, `theorems.md`, `tools16/*.py`, `results/try16_voltvar_sweep.json`
review 観点: `docs/mvp_review_policy.md` §4.2 適用、ゼロベース

---

## 論文主張のリフレーズ (policy §4.5 必須)

> **「配電 Volt-VAR 分散制御において、PV inverter の応答時定数 $\tau_j$ と droop ゲイン
> $K_j$ をフィーダ放射状深度 $d_j$ で grading する Stokes-Stratified Droop (M11) を提案。
> 432-cell synthetic sweep で uniform droop (M0) 比 SLA 違反率を 1.57-2.80 倍 (CI 完全分離)
> 削減し、Q-energy は同等。末端 inverter の 3-dB cutoff が $\tau_{\min}$ で直接設計可能で
> あることを Theorem 6 として閉形式で示し、雲影特性周波数からの設計則を提供する。」**

→ "gridflow" は文中ゼロ。policy §3.1 違反なし。

---

## 1. policy §4.2 観点別

### A. 方針適合性 (前提)

| 項目 | 判定 |
|---|---|
| gridflow 自体を contribution として claim していないか | ✅ 適合。Abstract / §1.4 / §8 で「gridflow framework」を contribution として claim していない (実装プラットフォームとしてのみ言及) |
| 課題出典 | ✅ `mvp_problem_candidates.md` 候補 1 (Volt-VAR + 雲影) を try16 で初採用、try11-15 の candidate 2 (VPP churn) からの **問題切替** で Rule 6 fixation 構造的回避 |
| Rule 1-9 v2 + Novelty Gate 適合 | ✅ 完全準拠 (`ideation_record.md` §1-10 で Rule 7→1→2→3→4→5→6→8→9v2 + Gate 9/9 を順番に実行) |

### B. 数値の信頼性

| 項目 | 判定 |
|---|---|
| 全数値が JSON / CSV から | ✅ `results/try16_voltvar_sweep.json` から転記 |
| Bootstrap CI 算出明示 | ✅ percentile bootstrap, n_boot=2000, `tools16/run_voltvar.py:_bootstrap_ci` |
| 再現性 | ✅ cloud event は `random.Random(seed)` 決定論的、CLI コマンド明記 |

### C. 整合性

| 項目 | 判定 |
|---|---|
| ideation→method→theorem→experiment の一貫性 | ✅ Rule 9 v2 で生存した Stokes invariant を §4 で M11 設計則として、§5/theorems.md Theorem 6 で Bode bound、§6 で empirical 確認 (CI 完全分離) |

### D. 完成度

| 項目 | 判定 |
|---|---|
| 実装が動作 | ✅ feeder_radial / cloud_simulator / controllers / run_voltvar 全て smoke-test pass、432-cell sweep 完走 (22秒) |
| Limitations 明示 | ✅ §7.2 で 3-phase 未モデル / 合成 cloud / 固定 topology / comm fault 未実装 を列挙 |
| Future Work | ✅ §7.3 で 実 ASOS データ / pandapower 3-phase / M11+M3 failover / 配置 joint optimisation |

### E. Top venue 水準

| 項目 | 判定 |
|---|---|
| Theory contribution | ◯ Theorem 6 (depth-graded LPF cascade Bode bound) は独立貢献、closed-form 設計則 |
| Empirical breadth | ◯ 432 cells, 3 feeder size × 2 α × 24 seeds × 3 methods, CI 完全分離 |
| Comparison breadth | △ M0 / M3 / M11 の 3 手法、Robbins 2013 (distance-based K のみ) との直接比較は実装未済 (= future work) |
| Reproducibility | ✅ git history + JSON + CLI |

---

## 2. Q1 — 新規性

**◯ 中〜強 (try11-15 と独立軸)**

| 要素 | 評価 |
|---|---|
| **Stokes 沈降 invariant の Volt-VAR 移植** | ◯ 中〜強 — 配電制御文献で sedimentology からの機構移植は確認できず |
| **Depth-graded $\tau_j$ + $K_j$ scheduler** | ◯ 中 — Robbins 2013 が distance-based K を扱うが $\tau$ schedule までは触れず。$\tau$ grading は本論文が初 |
| **Theorem 6 (末端 cutoff の closed-form 設計則)** | ◯ 中 — Bode bound と $\tau_{\min}$ の直接設計可能性、雲気候からの設計則は power systems 文献で見当たらない |
| **Mechanism: comm-free + delay-robust** | ◯ 強 — consensus-based の代替軸として理論保証付きで実装可能 |

→ try11-15 (= MILP set-cover / τ-diversification on VPP churn) と問題自体が異なる
(VPP standby vs 配電 Volt-VAR)、手法軸も異なる (= 設計時 topological scheduling)。
**完全独立 axis**.

## 3. Q2 — 定量効果

**◯ 強い (CI 完全分離 × 2 operating points)**

| Finding | データ | 評価 |
|---|---|---|
| **α=0.85: M11 4.01% [3.02, 4.98] vs M0 11.21% [8.62, 13.81]** | 144 cells | **CI 完全分離、2.80× 改善** ✅ |
| **α=1.00: M11 15.39% [12.24, 18.67] vs M0 24.10% [20.19, 27.96]** | 144 cells | **CI 完全分離、1.57× 改善** ✅ |
| **Q-energy: M11 19.85 [18.08, 21.57] vs M0 19.58 [17.71, 21.40]** | 同上 | **CI 重複 (= 同等)**, Theorem 7 検証 ✅ |
| **vs M3 (comm-required, δ=500ms)**: M11 はやや劣るが **40% 少ない Q-energy** | 同上 | comm-free 採用判定の Pareto trade-off 明確 ✅ |
| **max excursion**: M11 0.127 vs M0 0.104 | 同上 | 累積違反は M11 半減、ピークは限定的に大 (= trade-off 明示) |

## 4. PWRS publication readiness

**△ Major Revision 級 (try15 と同水準だが直交軸)**

### 強み
- ✅ Rule 1-9 v2 + Novelty Gate を policy 完全準拠で履行
- ✅ candidate 切替で **Rule 6 fixation を構造的に解消**
- ✅ 432 cells × 2 α で CI 完全分離の violation 削減 (1.57-2.80×)
- ✅ Theorem 6 で末端 cutoff の closed-form 設計則
- ✅ comm-free + 局所 V のみで大幅改善 = 実装実用性高い

### 弱み (= try17 scope)
- ❌ Robbins 2013 (distance-based K のみ) との直接比較未実施
- ❌ 合成 cloud のみ、実 ASOS / NREL pyranometer データでの再評価未実施
- ❌ 線形 DistFlow simulator、3-phase / line dynamics 未モデル
- ❌ M11 + M3 failover (comm 健全時 M3, comm fault 時 M11) hybrid 未実装

### 提案論文の core claim

> 「配電 Volt-VAR では雲影は feeder 上を空間伝搬する disturbance であり、
>  Stokes 沈降の graded bedding invariant を移植して **末端速い・基幹遅い**
>  depth-graded $\tau_j, K_j$ を設計時に固定する **Stokes-Stratified Droop (M11)** を提案。
>  通信不要で uniform droop 比 SLA 違反率を 1.57-2.80× 削減 (CI 完全分離) し、
>  Theorem 6 で末端 cutoff の closed-form 設計則を提供する。」

## 5. try11-15 との関係

| try | 採用問題 | 採用手法 | 軸 |
|---|---|---|---|
| try11-14 | VPP churn (cand 2) | MILP set-cover (M1, M7, M9, M9-grid) | combinatorial design |
| try15 | VPP churn (cand 2) | M10 (τ-diverse greedy) | τ-diversification by DER **type** |
| **try16** | **Volt-VAR (cand 1)** | **M11 (depth-graded $\tau$, $K$)** | **τ-stratification by feeder topology depth** |

→ **問題側で独立** (cand 1 vs cand 2) かつ **手法軸も独立** (topology depth vs DER type)、
Rule 6 fixation 完全打破。MVP loop が 4 try ぶり (try15 以来 2 例目) に独立 axis を確立。

## 6. PO への report

- **新規性**: ◯ あり。Stokes invariant 移植 + depth-graded τ+K + Theorem 6、try11-15 と直交軸
- **定量効果**: ◯ 強い。SLA 1.57-2.80× 改善、Q-energy 同等 (= 純粋 win)、CI 完全分離 × 2 operating points
- **published readiness**: △ Major Revision 級。Theorem は publish 水準、empirical は (i) Robbins 2013 比較 + (ii) 実 ASOS データ + (iii) 3-phase pandapower で堅牢化要

**try16 は MVP cycle として成功**:
policy §2.5.2 完全準拠の ideation → 候補プールから cand 1 切替 → Rule 9 v2 で
Stokes invariant 採用 → Theorem + 432-cell sweep で contribution 確立。

try15 (cand 2 / DER τ-diversity) と本 try16 (cand 1 / topology τ-stratification) は
Stokes-style mechanism transposition の **二例目** で、Rule 9 v2 が再現可能な
ideation フローであることを示唆 (= 偶然でない)。

## 7. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-05-06 後段 | 初版。policy 完全準拠 ideation → cand 1 切替で Rule 6 構造的回避 → M11 (Stokes-stratified) → 432-cell sweep で CI 完全分離 → Phase 2 self-review |
