# 3A. ドメイン層クラス設計

## 更新履歴

| バージョン | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 | gridflow設計チーム |
| 0.4 | 2026-04-06 | 不足クラス追加（CanonicalData, CDLRepository）、状態属性追加（ScenarioPack）（DD-REV-101/103） | Claude |
| 0.5 | 2026-04-06 | 第3章分割（03_class_design.md → 03a/03b/03c/03d） | Claude |
| 0.6 | 2026-04-06 | X5/X6レビュー対応: Event.target拡張(target_id+target_type), Metric PK統一(metric_id→name), Asset.bus→node_id統一, ExperimentResult/Result型群/Interruption追加 | Claude |
| 0.7 | 2026-04-07 | Phase0結果レビュー対応: (1) `parameters` 型を `dict` → `tuple[tuple[str, object], ...]` に統一（不変性確保, 論点6.1）。(2) `ExperimentResult` を UseCase 層 `03e_usecase_results.md` へ移設（論点6.4）。(3) `ScenarioRegistry` を Domain Protocol として再定義し、`PackNotFoundError` を Domain 契約として明示（論点6.3）。詳細は `review_record.md` 参照 | Claude |

---

> **ナビゲーション:** [クラス設計 Index](03_class_design.md) | **03a ドメイン層（本文書）** | [03b ユースケース層](03b_usecase_classes.md) | [03c アダプタ層](03c_adapter_classes.md) | [03d インフラ層](03d_infra_classes.md) | [03e UseCase結果型](03e_usecase_results.md)

---

## 3.1 クラス一覧

| DD-CLS | クラス名 | モジュール | レイヤー | 責務 | 関連要件 |
|---|---|---|---|---|---|
| DD-CLS-001 | ScenarioPack | gridflow.domain.scenario | Domain | 実験パッケージのデータモデル | REQ-F-001 |
| DD-CLS-002 | PackMetadata | gridflow.domain.scenario | Domain | パックのメタデータ | REQ-F-001 |
| DD-CLS-003 | ScenarioRegistry | gridflow.domain.scenario.registry | Domain (Protocol) | パックの登録・検索・バージョン管理（契約）。実装は Infra 層 (`gridflow.infra.scenario.file_registry` 等） | REQ-F-001 |
| DD-CLS-004 | Topology | gridflow.domain.cdl | Domain | ネットワークトポロジ | REQ-F-003 |
| DD-CLS-005 | Asset | gridflow.domain.cdl | Domain | 電力機器 | REQ-F-003 |
| DD-CLS-006 | TimeSeries | gridflow.domain.cdl | Domain | 時系列データ | REQ-F-003 |
| DD-CLS-007 | Orchestrator | gridflow.infra.orchestrator | Infra | 実験実行の統制 | REQ-F-002 |
| DD-CLS-008 | ExecutionPlan | gridflow.infra.orchestrator | Infra | 実行計画の定義 | REQ-F-002 |
| DD-CLS-009 | ContainerManager | gridflow.infra.orchestrator | Infra | Dockerコンテナ管理 | REQ-F-002 |
| DD-CLS-010 | CLIApp | gridflow.adapter.cli | Adapter | CLIエントリポイント | REQ-F-005 |
| DD-CLS-011 | CommandHandler | gridflow.adapter.cli | Adapter | CLIコマンドハンドラー基底 | REQ-F-005 |
| DD-CLS-012 | OutputFormatter | gridflow.adapter.cli | Adapter | CLI出力フォーマッタ | REQ-F-005 |
| DD-CLS-013 | BenchmarkHarness | gridflow.adapter.benchmark | Adapter | ベンチマーク評価 | REQ-F-004 |
| DD-CLS-014 | MetricCalculator | gridflow.usecase.interfaces | UseCase | 評価指標計算Protocol | REQ-F-004 |
| DD-CLS-015 | ReportGenerator | gridflow.adapter.benchmark | Adapter | ベンチマークレポート生成 | REQ-F-004 |
| DD-CLS-016 | PluginRegistry | gridflow.infra.plugin | Infra | プラグイン管理 | REQ-F-006 |
| DD-CLS-017 | PluginDiscovery | gridflow.infra.plugin | Infra | プラグイン検出・ロード | REQ-F-006 |
| DD-CLS-018 | ConnectorInterface | gridflow.usecase.interfaces | UseCase | 外部シミュレータ統一IF | REQ-F-007 |
| DD-CLS-019 | OpenDSSConnector | gridflow.adapter.connector | Adapter | OpenDSS接続実装 | REQ-F-007 |
| DD-CLS-020 | DataTranslator | gridflow.usecase.interfaces | UseCase | データ変換Protocol | REQ-F-007 |
| DD-CLS-021 | StructuredLogger | gridflow.infra.logging | Infra | 構造化ログ | REQ-Q-008 |
| DD-CLS-022 | ConfigManager | gridflow.infra.config | Infra | 設定管理 | REQ-Q-009 |
| DD-CLS-023 | ErrorHandler | gridflow.infra.error | Infra | エラーハンドリング | REQ-Q-008 |
| DD-CLS-024 | TimeSync | gridflow.infra.orchestrator | Infra | 時間同期制御 | REQ-F-002 |
| DD-CLS-025 | Event | gridflow.domain.cdl | Domain | シミュレーションイベント | REQ-F-003 |
| DD-CLS-026 | Metric | gridflow.domain.cdl | Domain | 評価指標 | REQ-F-003 |
| DD-CLS-027 | ExperimentMetadata | gridflow.domain.cdl | Domain | 実験メタデータ | REQ-F-003 |
| DD-CLS-028 | Node | gridflow.domain.cdl | Domain | ネットワークノード | REQ-F-003 |
| DD-CLS-029 | Edge | gridflow.domain.cdl | Domain | ネットワークエッジ | REQ-F-003 |
| DD-CLS-030 | TraceSpan | gridflow.infra.trace | Infra | トレーススパン（OTel互換） | REQ-Q-008 |
| DD-CLS-031 | TraceRecorder | gridflow.infra.trace | Infra | トレース記録 | REQ-Q-008 |
| DD-CLS-032 | PerfettoExporter | gridflow.infra.trace | Infra | Perfetto形式エクスポート | REQ-Q-008 |
| DD-CLS-033 | ExperimentResult | gridflow.usecase.result | UseCase | 実験結果の集約データモデル（v0.7 で UseCase 層へ移設）。詳細は [03e](03e_usecase_results.md) | REQ-F-002 |
| DD-CLS-048 | StepResult | gridflow.usecase.result | UseCase | 各ステップの実行結果（v0.7 新設）。詳細は [03e](03e_usecase_results.md) | REQ-F-002 |
| DD-CLS-049 | StepStatus | gridflow.usecase.result | UseCase | StepResult.status の Enum 型（v0.7 新設） | REQ-F-002 |
| DD-CLS-034 | NodeResult | gridflow.domain.result | Domain | ノード別シミュレーション結果 | REQ-F-002 |
| DD-CLS-035 | BranchResult | gridflow.domain.result | Domain | ブランチ別シミュレーション結果 | REQ-F-002 |
| DD-CLS-036 | LoadResult | gridflow.domain.result | Domain | 負荷別シミュレーション結果 | REQ-F-002 |
| DD-CLS-037 | GeneratorResult | gridflow.domain.result | Domain | 発電機別シミュレーション結果 | REQ-F-002 |
| DD-CLS-038 | RenewableResult | gridflow.domain.result | Domain | 再エネ別シミュレーション結果 | REQ-F-002 |
| DD-CLS-039 | Interruption | gridflow.domain.result | Domain | 停電イベント（IEEE 1366用） | REQ-F-004 |
| DD-CLS-040 | TimeSyncStrategy | gridflow.usecase.interfaces | UseCase | 時間同期戦略Protocol | REQ-F-002 |
| DD-CLS-041 | OrchestratorDriven | gridflow.infra.orchestrator | Infra | Orchestrator駆動の時間同期 | REQ-F-002 |
| DD-CLS-042 | FederationDriven | gridflow.infra.orchestrator | Infra | HELICS Federation駆動の時間同期 | REQ-F-002 |
| DD-CLS-043 | HybridSync | gridflow.infra.orchestrator | Infra | ハイブリッド時間同期 | REQ-F-002 |
| DD-CLS-044 | HELICSBroker | gridflow.infra.orchestrator | Infra | HELICS Broker管理 | REQ-F-002 |
| DD-CLS-045 | FederatedConnectorInterface | gridflow.usecase.interfaces | UseCase | HELICS対応コネクタIF | REQ-F-007 |
| DD-CLS-046 | SimulationTask | gridflow.usecase.scheduling | UseCase | バッチスケジューリング用タスク | REQ-F-002 |
| DD-CLS-047 | TaskResult | gridflow.usecase.scheduling | UseCase | タスク実行結果 | REQ-F-002 |
| DD-CLS-050 | SensitivityAnalyzer | gridflow.usecase.sensitivity | UseCase | 感度分析 (post-processing)。同一 simulation 結果に対して metric パラメータを変えて再評価 | REQ-F-016 |
| DD-CLS-051 | SensitivityResult | gridflow.domain.result | Domain | 感度分析結果。パラメータ軸上の metric 値曲線 + 特徴点 | REQ-F-016 |
| DD-CLS-052 | VoltageSensitivityMatrix | gridflow.domain.result | Domain | bus 間電圧感度行列。dV_j/dP_i を格納 | REQ-F-016 |

---

## 3.2 Scenario Pack関連（REQ-F-001）

### 3.2.1 クラス図

```mermaid
classDiagram
    class ScenarioPack {
        +str pack_id
        +str name
        +str version
        +PackMetadata metadata
        +Path network_dir
        +Path timeseries_dir
        +Path config_dir
    }

    class PackMetadata {
        +str name
        +str version
        +str description
        +str author
        +datetime created_at
        +str connector
        +int|None seed
        +tuple~tuple~str,object~~ parameters
    }

    class ScenarioRegistry {
        +Path registry_path
        +dict~str, ScenarioPack~ packs
        +register(pack: ScenarioPack) str
        +get(pack_id: str) ScenarioPack
        +list(query: str) list~ScenarioPack~
        +create_from_template(name: str, template: str) ScenarioPack
        +validate(path: Path) ValidationResult
    }

    ScenarioPack --> PackMetadata : metadata
    ScenarioRegistry --> ScenarioPack : manages
```

### 3.2.2 ScenarioPack

**モジュール:** `gridflow.domain.scenario`

| 属性 | 型 | 説明 |
|---|---|---|
| pack_id | str | パックの一意識別子 |
| name | str | パック名 |
| version | str | バージョン文字列 |
| metadata | PackMetadata | パックのメタデータ |
| network_dir | Path | ネットワーク定義ディレクトリ |
| timeseries_dir | Path | 時系列データディレクトリ |
| config_dir | Path | 設定ファイルディレクトリ |
| status | PackStatus | 現在の状態（Draft / Validated / Registered / Running / Completed）。第5章 5.3 状態遷移参照 |

### 3.2.3 PackMetadata

**モジュール:** `gridflow.domain.scenario`

| 属性 | 型 | 説明 |
|---|---|---|
| name | str | メタデータ名 |
| version | str | バージョン文字列 |
| description | str | パックの説明 |
| author | str | 作成者 |
| created_at | datetime | 作成日時 |
| connector | str | 使用するコネクタ名 |
| seed | int \| None | 乱数シード（再現性用） |
| parameters | tuple[tuple[str, object], ...] | 追加パラメータ（不変。利用時は `dict(self.parameters)` で復元） |

### 3.2.4 ScenarioRegistry（Domain Protocol）

**モジュール:** `gridflow.domain.scenario.registry`

> **配置方針（v0.7 変更）:** ScenarioRegistry は **Domain 層の Protocol** として定義する。実装クラス（例: `FileScenarioRegistry`）は Infra 層 `gridflow.infra.scenario.file_registry` に配置する。これにより以下を実現する：
> - UseCase 層は Protocol と Domain エラー（`PackNotFoundError`）のみに依存し、Infra 詳細を import しない（Clean Architecture 依存方向の遵守）
> - 「Pack の存在保証」が Domain ルール（不変条件）として表現され、storage backend を差し替えても契約が維持される
> - エラー契約（`get()` で未発見時に `PackNotFoundError` を送出）が Protocol 上で明示される
>
> 詳細な議論経緯は `review_record.md` 論点6.3 を参照。

**Protocol 定義:**

```python
from typing import Protocol

class ScenarioRegistry(Protocol):
    """シナリオパックの登録・検索契約。

    エラー契約:
        get():    存在しない pack_id に対し PackNotFoundError を送出
        register(): バリデーション失敗時に ValidationError を送出
        validate(): 構造不正を ValidationResult に格納（例外は送出しない）
    """
    def register(self, pack: ScenarioPack) -> str: ...
    def get(self, pack_id: str) -> ScenarioPack: ...
    def list(self, query: str) -> list[ScenarioPack]: ...
    def create_from_template(self, name: str, template: str) -> ScenarioPack: ...
    def validate(self, path: Path) -> ValidationResult: ...
```

**実装側で必要となる属性の例:**

| 属性 | 型 | 説明 |
|---|---|---|
| registry_path | Path | レジストリの保存先パス |
| packs | dict[str, ScenarioPack] | 登録済みパックのマップ |

#### メソッド

**register**

| 項目 | 内容 |
|---|---|
| **Input** | `pack: ScenarioPack` -- 登録対象のシナリオパック |
| **Process** | パックのバリデーションを実施し、pack_idをキーとしてレジストリに登録する。既存のpack_idと重複する場合はバージョンを比較し、新規バージョンとして登録する。 |
| **Output** | `str` -- 登録されたpack_id。バリデーション失敗時は `ValidationError` を送出。 |

**get**

| 項目 | 内容 |
|---|---|
| **Input** | `pack_id: str` -- 取得対象のパックID |
| **Process** | レジストリからpack_idに一致するScenarioPackを検索して返却する。 |
| **Output** | `ScenarioPack` -- 該当するパック。見つからない場合は `PackNotFoundError` を送出。 |

**list**

| 項目 | 内容 |
|---|---|
| **Input** | `query: str` -- 検索クエリ文字列（名前・タグ等でフィルタ） |
| **Process** | レジストリ内のパックをクエリ条件でフィルタリングし、一致するパックのリストを返却する。 |
| **Output** | `list[ScenarioPack]` -- 条件に合致するパックのリスト。該当なしの場合は空リスト。 |

**create_from_template**

| 項目 | 内容 |
|---|---|
| **Input** | `name: str` -- 新規パック名, `template: str` -- テンプレート名 |
| **Process** | 指定テンプレートを基にディレクトリ構成とメタデータを生成し、新規ScenarioPackを構築する。 |
| **Output** | `ScenarioPack` -- 生成されたパック。テンプレートが存在しない場合は `TemplateNotFoundError` を送出。 |

**validate**

| 項目 | 内容 |
|---|---|
| **Input** | `path: Path` -- バリデーション対象のパックディレクトリパス |
| **Process** | パックのディレクトリ構造、メタデータスキーマ、必須ファイルの存在をチェックする。 |
| **Output** | `ValidationResult` -- バリデーション結果。構造不正の場合は結果オブジェクトにエラー詳細を格納。 |

---

## 3.4 CDL関連（REQ-F-003）

CDL（Common Data Language）ドメインクラスは全て `dataclass(frozen=True)` として定義し、イミュータブルとする。全クラスに共通メソッド `to_dict()` および `validate()` を実装する。

> **コンテナ型の使い分け:** frozen dataclass の内部属性には不変コンテナ `tuple` を使用する（第6章準拠）。メソッドの引数・戻り値には `list` を使用し、呼び出し側の利便性を確保する。
>
> **`parameters` 等の辞書状データの表現（v0.7 確定）:** 任意キー/値を持つパラメータ辞書も `tuple[tuple[str, object], ...]` で表現する（`dict` は使わない）。理由は (1) `dict` は mutable のため frozen の不変原則に反する、(2) `dict` は unhashable のため frozen dataclass のハッシュ可能性を破壊する、(3) 実験再現性を Domain レベルで保証したい。利用側で辞書として扱いたい場合は `dict(self.parameters)` で復元する。詳細経緯は `review_record.md` 論点6.1 参照。

### 3.4.1 クラス図

```mermaid
classDiagram
    class Topology {
        +str topology_id
        +str name
        +list~Node~ nodes
        +list~Edge~ edges
        +str source_bus
        +to_dict() dict
        +validate() None
    }

    class Node {
        +str node_id
        +str name
        +str node_type
        +float voltage_kv
        +tuple~float, float~|None coordinates
        +to_dict() dict
        +validate() None
    }

    class Edge {
        +str edge_id
        +str from_node
        +str to_node
        +str edge_type
        +float|None length_km
        +to_dict() dict
        +validate() None
    }

    class Asset {
        +str asset_id
        +str name
        +str asset_type
        +str node_id
        +float rated_power_kw
        +tuple~tuple~str,object~~ parameters
        +to_dict() dict
        +validate() None
    }

    class TimeSeries {
        +str series_id
        +str name
        +list~datetime~ timestamps
        +list~float~ values
        +str unit
        +float resolution_s
        +to_dict() dict
        +validate() None
    }

    class Event {
        +str event_id
        +str event_type
        +datetime timestamp
        +str target_id
        +str target_type
        +tuple~tuple~str,object~~ parameters
        +to_dict() dict
        +validate() None
    }

    class Metric {
        +str name
        +float value
        +str unit
        +int|None step
        +float|None threshold
        +to_dict() dict
        +validate() None
    }

    class ExperimentMetadata {
        +str experiment_id
        +datetime created_at
        +str scenario_pack_id
        +str connector
        +int|None seed
        +tuple~tuple~str,object~~ parameters
        +to_dict() dict
        +validate() None
    }

    Topology --> Node : nodes
    Topology --> Edge : edges
    Event ..> Node : "target (node)"
    Event ..> Edge : "target (edge)"
    Event ..> Asset : "target (asset)"
    ExperimentMetadata ..> TimeSeries : references
    ExperimentMetadata ..> Metric : references
```

### 3.4.2 共通メソッド

全CDLクラスは以下の共通メソッドを実装する。

**to_dict**

| 項目 | 内容 |
|---|---|
| **Input** | なし |
| **Process** | インスタンスの全属性を再帰的に辞書形式へ変換する。datetime型はISO 8601文字列、Path型は文字列に変換する。 |
| **Output** | `dict` -- 属性名をキーとした辞書。 |

**validate**

| 項目 | 内容 |
|---|---|
| **Input** | なし |
| **Process** | インスタンスの属性値に対して型チェック・値域チェック・整合性チェックを実施する。 |
| **Output** | `None`。バリデーション失敗時は `CDLValidationError` を送出。 |

### 3.4.3 Topology

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| topology_id | str | トポロジの一意識別子 |
| name | str | トポロジ名 |
| nodes | list[Node] | ノードのリスト |
| edges | list[Edge] | エッジのリスト |
| source_bus | str | 電源バスのノードID |

### 3.4.4 Node

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| node_id | str | ノードの一意識別子 |
| name | str | ノード名 |
| node_type | str | ノード種別（例: "bus", "load", "generator"） |
| voltage_kv | float | 定格電圧（kV） |
| coordinates | tuple[float, float] \| None | 地理座標（緯度, 経度）。不明時はNone |

### 3.4.5 Edge

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| edge_id | str | エッジの一意識別子 |
| from_node | str | 始点ノードID |
| to_node | str | 終点ノードID |
| edge_type | str | エッジ種別（例: "line", "transformer"） |
| length_km | float \| None | 線路長（km）。該当しない場合はNone |

### 3.4.6 Asset

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| asset_id | str | 機器の一意識別子 |
| name | str | 機器名 |
| asset_type | str | 機器種別（例: "pv", "battery", "load"） |
| node_id | str | 接続先ノードID（Node.node_id を参照） |
| rated_power_kw | float | 定格電力（kW） |
| parameters | tuple[tuple[str, object], ...] | 機器固有の追加パラメータ（不変。利用時は `dict(self.parameters)`） |

### 3.4.7 TimeSeries

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| series_id | str | 時系列データの一意識別子 |
| name | str | 時系列名 |
| timestamps | list[datetime] | タイムスタンプのリスト |
| values | list[float] | 値のリスト |
| unit | str | 単位（例: "kW", "V", "A"） |
| resolution_s | float | データ解像度（秒） |

### 3.4.8 Event

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| event_id | str | イベントの一意識別子 |
| event_type | str | イベント種別（例: "fault", "switch", "setpoint", "load_change", "generation_change"） |
| timestamp | datetime | イベント発生時刻 |
| target_id | str | 対象要素の識別子（Node.node_id, Edge.edge_id, または Asset.asset_id） |
| target_type | str | 対象要素の種別（"node" \| "edge" \| "asset"） |
| parameters | tuple[tuple[str, object], ...] | イベント固有のパラメータ（不変） |

### 3.4.9 Metric

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| name | str | 指標名（実験内で一意、PK） |
| value | float | 指標値 |
| unit | str | 単位 |
| step | int \| None | 対応するステップ番号。全体指標の場合はNone |
| threshold | float \| None | 閾値（超過で警告）。不要時はNone |

### 3.4.10 ExperimentMetadata

**モジュール:** `gridflow.domain.cdl`

| 属性 | 型 | 説明 |
|---|---|---|
| experiment_id | str | 実験の一意識別子 |
| created_at | datetime | 実験作成日時 |
| scenario_pack_id | str | 使用したシナリオパックのID |
| connector | str | 使用したコネクタ名 |
| seed | int \| None | 乱数シード。未指定時はNone |
| parameters | tuple[tuple[str, object], ...] | 実験パラメータ（不変） |

### 3.4.11 CanonicalData（Union型）

CDL エンティティの統一的な型表現。DataTranslator Protocol の入出力型として使用する。

```python
CanonicalData = Topology | Asset | TimeSeries | Event | Metric | ExperimentMetadata
```

### 3.4.12 CDLRepository（Protocol）

**モジュール:** `gridflow.usecase.interfaces`

CDL データの永続化・取得を担う UseCase 層 Protocol。

**store**

| 項目 | 内容 |
|---|---|
| **Input** | `data: CanonicalData` -- 格納対象の CDL データ |
| **Process** | データをシリアライズし、ストレージに書き込む。data_id を生成して返却する。 |
| **Output** | `str` -- 格納されたデータの一意識別子。 |

**get**

| 項目 | 内容 |
|---|---|
| **Input** | `data_id: str` -- 取得対象のデータ識別子 |
| **Process** | ストレージからデータを読み込み、デシリアライズして返却する。 |
| **Output** | `CanonicalData` -- 取得されたデータ。未発見時は `DataNotFoundError(RegistryError)` を送出。 |

**get_result**

| 項目 | 内容 |
|---|---|
| **Input** | `exp_id: str` -- 実験 ID |
| **Process** | 指定実験の全結果データを取得する。 |
| **Output** | `ExperimentResult` -- 実験結果。未発見時は `ExperimentNotFoundError(OrchestratorError)` を送出。 |

**export**

| 項目 | 内容 |
|---|---|
| **Input** | `exp_id: str` -- 実験 ID, `format: str` -- 出力フォーマット（"csv" / "json" / "parquet"）, `output_dir: Path` -- 出力先ディレクトリ |
| **Process** | 指定フォーマットで実験結果をファイルに出力する。 |
| **Output** | `Path` -- 出力ファイルパス。フォーマット未対応時は `UnsupportedFormatError(AdapterError)` を送出。 |

---

## 3.4+ シミュレーション結果型（REQ-F-002, REQ-F-004）

第7章（アルゴリズム設計）のメトリクス計算・バッチスケジューリングで使用するシミュレーション結果のデータ型を定義する。全て `dataclass(frozen=True)` とする。

### 3.4.13 ExperimentResult ＝ → 03e へ移設（v0.7）

> **移設通知:** `ExperimentResult` および新設の `StepResult` / `StepStatus` は **UseCase 層**として `03e_usecase_results.md` に定義する。本セクションは互換のため見出しのみ残す。
>
> **移設理由:** ExperimentResult は「Orchestrator.run() の戻り値」「BenchmarkHarness / MetricCalculator の入力」というユースケース実行の産物であり、Domain ルール（実験そのもの）ではなく UseCase の関心事である。Domain → UseCase の依存方向違反を避けつつ、`StepResult` を UseCase 層に置く決定（論点6.4）と整合させるため、ExperimentResult ごと UseCase 層へ移した。
>
> 詳細は [03e_usecase_results.md](03e_usecase_results.md) および `review_record.md` 論点6.4 を参照。
>
> なお、配下の Result 型群（NodeResult / BranchResult / LoadResult / GeneratorResult / RenewableResult / Interruption）は **Domain 層に残す**。これらは「シミュレータが返す物理的な観測値の表現」であり Domain 概念として扱う。UseCase 層の ExperimentResult はこれら Domain 型を集約する。

### 3.4.14 NodeResult

**モジュール:** `gridflow.domain.result`

ノード単位の時系列シミュレーション結果。

| 属性 | 型 | 説明 |
|---|---|---|
| node_id | str | 対象ノードID |
| voltages | tuple[float, ...] | 各ステップの電圧値（pu） |

#### メソッド

**voltage_at**

| 項目 | 内容 |
|---|---|
| **Input** | `step: int` -- ステップ番号 |
| **Process** | 指定ステップの電圧値を返却する。 |
| **Output** | `float` -- 電圧値（pu）。 |

### 3.4.15 BranchResult

**モジュール:** `gridflow.domain.result`

ブランチ（線路・変圧器）単位の時系列シミュレーション結果。

| 属性 | 型 | 説明 |
|---|---|---|
| edge_id | str | 対象エッジID |
| currents | tuple[float, ...] | 各ステップの電流値（A） |
| losses_kw | tuple[float, ...] | 各ステップの損失（kW） |
| i_rated | float | 定格電流（A） |

#### メソッド

| メソッド | Input | Output | 説明 |
|---|---|---|---|
| current_at | `step: int` | `float` | 指定ステップの電流値 |
| loss_kw_at | `step: int` | `float` | 指定ステップの損失 |

### 3.4.16 LoadResult

**モジュール:** `gridflow.domain.result`

負荷単位の時系列シミュレーション結果。

| 属性 | 型 | 説明 |
|---|---|---|
| asset_id | str | 対象負荷のアセットID |
| demands | tuple[float, ...] | 各ステップの需要（kW） |
| supplied | tuple[float, ...] | 各ステップの供給量（kW） |

#### メソッド

| メソッド | Input | Output | 説明 |
|---|---|---|---|
| demand_at | `step: int` | `float` | 指定ステップの需要 |
| supplied_at | `step: int` | `float` | 指定ステップの供給量 |

### 3.4.17 GeneratorResult

**モジュール:** `gridflow.domain.result`

発電機単位の時系列シミュレーション結果。

| 属性 | 型 | 説明 |
|---|---|---|
| asset_id | str | 対象発電機のアセットID |
| powers | tuple[float, ...] | 各ステップの出力（kW） |
| cost_per_unit | float | 単位発電コスト（USD/kWh） |
| emission_factor | float | CO2排出係数（tCO2/kWh） |

#### メソッド

| メソッド | Input | Output | 説明 |
|---|---|---|---|
| power_at | `step: int` | `float` | 指定ステップの出力 |

### 3.4.18 RenewableResult

**モジュール:** `gridflow.domain.result`

再エネ発電機単位の時系列シミュレーション結果。

| 属性 | 型 | 説明 |
|---|---|---|
| asset_id | str | 対象再エネ機のアセットID |
| available | tuple[float, ...] | 各ステップの可用出力（kW） |
| dispatched | tuple[float, ...] | 各ステップの実出力（kW） |

#### メソッド

| メソッド | Input | Output | 説明 |
|---|---|---|---|
| available_at | `step: int` | `float` | 指定ステップの可用出力 |
| dispatched_at | `step: int` | `float` | 指定ステップの実出力 |

### 3.4.19 Interruption

**モジュール:** `gridflow.domain.result`

停電イベントのデータモデル。IEEE 1366 信頼性指標（SAIDI/SAIFI/CAIDI）の計算入力として使用する。

| 属性 | 型 | 説明 |
|---|---|---|
| event_id | str | 停電イベントID |
| start_time | float | 停電開始時刻（秒） |
| end_time | float | 停電終了時刻（秒） |
| duration_min | float | 停電時間（分） |
| customers_affected | int | 影響を受けた顧客数 |
| cause | str | 原因（"fault" \| "maintenance" \| "overload"） |

### 3.4.20 SensitivityResult

**モジュール:** `gridflow.domain.result`

感度分析の結果データモデル。metric パラメータ（e.g. 電圧閾値 θ_low）を sweep した際の metric 値の曲線と特徴点を格納する。`SensitivityAnalyzer` (UseCase 層) が生成する。

Connector の再実行は不要であり、既存の `ExperimentResult` 群を post-processing して生成する点が `SweepResult` との本質的な違いである。

| 属性 | 型 | 説明 |
|---|---|---|
| feeder_id | str | 対象フィーダーの識別子 |
| parameter_name | str | sweep 対象のパラメータ名（e.g. "voltage_low"） |
| parameter_values | tuple[float, ...] | パラメータ値の grid |
| metric_name | str | 評価対象の metric 名（e.g. "hosting_capacity_mw"） |
| metric_values | tuple[float, ...] | 各パラメータ値での metric 値 |
| metric_ci95_low | tuple[float, ...] \| None | Bootstrap 95% CI 下限 |
| metric_ci95_high | tuple[float, ...] \| None | Bootstrap 95% CI 上限 |
| n_experiments | int | 元の Monte Carlo 実験数 |
| bootstrap_resamples | int \| None | Bootstrap リサンプル数 |

### 3.4.21 VoltageSensitivityMatrix

**モジュール:** `gridflow.domain.result`

bus 間の電圧感度行列。S[i][j] = ΔV_j / ΔP_i (bus i への有効電力注入 1 MW に対する bus j の電圧変化 pu) を格納する。

`SensitivityAnalyzer` が複数の `ExperimentResult` の差分から数値的に推定するか、ソルバー固有の手法（OpenDSS の SystemY、pandapower の Jacobian）から取得する。後者の場合は Adapter 層の具象 Connector が Protocol 外のメソッドとして提供し、`SensitivityAnalyzer` が `isinstance` で型絞りして利用する。

| 属性 | 型 | 説明 |
|---|---|---|
| bus_ids | tuple[str, ...] | bus ID の順序付きリスト |
| matrix | tuple[tuple[float, ...], ...] | 感度行列 S[i][j] (行 = 注入 bus, 列 = 応答 bus) |
| max_singular_value | float | S の最大特異値（worst-case 感度の上界） |
| dominant_injection_bus | str | 最大特異値に対応する注入 bus |
| dominant_response_bus | str | 最大特異値に対応する応答 bus |

---

> **関連文書:** Connector・Benchmark・UseCase は → [03b ユースケース層](03b_usecase_classes.md) / StepResult・ExperimentResult は → [03e UseCase結果型](03e_usecase_results.md) / CLI・Plugin は → [03c アダプタ層](03c_adapter_classes.md) / Orchestrator・共通基盤・トレースは → [03d インフラ層](03d_infra_classes.md)
