# 第4章 処理フロー設計（シーケンス図・アクティビティ図）

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（4.1〜4.5） |

---

## 4.1 処理フロー一覧

**関連要件**: REQ-001〜REQ-010

| フローID | 対応UC | フロー名 | 図の種類 |
|---|---|---|---|
| DD-SEQ-001 | UC-01 | シナリオ実行 | シーケンス図+アクティビティ図 |
| DD-SEQ-002 | UC-02 | Scenario Pack作成・登録 | シーケンス図 |
| DD-SEQ-003 | UC-03 | ベンチマーク実行 | シーケンス図 |
| DD-SEQ-004 | UC-04 | バッチ実行 | シーケンス図+アクティビティ図+バッチ処理設計 |
| DD-SEQ-005 | UC-05 | 結果エクスポート | シーケンス図 |
| DD-SEQ-006 | UC-06 | コネクタ管理 | シーケンス図 |
| DD-SEQ-007 | UC-07 | メトリクス定義管理 | シーケンス図 |
| DD-SEQ-008 | UC-08 | 実験比較 | シーケンス図 |
| DD-SEQ-009 | UC-09 | 設定管理 | シーケンス図 |
| DD-SEQ-010 | UC-10 | ログ・監視 | シーケンス図 |
| DD-SEQ-012 | — | エラーハンドリング共通フロー | アクティビティ図 |
| DD-SEQ-013 | — | コンテナライフサイクル管理 | シーケンス図+状態遷移図 |
| DD-SEQ-014 | — | CDLデータ変換パイプライン | アクティビティ図 |
| DD-SEQ-015 | — | プラグイン読み込みフロー | シーケンス図 |

---

## 4.2 シナリオ実行フロー（UC-01）

**関連要件**: REQ-001

### 登場オブジェクト

- **Researcher** — 研究者（アクター）
- **CLIApp** — CLIエントリポイント
- **Orchestrator** — 実行オーケストレータ
- **ExecutionPlan** — 実行計画
- **ContainerManager** — コネクタコンテナ管理
- **OpenDSSConnector** — OpenDSS用コネクタ
- **DataTranslator** — CDL変換
- **CDLRepository** — CDLデータ永続化
- **BenchmarkHarness** — ベンチマーク評価

### IPO

| 項目 | 内容 |
|---|---|
| **Input** | `gridflow run <pack>` コマンド引数（pack: `str` — Scenario Packパスまたはpack_id） |
| **Process** | Pack読み込み → ExecutionPlan生成 → コンテナ起動 → ステップ順次実行 → CDL変換・保存 → ベンチマーク評価 |
| **Output** | `ExperimentResult`（実験結果オブジェクト） / 例外: `PackNotFoundError`, `ContainerStartupError`, `StepExecutionError` |

### シーケンス図

```mermaid
sequenceDiagram
    actor R as Researcher
    participant CLI as CLIApp
    participant ORC as Orchestrator
    participant EP as ExecutionPlan
    participant CM as ContainerManager
    participant CON as OpenDSSConnector
    participant DT as DataTranslator
    participant CDL as CDLRepository
    participant BH as BenchmarkHarness

    R->>CLI: gridflow run <pack>
    CLI->>CLI: load_scenario_pack(pack)
    CLI->>ORC: execute(scenario_pack)
    ORC->>EP: create(scenario_pack)
    EP-->>ORC: execution_plan

    ORC->>CM: start_container(connector_type)
    CM->>CON: コンテナ起動
    CON-->>CM: ready
    CM-->>ORC: container_handle

    loop 各ステップ (step in execution_plan.steps)
        ORC->>CON: execute(step)
        CON-->>ORC: StepResult
        ORC->>DT: to_canonical(step_result)
        DT-->>ORC: CDLData
        ORC->>CDL: store(cdl_data)
        CDL-->>ORC: ok
    end

    ORC->>BH: run(experiment_id)
    BH->>CDL: load_results(experiment_id)
    CDL-->>BH: cdl_data_list
    BH-->>ORC: BenchmarkReport

    ORC->>CM: stop_container(container_handle)
    CM->>CON: コンテナ停止
    CON-->>CM: stopped

    ORC-->>CLI: ExperimentResult
    CLI-->>R: 結果表示
```

### アクティビティ図（ステップループの分岐・エラー時フロー）

```mermaid
flowchart TD
    A([開始: gridflow run pack]) --> B[Scenario Pack読み込み]
    B --> C{Pack有効?}
    C -- No --> ERR1[PackNotFoundError発生]
    ERR1 --> Z([終了: エラー])
    C -- Yes --> D[ExecutionPlan生成]
    D --> E[コンテナ起動]
    E --> F{起動成功?}
    F -- No --> ERR2[ContainerStartupError発生]
    ERR2 --> Z
    F -- Yes --> G[次のステップ取得]
    G --> H{ステップ残あり?}
    H -- No --> L[BenchmarkHarness.run]
    H -- Yes --> I[Connector.execute step]
    I --> J{実行成功?}
    J -- No --> K[StepExecutionError記録]
    K --> M{リトライ可能?}
    M -- Yes --> I
    M -- No --> N[コンテナ停止]
    N --> Z
    J -- Yes --> O[DataTranslator.to_canonical]
    O --> P[CDLRepository.store]
    P --> G
    L --> Q[結果集約・表示]
    Q --> R[コンテナ停止]
    R --> S([終了: 正常完了])
```

---

## 4.3 Scenario Pack 作成・登録フロー（UC-02）

**関連要件**: REQ-002

### 登場オブジェクト

- **Researcher** — 研究者（アクター）
- **CLIApp** — CLIエントリポイント
- **ScenarioRegistry** — シナリオ管理レジストリ
- **PackMetadata** — Packメタデータ

### IPO

| 項目 | 内容 |
|---|---|
| **Input** | `gridflow scenario create <name> --template <tmpl>` / `gridflow scenario validate <path>` / `gridflow scenario register <path>` （name: `str`, tmpl: `str`, path: `Path`） |
| **Process** | テンプレートからディレクトリ生成 → スキーマ検証 → Registry登録 → pack_id発行 |
| **Output** | `pack_id: str`（登録時） / `ValidationResult`（検証時） / 例外: `TemplateNotFoundError`, `SchemaValidationError`, `RegistrationError` |

### シーケンス図

```mermaid
sequenceDiagram
    actor R as Researcher
    participant CLI as CLIApp
    participant SR as ScenarioRegistry
    participant PM as PackMetadata

    Note over R,PM: フェーズ1: Scenario Pack作成
    R->>CLI: gridflow scenario create <name> --template <tmpl>
    CLI->>SR: create_from_template(name, tmpl)
    SR->>SR: テンプレート検索・読み込み
    SR->>SR: ディレクトリ構造生成
    SR-->>CLI: 作成パス
    CLI-->>R: Pack作成完了

    Note over R,PM: フェーズ2: バリデーション
    R->>CLI: gridflow scenario validate <path>
    CLI->>PM: load(path)
    PM-->>CLI: pack_metadata
    CLI->>SR: validate(pack_metadata)
    SR->>SR: スキーマ検証
    SR-->>CLI: ValidationResult
    CLI-->>R: 検証結果表示

    Note over R,PM: フェーズ3: 登録
    R->>CLI: gridflow scenario register <path>
    CLI->>PM: load(path)
    PM-->>CLI: pack_metadata
    CLI->>SR: register(pack_metadata)
    SR->>SR: 重複チェック
    SR->>SR: pack_id発行
    SR-->>CLI: pack_id
    CLI-->>R: 登録完了（pack_id表示）
```

---

## 4.4 ベンチマーク実行フロー（UC-03）

**関連要件**: REQ-003

### 登場オブジェクト

- **Researcher** — 研究者（アクター）
- **CLIApp** — CLIエントリポイント
- **BenchmarkHarness** — ベンチマーク実行管理
- **CDLRepository** — CDLデータ永続化
- **MetricCalculator** — メトリクス計算（Strategyパターン）
- **BenchmarkReport** — ベンチマーク結果レポート
- **ReportGenerator** — レポート出力

### IPO

| 項目 | 内容 |
|---|---|
| **Input** | `gridflow benchmark run <exp_id> [--metrics voltage_deviation,thermal_overload]`（exp_id: `str`, metrics: `list[str]`（省略時は全メトリクス）） |
| **Process** | CDLから実験結果取得 → Strategyパターンでメトリクス計算 → レポート生成 → 出力 |
| **Output** | `BenchmarkReport` / ファイルエクスポート（CSV, JSON等） / 例外: `ExperimentNotFoundError`, `MetricCalculationError` |

### シーケンス図

```mermaid
sequenceDiagram
    actor R as Researcher
    participant CLI as CLIApp
    participant BH as BenchmarkHarness
    participant CDL as CDLRepository
    participant MC as MetricCalculator
    participant BR as BenchmarkReport
    participant RG as ReportGenerator

    R->>CLI: gridflow benchmark run <exp_id> --metrics m1,m2
    CLI->>BH: run(experiment_ids, metric_names)
    BH->>CDL: load_results(experiment_ids)
    CDL-->>BH: cdl_data_list

    loop 各メトリクス (metric in metric_names)
        BH->>MC: calculate(metric, cdl_data_list)
        Note right of MC: Strategyパターンで<br/>メトリクス種別ごとの<br/>計算ロジックを選択
        MC-->>BH: MetricResult
    end

    BH->>BR: create(metric_results)
    BR-->>BH: benchmark_report

    BH->>RG: generate(benchmark_report, format)
    RG-->>BH: formatted_output

    BH-->>CLI: BenchmarkReport
    CLI-->>R: 結果表示 or ファイルエクスポート
```

---

## 4.5 バッチ実行フロー（UC-04）

**関連要件**: REQ-004

### 登場オブジェクト

- **Researcher** — 研究者（アクター）
- **CLIApp** — CLIエントリポイント
- **Orchestrator** — 実行オーケストレータ
- **ExecutionPlan** — 実行計画（複数生成）
- **ContainerManager** — コネクタコンテナ管理（並列度制御）
- **OpenDSSConnector** — OpenDSS用コネクタ（複数インスタンス）
- **CDLRepository** — CDLデータ永続化

### IPO

| 項目 | 内容 |
|---|---|
| **Input** | `gridflow run <pack> --batch --sweep param=v1,v2,v3`（pack: `str`, sweep: `dict[str, list[Any]]`） |
| **Process** | パラメータ組合せ展開 → ExecutionPlan群生成 → 並列度制御付きコンテナ起動 → 並列ステップ実行 → 結果集約 |
| **Output** | `BatchResult`（全実験結果 + サマリ） / 例外: `ParameterExpansionError`, `BatchExecutionError` |

### シーケンス図

```mermaid
sequenceDiagram
    actor R as Researcher
    participant CLI as CLIApp
    participant ORC as Orchestrator
    participant EP as ExecutionPlan
    participant CM as ContainerManager
    participant CON as OpenDSSConnector
    participant CDL as CDLRepository

    R->>CLI: gridflow run <pack> --batch --sweep param=v1,v2,v3
    CLI->>ORC: execute_batch(scenario_pack, sweep_params)

    ORC->>ORC: パラメータ組合せ展開
    ORC->>EP: create_multiple(scenario_pack, param_combinations)
    EP-->>ORC: execution_plans[]

    loop 各実験 (plan in execution_plans, 並列度上限: max_parallel)
        ORC->>CM: start_container(connector_type)
        CM->>CON: コンテナ起動
        CON-->>CM: ready
        CM-->>ORC: container_handle

        loop 各ステップ (step in plan.steps)
            ORC->>CON: execute(step)
            CON-->>ORC: StepResult
            ORC->>CDL: store(cdl_data)
            CDL-->>ORC: ok
        end

        ORC->>CM: stop_container(container_handle)
        CM-->>ORC: stopped
    end

    ORC->>ORC: 結果集約・サマリ生成
    ORC-->>CLI: BatchResult
    CLI-->>R: バッチ結果表示
```

### アクティビティ図（並列実行・分岐・エラー時フロー）

```mermaid
flowchart TD
    A([開始: gridflow run pack --batch]) --> B[パラメータスイープ定義解析]
    B --> C[パラメータ組合せ展開]
    C --> D[ExecutionPlan群生成]
    D --> E{未実行プランあり?}
    E -- No --> M[結果集約]
    E -- Yes --> F{並列度上限未満?}
    F -- No --> G[実行中の実験完了を待機]
    G --> F
    F -- Yes --> H[コンテナ起動・実験開始]
    H --> I[ステップ順次実行]
    I --> J{ステップ成功?}
    J -- Yes --> K{全ステップ完了?}
    K -- No --> I
    K -- Yes --> L[実験結果をCDLに保存]
    L --> E
    J -- No --> N[失敗記録・コンテナ停止]
    N --> O[失敗実験をスキップ]
    O --> E
    M --> P[サマリレポート生成]
    P --> Q{失敗実験あり?}
    Q -- Yes --> R[失敗一覧をレポートに付加]
    R --> S([終了: バッチ完了])
    Q -- No --> S
```

### バッチ処理設計表

| 項目 | 内容 |
|---|---|
| 入力データ | Scenario Pack + パラメータスイープ定義 |
| 加工処理 | パラメータ展開 → 実験計画生成 → 並列実行 → 結果収集 |
| 出力データ | 実験結果群（CDL形式）+ サマリレポート |
| スケジュール | 即時実行（CLIトリガー） |
| 異常時処理 | 失敗実験をスキップし残りを継続、失敗一覧をレポート |
