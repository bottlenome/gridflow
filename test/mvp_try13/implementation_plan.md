# try13 — Implementation Plan (Phase 1)

実施開始: 2026-04-30
ideation: `ideation_record.md`
立ち上げ理由: try12 self-review で確定した残課題 (= multi-feeder × multi-method × multi-data empirical breadth + M9-grid 統合) を解消

## Milestone 一覧

| MS | 内容 | 完了基準 |
|---|---|---|
| **MS-1** | M9-grid MILP (try11 sdp_grid_aware + try12 sdp_bayes_robust の統合) + smoke test | M9-grid が kerber_dorf で feasible、grid + Bayes 両方の constraint が effective |
| **MS-2** | ACN 多月 (Feb / Mar 2019) + 多 site (jpl / office001) 取得 | data/ に 5 つの sha256-pinned CSV |
| **MS-3** | 7-method synthetic sweep (M1, M7, M9, M9-grid, B1, B4, B5) | per-method bootstrap CI、cost-SLA-grid Pareto |
| **MS-4** | 7-method ACN sweep (multi-month × multi-site × multi-pairing) | per-(feeder, method) bootstrap CI、site / month variance |
| **MS-5** | report.md + Phase 2 self-review | Q1/Q2 自己評価 + try13 published readiness 判定 |

## ディレクトリ規則

- `m9_grid_tools/`: try13 新規モジュールのみ (try11/try12 から import)
- `data/`: try13 で取得した ACN multi-month/site CSV (try11 fixture も import 可)
- `results/`: 全 sweep records JSON / CSV
