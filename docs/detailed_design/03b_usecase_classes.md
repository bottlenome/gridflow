# 3B. ユースケース層クラス設計

## 更新履歴

| バージョン | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 | gridflow設計チーム |
| 0.2 | 2026-04-04 | 3.5〜3.6 追記 | gridflow設計チーム |
| 0.4 | 2026-04-06 | 状態属性追加（Orchestrator）（DD-REV-103） | Claude |
| 0.5 | 2026-04-06 | 第3章分割（03_class_design.md → 03a/03b/03c/03d） | Claude |
| 0.6 | 2026-04-06 | X6レビュー対応: TimeSyncStrategy(Protocol)+3実装追加, FederatedConnectorInterface追加, SimulationTask/TaskResult追加 | Claude |

---

> **ナビゲーション:** [クラス設計 Index](03_class_design.md) | [03a ドメイン層](03a_domain_classes.md) | **03b ユースケース層（本文書）** | [03c アダプタ層](03c_adapter_classes.md) | [03d インフラ層](03d_infra_classes.md)

---

## 3.3 Orchestrator関連（REQ-F-002）

### 3.3.1 クラス図

```mermaid
classDiagram
    class Orchestrator {
        +ContainerManager container_manager
        +TimeSync time_sync
        +dict config
        +run(pack: ScenarioPack, options: dict) ExperimentResult
        +run_batch(packs: list~ScenarioPack~, options: dict) list~ExperimentResult~
        +cancel(exp_id: str) None
    }

    class ExecutionPlan {
        +str experiment_id
        +ScenarioPack pack
        +list~StepConfig~ steps
        +list~str~ connectors
        +dict parameters
    }

    class ContainerManager {
        +str compose_project
        +str network
        +int max_parallel
        +start(services: list~str~) None
        +stop(services: list~str~) None
        +health_check(service: str) HealthStatus
    }

    class TimeSync {
        +str mode
        +float step_size
        +int total_steps
    }

    Orchestrator --> ContainerManager : container_manager
    Orchestrator --> TimeSync : time_sync
    Orchestrator ..> ExecutionPlan : creates
    ExecutionPlan --> ScenarioPack : pack
```

### 3.3.2 Orchestrator

**モジュール:** `gridflow.infra.orchestrator`

| 属性 | 型 | 説明 |
|---|---|---|
| container_manager | ContainerManager | コンテナ管理インスタンス |
| time_sync | TimeSync | 時間同期制御インスタンス |
| config | dict | オーケストレータ設定 |
| state | OrchestratorState | 現在の状態（Idle / Initializing / Running / Completed / Failed）。第5章 5.1 状態遷移参照 |

#### メソッド

**run**

| 項目 | 内容 |
|---|---|
| **Input** | `pack: ScenarioPack` -- 実行対象のシナリオパック, `options: dict` -- 実行オプション（タイムアウト、並列数等） |
| **Process** | ExecutionPlanを生成し、ContainerManagerでコンテナを起動後、TimeSyncに従って時間ステップを進行しながらシミュレーションを実行する。各ステップの結果を収集し、完了後にコンテナを停止する。 |
| **Output** | `ExperimentResult` -- 実験結果。実行失敗時は `ExecutionError` を送出。 |

**run_batch**

| 項目 | 内容 |
|---|---|
| **Input** | `packs: list[ScenarioPack]` -- 実行対象のパックリスト, `options: dict` -- 実行オプション |
| **Process** | 複数のシナリオパックを順次またはmax_parallelに従い並列で実行する。各パックに対してrunメソッドを呼び出し、結果をリストとして集約する。 |
| **Output** | `list[ExperimentResult]` -- 各パックの実験結果リスト。個別の失敗はリスト内のExperimentResultにエラー情報として格納。 |

**cancel**

| 項目 | 内容 |
|---|---|
| **Input** | `exp_id: str` -- キャンセル対象の実験ID |
| **Process** | 実行中の実験を特定し、関連コンテナを停止してリソースを解放する。 |
| **Output** | `None`。該当実験が存在しない場合は `ExperimentNotFoundError` を送出。 |

### 3.3.3 ExecutionPlan

**モジュール:** `gridflow.infra.orchestrator`

| 属性 | 型 | 説明 |
|---|---|---|
| experiment_id | str | 実験の一意識別子 |
| pack | ScenarioPack | 対象シナリオパック |
| steps | list[StepConfig] | 実行ステップの設定リスト |
| connectors | list[str] | 使用するコネクタ名のリスト |
| parameters | dict | 実行パラメータ |

### 3.3.4 ContainerManager

**モジュール:** `gridflow.infra.orchestrator`

| 属性 | 型 | 説明 |
|---|---|---|
| compose_project | str | Docker Composeプロジェクト名 |
| network | str | Dockerネットワーク名 |
| max_parallel | int | 最大並列コンテナ数 |

#### メソッド

**start**

| 項目 | 内容 |
|---|---|
| **Input** | `services: list[str]` -- 起動対象のサービス名リスト |
| **Process** | Docker Composeを使用して指定サービスのコンテナを起動する。ネットワーク設定を適用し、起動完了を待機する。 |
| **Output** | `None`。起動失敗時は `ContainerStartError` を送出。 |

**stop**

| 項目 | 内容 |
|---|---|
| **Input** | `services: list[str]` -- 停止対象のサービス名リスト |
| **Process** | 指定サービスのコンテナをグレースフルに停止し、リソースを解放する。 |
| **Output** | `None`。停止失敗時は `ContainerStopError` を送出。 |

**health_check**

| 項目 | 内容 |
|---|---|
| **Input** | `service: str` -- ヘルスチェック対象のサービス名 |
| **Process** | 指定サービスのコンテナに対してヘルスチェックを実行し、応答状態を確認する。 |
| **Output** | `HealthStatus` -- サービスの稼働状態（healthy / unhealthy / starting）。サービスが存在しない場合は `ServiceNotFoundError` を送出。 |

### 3.3.5 TimeSync

**モジュール:** `gridflow.infra.orchestrator`

時間同期の**設定データ**。TimeSyncStrategy（3.3.6）の実行パラメータとして使用される。

| 属性 | 型 | 説明 |
|---|---|---|
| mode | str | 同期モード（"orchestrator" \| "federation" \| "hybrid"） |
| step_size | float | 1ステップあたりの時間幅（秒） |
| total_steps | int | 総ステップ数 |

### 3.3.6 TimeSyncStrategy（Protocol）

**モジュール:** `gridflow.usecase.interfaces`

時間同期の**実行戦略**インタフェース。第7章（7.1節）で定義されるアルゴリズムに対応する。TimeSync（3.3.5）が設定、TimeSyncStrategy が振る舞いを担う。

```mermaid
classDiagram
    class TimeSyncStrategy {
        <<Protocol>>
        +advance(step: int, context: dict) dict
    }

    class OrchestratorDriven {
        -list~ConnectorInterface~ connectors
        -CDLRepository cdl_repo
        +advance(step: int, context: dict) dict
    }

    class FederationDriven {
        -HELICSBroker broker
        -list~FederatedConnectorInterface~ connectors
        +advance(step: int, context: dict) dict
    }

    class HybridSync {
        -OrchestratorDriven orchestrator
        -FederationDriven federation
        +advance(step: int, context: dict) dict
    }

    TimeSyncStrategy <|.. OrchestratorDriven : implements
    TimeSyncStrategy <|.. FederationDriven : implements
    TimeSyncStrategy <|.. HybridSync : implements
```

#### メソッド

**advance**

| 項目 | 内容 |
|---|---|
| **Input** | `step: int` -- 現在のステップ番号, `context: dict` -- ステップ実行コンテキスト |
| **Process** | 同期戦略に従って全コネクタの1ステップ実行を統制し、結果を集約して返却する。 |
| **Output** | `dict` -- 集約された実行結果コンテキスト。同期失敗時は `SyncError(SimulationError)` を送出。 |

#### OrchestratorDriven

Orchestrator が直接ステップタイミングを制御する。OpenDSS / pandapower 等の非リアルタイムコネクタ向け。各コネクタを順次 `execute(step, context)` で呼び出し、CDLRepository に結果を格納する。

#### FederationDriven

HELICS Broker がタイミングを管理する。HELICS 対応シミュレータ向け。`broker.request_time()` で付与された時刻で `connector.execute_at(granted_time, context)` を呼び出す。

#### HybridSync

OrchestratorDriven と FederationDriven を組み合わせ、HELICS 対応/非対応コネクタを1つの実験で混在実行する。ステップごとに Orchestrator 管理コネクタを先に実行し、その後 Broker 経由で Federation 管理コネクタを実行する。

### 3.3.7 SimulationTask / TaskResult

**モジュール:** `gridflow.usecase.scheduling`

バッチスケジューリング（第7章 7.3節）で使用するタスク定義と結果。

**SimulationTask**（`dataclass`）

| 属性 | 型 | 説明 |
|---|---|---|
| task_id | str | タスクの一意識別子 |
| pack | ScenarioPack | 実行対象のシナリオパック |
| options | dict | 実行オプション |

**execute**

| 項目 | 内容 |
|---|---|
| **Input** | なし（属性から取得） |
| **Process** | Orchestrator.run() を非同期で呼び出し、ExperimentResult を取得する。 |
| **Output** | `TaskResult` -- タスク実行結果。失敗時は `SchedulerError(SimulationError)` を送出。 |

**TaskResult**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| task_id | str | 対応するタスクID |
| status | str | "completed" \| "failed" |
| data | ExperimentResult \| None | 成功時の実験結果 |
| error | str \| None | 失敗時のエラーメッセージ |

---

## 3.5 Connector関連クラス設計（REQ-F-007）

### 3.5.1 クラス図

```mermaid
classDiagram
    class ConnectorInterface {
        <<Protocol>>
        +initialize(config: dict~str, Any~) None
        +execute(step: int, context: dict~str, Any~) StepResult
        +health_check() HealthStatus
        +teardown() None
    }

    class FederatedConnectorInterface {
        <<Protocol>>
        +execute_at(granted_time: float, context: dict~str, Any~) StepResult
    }

    class OpenDSSConnector {
        -str dss_script_path
        -DSSInterface engine
        +initialize(config: dict~str, Any~) None
        +execute(step: int, context: dict~str, Any~) StepResult
        +health_check() HealthStatus
        +teardown() None
    }

    class DataTranslator {
        <<Protocol>>
        +to_canonical(raw: Any) CanonicalData
        +from_canonical(data: CanonicalData) Any
    }

    class OpenDSSTranslator {
        +to_canonical(raw: Any) CanonicalData
        +from_canonical(data: CanonicalData) Any
    }

    class StepResult {
        <<dataclass>>
        +str status
        +dict~str, Any~ data
        +float elapsed_ms
    }

    class HealthStatus {
        <<dataclass>>
        +bool healthy
        +str message
    }

    ConnectorInterface <|-- FederatedConnectorInterface : extends
    ConnectorInterface <|.. OpenDSSConnector : implements
    DataTranslator <|.. OpenDSSTranslator : implements
    OpenDSSConnector --> DataTranslator : uses
    OpenDSSConnector ..> StepResult : returns
    OpenDSSConnector ..> HealthStatus : returns
```

### 3.5.2 ConnectorInterface（Protocol）

**モジュール:** `gridflow.usecase.interfaces`

UseCase層に定義し、DIP（依存性逆転の原則）を適用する。Adapter層の具象コネクタはこのProtocolを実装する。

#### メソッド

**initialize**

| 項目 | 内容 |
|---|---|
| **Input** | `config: dict[str, Any]` -- コネクタ固有の設定（スクリプトパス、接続先等） |
| **Process** | コネクタの初期化処理を実行する。外部シミュレータとの接続確立、設定ファイルの読み込み、内部状態の初期化を行う。 |
| **Output** | `None`。初期化失敗時は `ConnectorInitError`（E-30001）を送出。 |

**execute**

| 項目 | 内容 |
|---|---|
| **Input** | `step: int` -- 現在のシミュレーションステップ番号, `context: dict[str, Any]` -- ステップ実行コンテキスト（他コネクタからの入力データ等） |
| **Process** | 1ステップ分のシミュレーションを実行する。contextから入力データを取得し、外部シミュレータに渡して計算を実行し、結果をCDL準拠のデータ形式に変換して返却する。 |
| **Output** | `StepResult` -- ステップ実行結果。実行失敗時は `ConnectorExecuteError`（E-30002）を送出。 |

**health_check**

| 項目 | 内容 |
|---|---|
| **Input** | なし |
| **Process** | コネクタおよび外部シミュレータの稼働状態を確認する。接続状態、プロセス生存、メモリ使用量等をチェックする。 |
| **Output** | `HealthStatus` -- 稼働状態。通信失敗時もHealthStatus（healthy=False）として返却し、例外は送出しない。 |

**teardown**

| 項目 | 内容 |
|---|---|
| **Input** | なし |
| **Process** | コネクタの終了処理を実行する。外部シミュレータとの接続切断、一時ファイルの削除、リソースの解放を行う。 |
| **Output** | `None`。終了処理失敗時は `ConnectorTeardownError`（E-30003）を送出。 |

### 3.5.2a FederatedConnectorInterface（Protocol）

**モジュール:** `gridflow.usecase.interfaces`

HELICS 対応コネクタ向けの拡張 Protocol。ConnectorInterface を継承し、時刻ベースの実行メソッド `execute_at` を追加する。FederationDriven / HybridSync 戦略で使用される。

#### メソッド

**execute_at**

| 項目 | 内容 |
|---|---|
| **Input** | `granted_time: float` -- HELICS Broker から付与されたシミュレーション時刻（秒）, `context: dict[str, Any]` -- ステップ実行コンテキスト |
| **Process** | 付与された時刻で1ステップ分のシミュレーションを実行する。`execute(step, context)` のステップベース実行に対し、時刻ベースでの実行を提供する。 |
| **Output** | `StepResult` -- ステップ実行結果。実行失敗時は `ConnectorExecuteError`（E-30002）を送出。 |

> **備考:** HELICS 非対応のコネクタ（OpenDSS等）はこの Protocol を実装する必要はない。ConnectorInterface のみ実装すれば OrchestratorDriven 戦略で使用可能。

### 3.5.3 OpenDSSConnector

**モジュール:** `gridflow.adapter.connector`

py-dss-interface経由でOpenDSSエンジンを操作する具象コネクタ。DSSスクリプト（.dss）を入力とし、CDL準拠の出力データ（Topology, Asset, TimeSeries, Metric）を生成する。

| 属性 | 型 | 説明 |
|---|---|---|
| dss_script_path | str | OpenDSSスクリプトファイルのパス |
| engine | DSSInterface | py-dss-interfaceのエンジンインスタンス |

#### メソッド

**initialize**

| 項目 | 内容 |
|---|---|
| **Input** | `config: dict[str, Any]` -- `{"dss_script": str, "options": dict}` |
| **Process** | py-dss-interfaceを初期化し、DSSスクリプトをコンパイルする。スクリプト構文エラーがあれば即座に検出する。 |
| **Output** | `None`。スクリプト不正時は `ConnectorInitError`（E-30001）を送出。 |

**execute**

| 項目 | 内容 |
|---|---|
| **Input** | `step: int` -- ステップ番号, `context: dict[str, Any]` -- 入力コンテキスト |
| **Process** | OpenDSSエンジンで1ステップのパワーフロー計算を実行する。contextから負荷・発電データを設定し、Solve後にノード電圧・線路電流・損失等を取得する。OpenDSSTranslatorでCDL形式に変換する。 |
| **Output** | `StepResult` -- status="success"時、data内にTopology/Asset/TimeSeries/Metricを格納。 |

### 3.5.4 DataTranslator（Protocol）・OpenDSSTranslator

**モジュール:** `gridflow.usecase.interfaces`（Protocol）/ `gridflow.adapter.connector`（実装）

**DataTranslator（Protocol）**

| 項目 | 内容 |
|---|---|
| **to_canonical** | `raw: Any` → `CanonicalData` -- シミュレータ固有の生データをCDL準拠データに変換 |
| **from_canonical** | `data: CanonicalData` → `Any` -- CDL準拠データをシミュレータ固有形式に逆変換 |

**OpenDSSTranslator** はOpenDSS固有のデータ構造（ノード電圧配列、線路電流配列等）とCDLクラス（Topology, Asset, TimeSeries, Metric）間の変換を担う。

### 3.5.5 StepResult・HealthStatus

**モジュール:** `gridflow.usecase.interfaces`

**StepResult**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| status | str | 実行結果ステータス（"success" \| "warning" \| "error"） |
| data | dict[str, Any] | CDL準拠の出力データ |
| elapsed_ms | float | 実行時間（ミリ秒） |

**HealthStatus**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| healthy | bool | 正常稼働ならTrue |
| message | str | 状態メッセージ（異常時はエラー詳細） |

### 3.5.6 REST APIエンドポイント

Connector間通信はRESTで行う。各コネクタは以下のエンドポイントを公開する。

| メソッド | パス | リクエストボディ | レスポンス | 説明 |
|---|---|---|---|---|
| POST | /initialize | `{"config": dict}` | `{"status": "ok"}` | Connector初期化 |
| POST | /execute | `{"step": int, "context": dict}` | `StepResult（JSON）` | 1ステップ実行 |
| GET | /health | なし | `HealthStatus（JSON）` | ヘルスチェック |
| POST | /teardown | なし | `{"status": "ok"}` | 終了・リソース解放 |

---

## 3.6 Benchmark関連クラス設計（REQ-F-004）

### 3.6.1 クラス図

```mermaid
classDiagram
    class BenchmarkHarness {
        +list~MetricCalculator~ calculators
        +ReportGenerator report_generator
        +run(experiment_ids: list~str~, metric_names: list~str~) BenchmarkReport
        +compare(a: BenchmarkReport, b: BenchmarkReport) ComparisonReport
        +export(report: BenchmarkReport, format: str, path: Path) Path
    }

    class MetricCalculator {
        <<Protocol>>
        +str name
        +calculate(experiment_result: ExperimentResult) MetricValue
    }

    class ReportGenerator {
        +generate(report: BenchmarkReport, format: str) str|bytes
    }

    class BenchmarkReport {
        <<dataclass>>
        +str report_id
        +list~str~ experiment_ids
        +dict~str, MetricValue~ metrics
        +datetime created_at
    }

    class ComparisonReport {
        <<dataclass>>
        +BenchmarkReport baseline
        +BenchmarkReport target
        +dict~str, MetricDiff~ diffs
    }

    class MetricValue {
        <<dataclass>>
        +str name
        +float value
        +str unit
    }

    BenchmarkHarness --> MetricCalculator : uses
    BenchmarkHarness --> ReportGenerator : uses
    BenchmarkHarness ..> BenchmarkReport : produces
    BenchmarkHarness ..> ComparisonReport : produces
    MetricCalculator ..> MetricValue : returns
```

### 3.6.2 BenchmarkHarness

**モジュール:** `gridflow.adapter.benchmark`

| 属性 | 型 | 説明 |
|---|---|---|
| calculators | list[MetricCalculator] | 登録済み指標計算器のリスト |
| report_generator | ReportGenerator | レポート生成器 |

#### メソッド

**run**

| 項目 | 内容 |
|---|---|
| **Input** | `experiment_ids: list[str]` -- 評価対象の実験IDリスト, `metric_names: list[str]` -- 計算する指標名リスト |
| **Process** | 指定された実験結果を取得し、metric_namesに対応するMetricCalculatorを選択して各指標を計算する。結果をBenchmarkReportとして集約する。 |
| **Output** | `BenchmarkReport` -- ベンチマーク評価レポート。実験IDが存在しない場合は `ExperimentNotFoundError` を送出。 |

**compare**

| 項目 | 内容 |
|---|---|
| **Input** | `a: BenchmarkReport` -- ベースラインレポート, `b: BenchmarkReport` -- 比較対象レポート |
| **Process** | 2つのレポートの共通指標について差分（絶対値・変化率）を算出し、改善/悪化を判定する。 |
| **Output** | `ComparisonReport` -- 比較結果レポート。共通指標がない場合は `NoComparableMetricsError` を送出。 |

**export**

| 項目 | 内容 |
|---|---|
| **Input** | `report: BenchmarkReport` -- 出力対象レポート, `format: str` -- 出力形式（"json" \| "csv" \| "html"）, `path: Path` -- 出力先パス |
| **Process** | ReportGeneratorを使用してレポートを指定形式に変換し、指定パスに書き出す。 |
| **Output** | `Path` -- 出力されたファイルのパス。書き込み失敗時は `ExportError` を送出。 |

### 3.6.3 MetricCalculator（Protocol）

**モジュール:** `gridflow.usecase.interfaces`

Strategyパターンを適用し、指標計算ロジックを交換可能にする。

| プロパティ/メソッド | 型 | 説明 |
|---|---|---|
| name（property） | str | 指標名 |
| calculate | (ExperimentResult) → MetricValue | 指標計算 |

#### 標準指標計算器一覧

| クラス名 | 指標名 | 単位 | 準拠規格 | 説明 |
|---|---|---|---|---|
| VoltageDeviationCalculator | voltage_deviation_max | % | EN 50160 | 最大電圧偏差率 |
| VoltageDeviationCalculator | voltage_deviation_mean | % | EN 50160 | 平均電圧偏差率 |
| VoltageDeviationCalculator | voltage_deviation_p95 | % | EN 50160 | 95パーセンタイル電圧偏差率 |
| VoltageDeviationCalculator | voltage_violation_ratio | % | EN 50160 | 電圧違反率（閾値超過サンプル比） |
| ThermalOverloadCalculator | thermal_overload_hours | h | — | 熱容量超過の累積時間 |
| EnergyNotSuppliedCalculator | energy_not_supplied | MWh | — | 供給不能エネルギー量 |
| SAIDICalculator | saidi | min/customer | IEEE 1366 | 顧客あたり平均停電時間 |
| SAIFICalculator | saifi | 回/customer | IEEE 1366 | 顧客あたり平均停電回数 |
| CAIDICalculator | caidi | min/回 | IEEE 1366 | 停電1回あたり平均復旧時間 |
| DispatchCostCalculator | dispatch_cost | USD | — | 発電コスト |
| CO2EmissionsCalculator | co2_emissions | tCO2 | — | CO2排出量 |
| CurtailmentCalculator | curtailment | MWh | — | 出力抑制量 |
| LossesCalculator | losses | MWh | — | 系統損失 |
| RestorationTimeCalculator | restoration_time | s | — | 復旧時間 |
| RuntimeCalculator | runtime | s | — | シミュレーション実行時間 |

### 3.6.4 ReportGenerator

**モジュール:** `gridflow.adapter.benchmark`

**generate**

| 項目 | 内容 |
|---|---|
| **Input** | `report: BenchmarkReport` -- 変換対象レポート, `format: str` -- 出力形式（"json" \| "csv" \| "html"） |
| **Process** | BenchmarkReportを指定フォーマットに変換する。JSON: 構造化データ、CSV: フラットテーブル、HTML: グラフ付きレポート。 |
| **Output** | `str \| bytes` -- 変換結果。未対応フォーマットの場合は `UnsupportedFormatError` を送出。 |

### 3.6.5 データクラス

**BenchmarkReport**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| report_id | str | レポートの一意識別子 |
| experiment_ids | list[str] | 評価対象の実験IDリスト |
| metrics | dict[str, MetricValue] | 指標名→計算結果のマッピング |
| created_at | datetime | レポート作成日時 |

**ComparisonReport**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| baseline | BenchmarkReport | ベースラインレポート |
| target | BenchmarkReport | 比較対象レポート |
| diffs | dict[str, MetricDiff] | 指標名→差分情報のマッピング |

**MetricValue**（`dataclass(frozen=True)`）

| 属性 | 型 | 説明 |
|---|---|---|
| name | str | 指標名 |
| value | float | 指標値 |
| unit | str | 単位 |

---

> **関連文書:** ドメインクラス（ScenarioPack, CDL）は → [03a ドメイン層](03a_domain_classes.md) / CLI・Plugin は → [03c アダプタ層](03c_adapter_classes.md) / 共通基盤・トレースは → [03d インフラ層](03d_infra_classes.md)
