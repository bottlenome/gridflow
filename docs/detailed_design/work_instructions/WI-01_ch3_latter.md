# WI-01: 第3章後半（3.5〜3.9）

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/03_class_design.md` に追記
**前提**: 3.1〜3.4は既に書かれている。Readで既存内容を読み、末尾に追記した全体をWriteする。
**共通ルール**: `WI-00_common.md` 参照

---

## 3.5 Connector 関連クラス設計（REQ-F-007）

### 設計に必要な情報

```python
# ConnectorInterface Protocol
class ConnectorInterface(Protocol):
    def initialize(self, config: dict[str, Any]) -> None: ...
    def execute(self, step: int, context: dict[str, Any]) -> StepResult: ...
    def health_check(self) -> HealthStatus: ...
    def teardown(self) -> None: ...

@dataclass(frozen=True)
class StepResult:
    status: str          # "success" | "warning" | "error"
    data: dict[str, Any] # CDL準拠の出力データ
    elapsed_ms: float

@dataclass(frozen=True)
class HealthStatus:
    healthy: bool
    message: str

# DataTranslator Protocol
class DataTranslator(Protocol):
    def to_canonical(self, raw: Any) -> CanonicalData: ...
    def from_canonical(self, data: CanonicalData) -> Any: ...
```

### 記述すべきクラス
- ConnectorInterface (Protocol) — UseCase層に定義（DIP原則）
- OpenDSSConnector — Adapter層。py-dss-interface経由。DSSスクリプト(.dss)入力。出力CDL: Topology, Asset, TimeSeries, Metric
- DataTranslator (Protocol) + OpenDSSTranslator
- StepResult, HealthStatus (dataclass)

### REST API仕様表
Connector間通信はREST。以下のエンドポイント表を含めること:

| メソッド | パス | 説明 |
|---|---|---|
| POST | /initialize | Connector初期化 |
| POST | /execute | 1ステップ実行 |
| GET | /health | ヘルスチェック |
| POST | /teardown | 終了・リソース解放 |

---

## 3.6 Benchmark 関連クラス設計（REQ-F-004）

### 設計に必要な情報

標準指標8件:

| 指標名 | 単位 | 説明 |
|---|---|---|
| voltage_deviation | % | ノード電圧の基準値からの逸脱率 |
| thermal_overload_hours | h | 熱容量超過の累積時間 |
| energy_not_supplied | MWh | 供給不能エネルギー量 |
| dispatch_cost | USD | 発電コスト |
| co2_emissions | tCO2 | CO2排出量 |
| curtailment | MWh | 出力抑制量 |
| restoration_time | s | 復旧時間 |
| runtime | s | シミュレーション実行時間 |

```python
class MetricCalculator(Protocol):
    @property
    def name(self) -> str: ...
    def calculate(self, experiment_result: ExperimentResult) -> MetricValue: ...
```

### 記述すべきクラス
- BenchmarkHarness — run(experiment_ids, metric_names)→BenchmarkReport, compare(a,b)→ComparisonReport, export(report,format,path)→Path
- MetricCalculator (Protocol) — Strategy パターン
- ReportGenerator — generate(report, format)→str/bytes
- VoltageDeviationCalculator, ThermalOverloadCalculator 等は一覧で言及

---

## 3.7 CLI 関連クラス設計（REQ-F-005）

### 設計に必要な情報

トップレベルコマンド10個:

| コマンド | 説明 | 関連UC |
|---|---|---|
| `gridflow run` | 実験実行 | UC-01 |
| `gridflow scenario` | Scenario Pack管理 | UC-02 |
| `gridflow benchmark` | ベンチマーク評価 | UC-03 |
| `gridflow status` | 実行状態確認 | UC-04 |
| `gridflow logs` | ログ表示 | UC-05 |
| `gridflow trace` | トレース表示 | UC-05 |
| `gridflow metrics` | メトリクス表示 | UC-05 |
| `gridflow debug` | デバッグ情報 | UC-06 |
| `gridflow results` | 結果表示・エクスポート | UC-09 |
| `gridflow update` | 自己更新 | UC-08 |

scenarioサブコマンド: create, list, clone, validate, register
グローバルオプション: --format(json|table|plain), --verbose, --quiet, --config
終了コード: 0=成功, 1=一般エラー, 2=引数エラー, 3=設定エラー, 4=実行エラー

### 記述すべきクラス
- CLIApp — エントリポイント。clickまたはtyper使用
- CommandHandler — 各コマンドのハンドラー基底
- OutputFormatter — テーブル/JSON/カラー出力の切替

### 追加要素
- CLI出力フォーマット仕様（テーブル/JSON/plain各形式のサンプル出力）
- CLI状態遷移図（Mermaid stateDiagram: 起動→コマンド解析→実行→出力→終了）

---

## 3.8 Plugin API 関連クラス設計（REQ-F-006）

### 設計に必要な情報

L1-L4カスタマイズレベル:

| レベル | 名称 | 対象ユーザ | 必要スキル | 変更範囲 |
|---|---|---|---|---|
| L1 | 設定変更 | 全研究者 | YAML編集 | パラメータ値 |
| L2 | プラグイン開発 | 中級 | Python基礎 | カスタムConnector/Metric（<100行） |
| L3 | パイプライン構成 | 上級 | Python+Docker | ワークフロー再構成 |
| L4 | ソース改変 | 開発者 | フルスタック | コア機能変更（フォーク） |

### 記述すべきクラス
- PluginRegistry — register(plugin), get(name), list_all()
- PluginDiscovery — discover(plugin_dir)→list[PluginInfo], load(info)→Plugin
- L1Config — YAML設定のバリデーション・適用
- L2PluginBase — Protocol。カスタムConnector/MetricCalculatorの基底
- L3PipelineConfig — パイプライン定義のパース・検証
- L4SourceExtension — フォークポイント定義

---

## 3.9 共通基盤クラス設計（REQ-Q-008, REQ-Q-009）

### 記述すべきクラス
- StructuredLogger — structlog使用。JSON Lines形式。レベル5段階(DEBUG/INFO/WARNING/ERROR/CRITICAL)。bind(context)でコンテキスト付与
- ConfigManager — YAML設定読込。優先順位: CLI > 環境変数 > プロジェクト設定 > ユーザー設定 > デフォルト値。get(key), set(key,value), validate()
- ErrorHandler — GridflowError基底。format_error(e)→str, handle(e)→None, to_exit_code(e)→int
