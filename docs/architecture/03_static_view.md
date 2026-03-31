# 3. 静的ビュー

## 3.1 ブロック図（システムコンテキスト・サブシステム分割）

### 3.1.1 システムコンテキスト図

gridflow と外部システム・アクターの境界を示す。

```mermaid
graph TB
    subgraph External Actors
        R[Researcher<br>L1-L4]
        CI[CI/CD System]
        LLM[LLM Agent]
    end

    subgraph "External Systems"
        SIM1[OpenDSS]
        SIM2[HELICS]
        SIM3[pandapower]
        SIM4[GridLAB-D]
        SIM5[Grid2Op]
        REAL[実機 SCADA / HIL<br>将来]
        GH[GitHub<br>Scenario Pack 共有]
    end

    subgraph "gridflow"
        GF[gridflow Core]
    end

    R -->|CLI / Notebook / API| GF
    CI -->|CLI / API| GF
    LLM -->|CLI / API| GF

    GF -->|Connector Interface| SIM1
    GF -->|Connector Interface| SIM2
    GF -->|Connector Interface| SIM3
    GF -->|Connector Interface| SIM4
    GF -->|Connector Interface| SIM5
    GF -->|Connector Interface| REAL

    GF <-->|Scenario Pack import/export| GH
```

> **注:** Connector Interface はシミュレータ/実機を区別しない（AS-4）。全ての外部システムは同一インターフェースの異なる実装として接続される。

### 3.1.2 サブシステム分割（Clean Architecture レイヤー）

AS-2（Clean Architecture）に基づき、依存方向を「外側 → 内側」に統一する。AS-1（DDD）に基づき、各サブシステムは Bounded Context を形成する。

```mermaid
graph TB
    subgraph "Frameworks & Drivers（最外層）"
        Docker[Docker Runtime]
        FS[File System]
        ExtSys[External Systems<br>OpenDSS / HELICS / SCADA / ...]
    end

    subgraph "Interface Adapters（アダプタ層）"
        CLI[CLI Interface]
        NB[Notebook Bridge]
        WebUI[Web UI optional]
        CONN[Connector Implementations<br>OpenDSSConnector / HELICSConnector / ...]
        EXPORT[Data Export<br>CSV / JSON / Parquet]
        SCENIO[Scenario Pack I/O<br>ファイル読み書き・GitHub 連携]
    end

    subgraph "Use Cases（ユースケース層）"
        ORCH[Orchestrator<br>実行制御・時間同期・バッチ管理]
        BENCH[Benchmark Engine<br>評価指標算出・比較]
        SCENREG[Scenario Registry<br>登録・検索・バージョン管理]
        OBSV[Observability<br>ログ・トレース・メトリクス]
    end

    subgraph "Entities（ドメインモデル層 = CDL）"
        TOPO[Topology<br>系統構成]
        ASSET[Asset<br>設備・DER]
        TS[TimeSeries<br>時系列データ]
        EVENT[Event<br>イベント・操作]
        METRIC[Metric<br>評価指標]
        EXPMETA[ExperimentMetadata<br>実験メタデータ]
        SCENPACK[ScenarioPack<br>実験定義]
    end

    %% 依存方向: 外側 → 内側
    CLI --> ORCH
    CLI --> SCENREG
    CLI --> BENCH
    CLI --> OBSV
    NB --> ORCH
    NB --> BENCH
    CONN --> ORCH
    EXPORT --> METRIC
    EXPORT --> TS
    SCENIO --> SCENPACK

    ORCH --> SCENPACK
    ORCH --> TOPO
    ORCH --> TS
    ORCH --> EVENT
    BENCH --> METRIC
    BENCH --> TS
    SCENREG --> SCENPACK
    OBSV --> EVENT
    OBSV --> EXPMETA

    CONN -.->|implements| ExtSys
    CLI -.->|runs on| Docker
    SCENIO -.->|reads/writes| FS
```

### 3.1.3 Bounded Context の対応関係

| Bounded Context | Clean Architecture レイヤー | 責務 | 対応 FR |
|---|---|---|---|
| **Experiment Domain** | Entities | 電力系統実験のドメインモデル（Topology, Asset, TimeSeries, Event, Metric, ExperimentMetadata, ScenarioPack） | FR-01, FR-03 |
| **Orchestration** | Use Cases | 実験の実行制御。Scenario Pack のロード、Connector の初期化、ステップ実行、時間同期、結果収集 | FR-02 |
| **Evaluation** | Use Cases | 実験結果の評価。評価指標の算出、複数実験の比較、レポート生成 | FR-04 |
| **Scenario Management** | Use Cases | Scenario Pack の登録・検索・バージョン管理 | FR-01 |
| **Observability** | Use Cases | 実行ログ、トレース、KPI メトリクスの収集・提供 | QA-8 |
| **Connectors** | Interface Adapters | 外部システム（シミュレータ/実機）との接続。各 Connector が Orchestration の定義するインターフェースを実装 | FR-07 |
| **UX** | Interface Adapters | CLI、Notebook Bridge、Web UI。Use Cases 層を呼び出す窓口 | FR-05 |
| **Data Export** | Interface Adapters | CDL のデータを CSV/JSON/Parquet に変換して出力 | FR-03 |
| **Plugin System** | 横断 (Use Cases + Interface Adapters) | L1-L4 カスタムレイヤー。L1: Scenario Pack のパラメータ変更、L2: Use Cases 層への Plugin 注入、L3: Connector 追加、L4: ソース改変 | FR-06 |

---

## 3.2 クラス図（主要モジュールの内部構造・インターフェース）

### 3.2.1 Core Runtime（Orchestration Bounded Context）

```mermaid
classDiagram
    class Orchestrator {
        +run(scenario_pack_id: str, options: RunOptions) RunResult
        +run_from_step(scenario_pack_id: str, step: str, options: RunOptions) RunResult
        +status() OrchestratorStatus
        +shutdown() void
    }

    class RunOptions {
        +seed: int | None
        +dry_run: bool
        +parallel: bool
    }

    class RunResult {
        +experiment_id: str
        +status: RunStatus
        +steps: list~StepResult~
        +duration: timedelta
        +output_path: Path
    }

    class ExecutionPlan {
        +steps: list~ExecutionStep~
        +sync_strategy: SyncStrategy
        +generate(scenario_pack: ScenarioPack) ExecutionPlan
    }

    class ExecutionStep {
        +name: str
        +connector_id: str
        +inputs: dict
        +depends_on: list~str~
    }

    class Scheduler {
        <<interface>>
        +schedule(plan: ExecutionPlan) void
        +cancel() void
    }

    class SequentialScheduler {
        +schedule(plan: ExecutionPlan) void
        +cancel() void
    }

    class ConnectorInterface {
        <<interface>>
        +initialize(config: dict) void
        +execute(step: ExecutionStep, context: ExecutionContext) StepResult
        +health_check() HealthStatus
        +teardown() void
    }

    class ExecutionContext {
        +experiment_id: str
        +cdl: CanonicalDataLayer
        +logger: StructuredLogger
        +plugin_registry: PluginRegistry
    }

    Orchestrator --> ExecutionPlan
    Orchestrator --> Scheduler
    Orchestrator --> ConnectorInterface
    Orchestrator --> ExecutionContext
    ExecutionPlan --> ExecutionStep
    Scheduler <|.. SequentialScheduler
```

> **設計ポイント:**
> - `ConnectorInterface` は AS-4 により、シミュレータ/実機を区別しない
> - `Scheduler` はインターフェース（AS-2: DI）。P0 は `SequentialScheduler`、将来の並列実行は別実装で差替え
> - `ExecutionContext` に `PluginRegistry` を含め、L2 プラグインが実行時に呼び出される（FR-06）
> - `run_from_step` は AC-5（cache/resume）の拡張ポイント

### 3.2.2 Connectors（Connector Bounded Context）

```mermaid
classDiagram
    class ConnectorInterface {
        <<interface>>
        +initialize(config: dict) void
        +execute(step: ExecutionStep, context: ExecutionContext) StepResult
        +health_check() HealthStatus
        +teardown() void
    }

    class StepResult {
        +connector_id: str
        +status: StepStatus
        +data: CanonicalData
        +duration: timedelta
        +raw_output: Any
    }

    class OpenDSSConnector {
        +initialize(config: dict) void
        +execute(step: ExecutionStep, context: ExecutionContext) StepResult
        +health_check() HealthStatus
        +teardown() void
    }

    class HELICSConnector {
        +initialize(config: dict) void
        +execute(step: ExecutionStep, context: ExecutionContext) StepResult
        +health_check() HealthStatus
        +teardown() void
    }

    class MockConnector {
        +initialize(config: dict) void
        +execute(step: ExecutionStep, context: ExecutionContext) StepResult
        +health_check() HealthStatus
        +teardown() void
    }

    ConnectorInterface <|.. OpenDSSConnector
    ConnectorInterface <|.. HELICSConnector
    ConnectorInterface <|.. MockConnector

    note for MockConnector "TDD 用。AS-3 により\nConnector テストは\nモック層と統合層の\n2層構成"
```

> **設計ポイント:**
> - 全 Connector が同一インターフェースを実装（AS-2, AS-4）
> - `MockConnector` は AS-3（TDD）のためのテストダブル
> - `StepResult.data` は `CanonicalData` 型（Entities 層）を返す。Connector 内部で外部フォーマット → CDL 変換を行う
> - 将来の実機 Connector（SCADA, HIL）も同一インターフェースで追加可能

### 3.2.3 Data Model（Experiment Domain Bounded Context = CDL）

```mermaid
classDiagram
    class Topology {
        +buses: list~Bus~
        +lines: list~Line~
        +transformers: list~Transformer~
        +switches: list~Switch~
    }

    class Bus {
        +id: str
        +name: str
        +base_kv: float
        +type: BusType
    }

    class Asset {
        +id: str
        +name: str
        +asset_type: AssetType
        +bus_id: str
        +parameters: dict
    }

    class TimeSeries {
        +id: str
        +asset_id: str
        +variable: str
        +timestamps: list~datetime~
        +values: list~float~
        +unit: str
    }

    class Event {
        +id: str
        +timestamp: datetime
        +event_type: EventType
        +source: str
        +data: dict
    }

    class Metric {
        +id: str
        +name: str
        +value: float
        +unit: str
        +experiment_id: str
        +metadata: dict
    }

    class ExperimentMetadata {
        +experiment_id: str
        +scenario_pack_id: str
        +seed: int
        +start_time: datetime
        +end_time: datetime
        +status: RunStatus
        +connector_versions: dict
    }

    class ScenarioPack {
        +id: str
        +name: str
        +version: str
        +topology: Topology
        +assets: list~Asset~
        +timeseries_refs: list~str~
        +connector_config: dict
        +evaluation_metrics: list~str~
        +seed: int | None
        +expected_outputs: dict | None
        +metadata: dict
    }

    class CanonicalDataLayer {
        <<interface>>
        +store_result(experiment_id: str, data: CanonicalData) void
        +get_result(experiment_id: str) CanonicalData
        +list_experiments() list~ExperimentMetadata~
        +export(experiment_id: str, format: ExportFormat) Path
    }

    ScenarioPack --> Topology
    ScenarioPack --> Asset
    Topology --> Bus
    Asset --> TimeSeries
    CanonicalDataLayer --> ExperimentMetadata
    CanonicalDataLayer --> Metric
    CanonicalDataLayer --> TimeSeries
    CanonicalDataLayer --> Event

    note for Topology "CIM (IEC 61970) と\n対応関係を持つ設計\n(AC-7)"
    note for ScenarioPack "metadata フィールドで\n教育メタデータ等を\n拡張可能 (AC-3)"
```

> **設計ポイント:**
> - Entities 層は外部依存なし（AS-2）。Pure Python のデータクラス
> - `Topology`, `Asset` は CIM (IEC 61970) と対応関係を持つ（AC-7）
> - `ScenarioPack.metadata` は拡張可能な dict で、教育メタデータ（AC-3）や将来の追加属性に対応
> - `CanonicalDataLayer` はインターフェース。P0 はファイルシステム実装、将来は DB 実装に差替え可能

### 3.2.4 Evaluation（Evaluation Bounded Context）

```mermaid
classDiagram
    class BenchmarkEngine {
        +run(experiment_ids: list~str~, metric_names: list~str~) BenchmarkResult
        +compare(experiment_ids: list~str~) ComparisonTable
    }

    class BenchmarkResult {
        +experiment_id: str
        +metrics: dict~str, Metric~
        +timestamp: datetime
    }

    class ComparisonTable {
        +experiments: list~str~
        +metrics: dict~str, list~float~~
        +ranking: dict~str, int~
        +export(format: ExportFormat) Path
    }

    class MetricCalculator {
        <<interface>>
        +calculate(data: CanonicalData) Metric
    }

    class VoltageViolationCalculator {
        +calculate(data: CanonicalData) Metric
    }

    class ENSCalculator {
        +calculate(data: CanonicalData) Metric
    }

    class CustomMetricCalculator {
        +calculate(data: CanonicalData) Metric
    }

    BenchmarkEngine --> MetricCalculator
    BenchmarkEngine --> BenchmarkResult
    BenchmarkEngine --> ComparisonTable
    MetricCalculator <|.. VoltageViolationCalculator
    MetricCalculator <|.. ENSCalculator
    MetricCalculator <|.. CustomMetricCalculator

    note for CustomMetricCalculator "L2 Plugin API で\n研究者が独自指標を\n追加可能 (FR-06)"
```

### 3.2.5 UX（UX Bounded Context）

```mermaid
classDiagram
    class CLIApp {
        +run(args: list~str~) int
    }

    class RunCommand {
        +execute(scenario_pack_id: str, options: RunOptions) void
    }

    class ScenarioCommand {
        +create(name: str) void
        +list() void
        +clone(source: str, target: str) void
        +validate(name: str) void
        +register(name: str) void
    }

    class BenchmarkCommand {
        +run(experiment_ids: list~str~) void
        +export(format: str) void
    }

    class ResultsCommand {
        +list() void
        +show(experiment_id: str) void
        +plot(experiment_id: str, metric: str) void
        +export(experiment_id: str, format: str) void
    }

    class StatusCommand {
        +execute() void
    }

    class NotebookBridge {
        +get_orchestrator() Orchestrator
        +get_cdl() CanonicalDataLayer
        +get_benchmark() BenchmarkEngine
        +load_result(experiment_id: str) DataFrame
    }

    CLIApp --> RunCommand
    CLIApp --> ScenarioCommand
    CLIApp --> BenchmarkCommand
    CLIApp --> ResultsCommand
    CLIApp --> StatusCommand

    note for NotebookBridge "Jupyter / Python script\nからの直接アクセス用\n(FR-05)"
```

---

## 3.3 配置図（Docker コンテナ・ホスト環境の物理配置）

> **注:** 配置図は Round 3 で作成する。Docker Compose 構成、コンテナ間通信、データボリュームの配置を、シーケンス図で明らかになるプロセス間通信を反映して記述する予定。
