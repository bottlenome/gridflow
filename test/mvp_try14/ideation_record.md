# try14 — Phase 0.5 Ideation + Phase 1 Plan

実施: 2026-04-30
シナリオ: VPP standby design (try11→12→13 継続)、PWRS revision 投稿水準到達
立ち上げ理由: try13 review_record で確定した残課題 3 件を構造的に解決

## 起点 — try13 で残った 3 課題

| # | 課題 | 影響 |
|---|---|---|
| (a) | cigre_lv α=0.70 strict envelope で M9-grid infeasible | 「他 feeder regime で破綻」reviewer の懸念 |
| (b) | ACN は caltech/JPL = workplace pattern、residential VPP は phase が逆 | 「真の home VPP で効くか」未検証 |
| (c) | 全実験が LV demo feeder (400V, 0.16-0.95 MVA)、商用 VPP は MV (4-22kV, 10-100 MVA) | 「deployable」主張に説得力なし |

## try14 の構造的解決

| # | 解決策 | 実装 |
|---|---|---|
| (a) | **M9-grid-soft**: Bayes posterior expected-loss を hard 制約から slack-penalised に → 常に feasible | `tools14/sdp_full_soft.py` |
| (b) | **ACN phase-invert**: 既存 ACN session を residential phase 用に semantic 反転 (= 在宅時=available) | `tools14/real_data_residential.py` |
| (c) | **CIGRE MV feeder**: pandapower 同梱の `create_cigre_network_mv()` (14-bus 22kV) を統合 | `tools14/feeders_mv.py` |

## Milestone

| MS | 内容 | 完了基準 |
|---|---|---|
| MS-1 | M9-grid-soft + smoke | cigre_lv α=0.70 strict で feasible、slack 統計を report |
| MS-2 | CIGRE MV feeder support | MV feeder で M1/M7/M9-grid-soft が解け、metric が finite |
| MS-3 | ACN phase-invert | residential proxy trace が朝 commute の active drop を再現 |
| MS-4 | 統合 sweep (LV+MV × workplace+residential × 7 method × bootstrap CI) | feeder/phase ごとの勝者順を CI で確定 |
| MS-5 | report.md + self-review | Q1/Q2 自己評価 + try14 published readiness 判定 |
