# try13 Phase 2 Self-Review + Self-Assessment

実施: 2026-04-30
評価対象: `report.md` ・`m9_grid_tools/*.py` ・`results/try13_*.json`

---

## Q1: 新規性はあるか?

**◯ あり (中程度)**

| 要素 | 評価 |
|---|---|
| **M9-grid MILP 統合** | ◯ 中程度 — try11 M7 + try12 M9 を単一 MILP に統合した formulation。VPP / DER siting 文献に "trigger-orth + Bayes-robust + DistFlow 全部" を同時に解く先行確認できず |
| **Multi-method bootstrap CI 比較** | ◯ 弱〜中 — 7 method × 4 dataset × 3 feeder は VPP literature 標準を超える比較範囲 |
| **Multi-month/site ACN 実証** | ◯ 弱 — 4242 sessions × 4 dataset は試行範囲拡大、ただし caltech-dominated |
| Theorem 2/3 (try12 継承) | △ — 本 try13 では新規性なし、try12 のものを継承 |

## Q2: 定量的に評価できているか?

**◯ できている (強い結果)**

### Statistical significance で立つ findings (CI 完全分離)

| Finding | データ | 根拠 |
|---|---|---|
| **kerber_dorf で M9-grid 単独勝者** | ACN 168 cells | M9-grid SLA 0% / V_disp 0% / ¥4,900 vs M1 V_disp 100%, M7 SLA 34.3% [27.2, 42.4], M9 V_disp 100%, B1/B4 ¥6,000 — CI 完全分離 |
| **B 系 (B1/B4/B5) が ACN 実データで全部破綻** | ACN 168 cells | cigre_lv B1: 96.2 [91.9, 99.8]%, B5 全 feeder で 41-96% SLA fail |
| **Synthetic でも kerber_dorf M9-grid 単独勝者** | 63 cells | 0.2% / 0% / ¥4,600 — M9-grid 唯一 |

### Mixed findings

- cigre_lv: 全 MILP 系同等 (= operating regime が constraint 効かない)
- kerber_landnetz: M9 / M9-grid / M7 同点 (M9 cheap、grid constraint 非効果)
- cigre_lv α=0.70 strict で M7/M9-grid infeasible (= 正直な envelope 限界報告)

---

## Q3: PWRS publication readiness

**△ Major Revision 級** (try12 と同水準だが empirical breadth は改善)

### 強み
- ✅ 7-method × 4-dataset × 3-feeder = **231 cells** で 1 cell の statistically significant 単独勝者 (kerber_dorf M9-grid)
- ✅ B1/B4/B5 baseline 全て CI で破綻、cost-loss frontier で M9-grid が支配
- ✅ M9-grid = "3 軸同時保証" の唯一構成という framing が複数 sweep で支持
- ✅ Theorem 2/3 (try12 継承) で theory contribution あり

### 弱み (= try14 で対応)
- ❌ kerber_dorf でしか単独勝者、他 feeder で tied or infeasible
- ❌ ACN 4 dataset は caltech-dominated (3/4)、site variance 不足
- ❌ Pecan Street (residential) は依然未取得 — workplace ACN との phase 違いが reviewer の懸念
- ❌ MV feeder (IEEE 13/34) 未実装 — LV demo feeder のみ

---

## §3.1 適合確認

✅ Abstract / §1 / §3 / §4 / §8 で gridflow framework を contribution として claim していない。Methodology section で "implementation" としてのみ言及。

---

## 総合判定

**条件付き合格 v3** (try11 M-1〜M-6 + try12 N-1/N-2 + try13 7-method 比較で 3 cycle 累積貢献):
- Theory: try12 Theorem 2/3 + try13 M9-grid 統合 = published 水準
- Empirical: kerber_dorf 単独勝者 = MAJOR REVISION 級
- 残課題: try14 で Pecan Street + MV feeder + IEEE 13/34 を扱うべき

**MVP cycle としての到達点**: try11 → try12 → try13 の 3 cycle で:
1. trigger-orth MILP の発明
2. Bayes-robust constraint の発見
3. M9-grid 統合 + multi-method/data 比較

の論理が完結し、PWRS / IEEE T-SG 投稿の **theoretical + empirical 両面の contribution candidate** を構成。empirical breadth を try14 で完成すれば revision 投稿水準に到達する見込み。
