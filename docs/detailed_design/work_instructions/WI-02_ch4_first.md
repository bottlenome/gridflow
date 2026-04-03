# WI-02: 第4章前半（4.1〜4.5）

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/04_process_flow.md` を新規作成
**共通ルール**: `WI-00_common.md` 参照

冒頭:
```markdown
# 第4章 処理フロー設計（シーケンス図・アクティビティ図）
## 更新履歴
| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（4.1〜4.5） |
```

---

## 4.1 処理フロー一覧

以下のフロー一覧表を作成:

| フローID | 対応UC | フロー名 | 図の種類 |
|---|---|---|---|
| DD-SEQ-001 | UC-01 | シナリオ実行 | シーケンス図+アクティビティ図 |
| DD-SEQ-002 | UC-02 | Scenario Pack作成・登録 | シーケンス図 |
| DD-SEQ-003 | UC-03 | ベンチマーク実行 | シーケンス図 |
| DD-SEQ-004 | UC-04 | バッチ実行 | シーケンス図+アクティビティ図+バッチ処理設計 |
| ...（UC-05〜UC-10、4.12〜4.15も一覧に含める） |

---

## 4.2 シナリオ実行フロー（UC-01）

### 登場オブジェクト
Researcher, CLIApp, Orchestrator, ExecutionPlan, ContainerManager, OpenDSSConnector, DataTranslator, CDLRepository, BenchmarkHarness

### フロー概要
1. Researcher が `gridflow run <pack>` を実行
2. CLIApp がScenarioPackを読み込み、Orchestratorに渡す
3. Orchestrator がExecutionPlanを生成
4. ContainerManager がConnectorコンテナを起動
5. ステップループ: Connector.execute(step) → StepResult → DataTranslator.to_canonical() → CDLRepository.store()
6. 全ステップ完了後、BenchmarkHarness.run() で評価
7. 結果をCLIに返却・表示

### 必要な図
- Mermaid sequenceDiagram（上記フローをメッセージレベルで）
- Mermaid flowchart（ステップループの分岐・エラー時フロー）

---

## 4.3 Scenario Pack 作成・登録フロー（UC-02）

### フロー概要
1. `gridflow scenario create <name> --template <tmpl>`
2. CLIApp → ScenarioRegistry.create_from_template()
3. テンプレートからディレクトリ構造生成
4. `gridflow scenario validate <path>` → PackMetadata読み込み → スキーマ検証
5. `gridflow scenario register <path>` → Registry登録 → pack_id発行

Mermaid sequenceDiagramで記述。

---

## 4.4 ベンチマーク実行フロー（UC-03）

### フロー概要
1. `gridflow benchmark run <exp_id> [--metrics voltage_deviation,thermal_overload]`
2. CLIApp → BenchmarkHarness.run(experiment_ids, metric_names)
3. CDLRepositoryから実験結果取得
4. MetricCalculator群でメトリクス計算（Strategyパターン）
5. BenchmarkReport生成
6. ReportGenerator.generate(report, format)
7. CLI出力 or ファイルエクスポート

Mermaid sequenceDiagramで記述。

---

## 4.5 バッチ実行フロー（UC-04）

### フロー概要
1. `gridflow run <pack> --batch --sweep param=v1,v2,v3`
2. Orchestrator がパラメータ組合せからExecutionPlan群を生成
3. ContainerManagerが並列度上限（max_parallel）に従い順次起動
4. 各実験のステップループを並列実行
5. 全実験完了後、結果集約

### 必要な図
- Mermaid sequenceDiagram（コンテナ起動・実行・終了）
- Mermaid flowchart（並列実行・分岐・エラー時フロー）
- バッチ処理設計表:

| 項目 | 内容 |
|---|---|
| 入力データ | Scenario Pack + パラメータスイープ定義 |
| 加工処理 | パラメータ展開→実験計画生成→並列実行→結果収集 |
| 出力データ | 実験結果群（CDL形式）+ サマリレポート |
| スケジュール | 即時実行（CLIトリガー） |
| 異常時処理 | 失敗実験をスキップし残りを継続、失敗一覧をレポート |
