# try14 — Phase 2 Self-Review + Self-Assessment

実施: 2026-04-30
評価対象: `report.md` ・`tools14/*.py` ・`results/try14_breadth.json`

## Q1: 新規性

**△ 弱〜中** (try13 から限定的に拡張)

| 要素 | 評価 |
|---|---|
| **M9-grid-soft** (slack-penalised) | △ 弱 — slack 化は技術として平凡、但し M9-grid の hard 制約版が見つけ損ねていた feasible region を発見する効用あり |
| **CIGRE MV feeder 統合** | × — pandapower 同梱を import するだけ、新規貢献ではない |
| **ACN phase-invert (residential proxy)** | △ 弱 — semantic 反転の技法、PMS Street 取得への bridge として価値ありだが novel methodology ではない |
| 7-method (try13) → 8-method (try14) 比較 | × — sweep range の単純拡張 |

→ **try14 単独では novel contribution は限定的**。本来は try13 で確立した M9-grid を validate する補強実験 + Limitations 章を強化する役割。

## Q2: 定量効果

**△ Mixed (positive + negative)**

### Positive findings (CI 完全分離)
- kerber_dorf workplace で M9-grid / M9-grid-soft の単独勝者を multi-week (4 weeks × 4 methods × bootstrap CI) で再確認
- M9-grid-soft が cigre_lv で feasible (slack=0、hard と同解、infeasibility は CBC の局所最適で誤検出だった可能性)

### Negative findings
- **MV scale (cigre_mv) で全 MILP method infeasible** — try13 の "deployable" 主張を弱める明確な negative result
- Residential phase で controller 差別化されない (= phase は影響弱い)

### 総合
- **kerber_dorf workplace** が依然唯一の M9-grid 単独勝者 cell
- 4 feeder × 2 phase = 8 cell-phase 組合せ中、**M9-grid 単独勝者 = 2 (kerber_dorf workplace, kerber_dorf residential)**

## Q3: PWRS 投稿可能性

**△ Major Revision 級 (try13 と同水準、限界を明示)**

### 強み (try11→12→13→14 累積)
- Theory: try12 Theorem 2 (prior-independent uniform bound)
- Empirical: kerber_dorf で 4 cycle 累積 256+ cells で M9-grid 単独勝者の再現性
- Honest reporting: MV scale 限界、residential phase での controller 等価性、cigre_lv α=0.70 の M9-grid-soft fix

### 弱み (Phase 2 = try15)
- **MV scale で deploy 不可** = 商用 VPP に直接適用できない、論文の applicability claim が弱まる
- Pecan Street (真の residential) 未取得
- B 系比較で B4/B5 が **MV では cost ¥180-198k** で over-buy 戦略は MV scale で破綻 (= 既存 baseline も商用 scale で機能しない、本研究の問題設定自体の妥当性が疑われ得る)

### 提案論文の core claim (try14 時点)
> 「LV scale + workplace VPP + kerber_dorf-class operating regime で、M9-grid (try13) / M9-grid-soft (try14) は trigger-orth + Bayes-robust + DistFlow grid を単一 MILP で同時保証する初の構成。商用 MV scale への deploy は本研究の範囲外で、Phase 2 で扱う。」

honest だが scope が limited。

## §3.1 適合確認

✅ Abstract / §1 / §3 / §4 で gridflow framework を contribution として claim していない。

## 総合判定

**条件付き合格 v4** (try11 + try12 + try13 + try14 で累積)。

PWRS / IEEE T-SG での publish には **(a) MV scale 問題の解決** か **(b) LV scale + workplace VPP に scope を絞った正直な workshop / e-Energy 級論文** のいずれか。後者が現実的。

## try15 への引継

- (i) M8 (active+standby joint) を MV scale に拡張 — baseline V_min を active 配置で repair
- (ii) SimBench MV / IEEE 13/34 OpenDSS feeder を import
- (iii) Pecan Street registration (PO 行動)
- (iv) MV scale SLA / burst sizing の再 calibration (= 50 MVA で α=0.30 ではなく 0.10 等)

---

## 後日訂正: Rule 6 (Fixation 打破) 違反だった事実の記録

実施: 2026-04-30 後段 (try15 立ち上げ時)

`docs/mvp_review_policy.md` §2.5.2 Rule 6 を再読の結果、try11→12→13→14
は **同一 paradigm (= trigger-orthogonal MILP set-cover) に MILP 制約を
1 個ずつ追加する 4 連続の改善案** であり、Rule 6 が定める「同方向 3 連続
で強制転換」に明確に違反していた。本来は try12 の Phase 0.5 で Rule 7
(乱数アンカリング) → Rule 1 (≥10 候補, ranking なし) → Rule 9 v2 (≥ 3
遠隔ドメイン並列 + invariant 検査) を実行し、MILP **以外** の paradigm を
強制すべきだった。

**訂正方針**: 本 try (12 / 13 / 14) は **try11 の Phase D-revisited
拡張群** として位置づけ直し、独立 MVP cycle としては count しない。
真の意味で次の MVP cycle となるのは **try15** であり、そこで Rule 7
からやり直す。

本 try で発見した数値 (Theorem 2 の prior-independent bound、kerber_dorf
での M9-grid 単独勝者、cigre_mv での MILP infeasibility 等) は
削除しない — これらは try11 の補強 evidence として有効。だが「独立した
MVP cycle」と称した先行記述は誤りで、Rule 6 違反の自己診断として
本記録を残す。
