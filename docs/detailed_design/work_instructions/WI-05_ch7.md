# WI-05: 第7章 アルゴリズム設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/07_algorithm.md` を新規作成
**共通ルール**: `WI-00_common.md` 参照

冒頭:
```markdown
# 第7章 アルゴリズム設計
## 更新履歴
| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |
```

---

## 7.1 時間同期アルゴリズム（REQ-F-002）

3方式を定義:

| 方式 | 対象Connector | 制御主体 |
|---|---|---|
| Orchestrator-driven | OpenDSS, pandapower | Orchestrator がステップタイミング決定 |
| Federation-driven | HELICS | HELICS Broker が時間管理 |
| Hybrid | 混合環境 | Orchestrator + HELICS Broker 連携 |

Orchestrator-drivenの疑似コード:
```
for step in range(total_steps):
    for connector in connectors:
        result = connector.execute(step, context)
        cdl_repo.store(experiment_id, step, result)
    context = update_context(results)
```

---

## 7.2 Benchmark メトリクス計算アルゴリズム（REQ-F-004）

8指標の計算式と疑似コード:

| 指標 | 計算式 |
|---|---|
| voltage_deviation | `max(abs(V_node - V_nominal) / V_nominal * 100)` [%] |
| thermal_overload_hours | `sum(dt for t in steps if I_branch > I_rated)` [h] |
| energy_not_supplied | `sum((P_demand - P_supplied) * dt for t in steps if P_supplied < P_demand)` [MWh] |
| dispatch_cost | `sum(P_gen * cost_per_unit * dt for gen in generators for t in steps)` [USD] |
| co2_emissions | `sum(P_gen * emission_factor * dt for gen in generators for t in steps)` [tCO2] |
| curtailment | `sum((P_available - P_dispatched) * dt for gen in renewables for t in steps)` [MWh] |
| restoration_time | `t_restored - t_fault` [s] |
| runtime | `t_end - t_start` [s] |

各指標の疑似コード（Python風）を記述すること。

---

## 7.3 バッチスケジューリングアルゴリズム（REQ-F-002）
- FIFO + 並列度制御（max_parallel設定値に従う）
- asyncio.Semaphore で並列数制限
- 疑似コード記述

## 7.4 Scenario Pack バージョン管理アルゴリズム（REQ-F-001）
- SemVer（MAJOR.MINOR.PATCH）
- content hash（SHA-256）で内容の同一性を検証
- バージョン比較・互換性チェックの疑似コード

## 7.5 Plugin 依存解決アルゴリズム（REQ-F-006）
- トポロジカルソート（DAG）で依存順序を決定
- 循環依存検出
- 疑似コード記述

## 7.6 性能設計（REQ-Q-010）
- 性能目標: gridflowオーバーヘッド < 外部ツール実行時間の5%
- 測定方法: runtime指標でオーバーヘッド計測
- ボトルネック対策: ファイルI/O最適化（Parquet）、コンテナ起動時間最小化（プリウォーム）、不要なデータコピー排除
- 最適化方針を表で整理
