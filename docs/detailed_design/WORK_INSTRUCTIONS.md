# 詳細設計書 作業指示書

アーキテクト（メインエージェント）が基本設計書・アーキテクチャドキュメントから必要情報を抽出し、設計者エージェントへの指示に埋め込む。設計者は本ファイルの該当セクションを参照して作業する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（第3章後半〜第11章の作業指示） |

---

## 共通ルール

- 各メソッドは **IPO形式**: Input（引数・型）→ Process（処理概要）→ Output（戻り値・型・例外）
- Mermaid図を積極活用（classDiagram, sequenceDiagram, stateDiagram-v2, erDiagram, flowchart）
- 更新履歴を各ファイル冒頭に含める（版数0.1, 日付2026-04-03）
- 関連要件ID（REQ-xxx）を各セクション冒頭に明記
- **入力ファイルを自分で読まない**: 本指示書に埋め込まれた情報のみで作業する

---

## WI-01: 第3章後半（3.5〜3.9）

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/03_class_design.md` に追記
**前提**: 3.1〜3.4は既に書かれている。Readで既存内容を読み、末尾に追記した全体をWriteする。

### 3.5 Connector 関連クラス設計（REQ-F-007）

基本設計から抽出した情報:

```python
# ConnectorInterface Protocol（基本設計06章）
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

クラス: ConnectorInterface, OpenDSSConnector, DataTranslator, StepResult, HealthStatus
REST API仕様: Connector間通信は REST（POST /execute, GET /health, POST /initialize, POST /teardown）
OpenDSS固有: py-dss-interface経由、DSSスクリプト(.dss)入力、出力CDLエンティティ=Topology,Asset,TimeSeries,Metric

### 3.6 Benchmark 関連クラス設計（REQ-F-004）

基本設計から抽出した情報:

標準指標8件: voltage_deviation(%), thermal_overload_hours(h), energy_not_supplied(MWh), dispatch_cost(USD), co2_emissions(tCO2), curtailment(MWh), restoration_time(s), runtime(s)

```python
# MetricCalculator Protocol（基本設計03章3.6節）
class MetricCalculator(Protocol):
    @property
    def name(self) -> str: ...
    def calculate(self, experiment_result: ExperimentResult) -> MetricValue: ...
```

クラス: BenchmarkHarness（run, compare, export）, MetricCalculator(Protocol), ReportGenerator
Strategy パターンでカスタム指標追加を容易に。

### 3.7 CLI 関連クラス設計（REQ-F-005）

基本設計から抽出した情報:

トップレベルコマンド10個:
- `gridflow run` (UC-01), `gridflow scenario` (UC-02), `gridflow benchmark` (UC-03)
- `gridflow status` (UC-04), `gridflow logs` (UC-05), `gridflow trace` (UC-05)
- `gridflow metrics` (UC-05), `gridflow debug` (UC-06), `gridflow results` (UC-09)
- `gridflow update` (UC-08)

scenarioサブコマンド: create, list, clone, validate, register
benchmarkサブコマンド: run, export
resultsサブコマンド: show, export

グローバルオプション: --format(json|table|plain), --verbose, --quiet, --config
終了コード: 0=成功, 1=一般エラー, 2=引数エラー, 3=設定エラー, 4=実行エラー

CLI出力フォーマット仕様（テーブル/JSON/カラー）とCLI状態遷移図を含めること。

### 3.8 Plugin API 関連クラス設計（REQ-F-006）

基本設計から抽出した情報:

L1-L4カスタマイズレベル:
- L1(設定変更): YAML/TOML編集。パラメータ値の変更のみ
- L2(プラグイン開発): Python Protocol実装。カスタムConnector/Metric追加（<100行）
- L3(パイプライン構成): ワークフロー再構成。Python+Docker必要
- L4(ソース改変): フォーク。フルスタックスキル必要

IF一覧: IF-02(L1 YAML), IF-03(L2 Protocol), IF-04(L3 Protocol), IF-05(L4 Fork)
クラス: PluginRegistry, PluginDiscovery, L1Config, L2PluginBase, L3PipelineConfig, L4SourceExtension

### 3.9 共通基盤クラス設計（REQ-Q-008, REQ-Q-009）

クラス: StructuredLogger, ConfigManager, ErrorHandler
- StructuredLogger: structlog使用。JSON Lines形式。ログレベル5段階。
- ConfigManager: YAML設定読込。優先順位: CLI > 環境変数 > プロジェクト > ユーザー > デフォルト
- ErrorHandler: GridflowError基底。レイヤー別例外捕捉。エラーコードE-{レイヤー2桁}{連番3桁}

---

## WI-02: 第4章前半（4.1〜4.5）

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/04_process_flow.md` を新規作成

UC一覧（アーキテクチャ04_dynamic_viewより）:
- UC-01: 実験実行（Researcher→gridflow run→Orchestrator→Connector→CDL→結果表示）
- UC-02: Scenario Pack管理（create/list/clone/validate/register）
- UC-03: ベンチマーク評価・比較（benchmark run→MetricCalculator→ReportGenerator）
- UC-04: 起動・終了（docker compose up/down、ヘルスチェック）

各UCにシーケンス図(sequenceDiagram)を必須、分岐・並行処理にはアクティビティ図(flowchart)を併記。
4.5はバッチ処理設計（入力→加工→出力→スケジュール→異常時処理）を含む。

---

## WI-03: 第4章後半（4.6〜4.15）

**対象ファイル**: 4.1〜4.5が書かれた04_process_flow.mdに追記

- 4.6 UC-05 ログ・実行トレース: gridflow logs/trace/metricsコマンドの内部フロー
- 4.7 UC-06 デバッグ・エラー対応: gridflow debugコマンド、エラー診断フロー
- 4.8 UC-07 インストール・セットアップ: docker compose pull→設定生成→ヘルスチェック
- 4.9 UC-08 アップデート・アンインストール: gridflow update、イメージ更新フロー
- 4.10 UC-09 結果参照・データエクスポート: gridflow results show/export
- 4.11 UC-10 LLM実験指示: 構造化I/O(JSON/YAML)でLLMからのコマンド受付
- 4.12 Connector初期化・実行: initialize→execute(step loop)→teardown
- 4.13 CDL変換: raw→DataTranslator.to_canonical()→CDL→DataTranslator.from_canonical()→native
- 4.14 Pluginロード・実行: PluginDiscovery→PluginRegistry→load→execute
- 4.15 エラーハンドリング: Domain→UseCase→Adapter→ユーザー表示の例外伝播フロー

---

## WI-04: 第5章 状態遷移設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/05_state_transition.md` を新規作成

### 5.1 Orchestrator状態遷移
状態: Idle→Initializing→Ready→Running→Collecting→Completed/Failed
イベント: run_requested, containers_ready, step_completed, all_steps_done, error_occurred, reset

### 5.2 Connector状態遷移
状態: Disconnected→Connecting→Connected→Executing→Idle→Disconnecting
イベント: initialize_called, connection_established, execute_called, step_done, teardown_called

### 5.3 Scenario Packライフサイクル
状態: Draft→Validated→Registered→Running→Completed→Archived
イベント: validate, register, run, complete, archive

### 5.4 バッチジョブ状態遷移
状態: Queued→Running→Succeeded/Failed/Cancelled
イベント: dequeue, complete, fail, cancel, retry

各状態遷移にMermaid stateDiagram-v2 + 状態遷移表（状態×イベントマトリクス）をセットで。

---

## WI-05: 第7章 アルゴリズム設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/07_algorithm.md` を新規作成

### 7.1 時間同期アルゴリズム
3方式: Orchestrator-driven(OpenDSS等), Federation-driven(HELICS), Hybrid
疑似コードでステップ制御ループを記述。

### 7.2 Benchmarkメトリクス計算
8指標の計算式・疑似コード:
- voltage_deviation = max(|V_node - V_nominal| / V_nominal * 100) [%]
- thermal_overload_hours = Σ(t_overload) [h]
- energy_not_supplied = Σ(P_demand - P_supplied) * Δt [MWh]
- dispatch_cost = Σ(P_gen * cost_gen) * Δt [USD]
- co2_emissions = Σ(P_gen * emission_factor) * Δt [tCO2]
- curtailment = Σ(P_available - P_dispatched) * Δt [MWh]
- restoration_time = t_restored - t_fault [s]
- runtime = t_end - t_start [s]

### 7.3 バッチスケジューリング: FIFO + 並列度制御
### 7.4 Scenario Packバージョン管理: SemVer + content hash
### 7.5 Plugin依存解決: トポロジカルソート
### 7.6 性能設計: QA-10基準(5%以下オーバーヘッド)、測定方法、最適化方針

---

## WI-06: 第10章 テスト詳細設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/10_test_detail.md` を新規作成

テストピラミッド: 単体70%・統合20%・E2E10%。カバレッジ目標80%。pytest使用。
単体テスト最低20件（UT-001〜UT-020）、統合テスト最低5件（IT-001〜IT-005）、E2Eテスト最低3件（E2E-001〜E2E-003）。
QA-1〜QA-11の検証方法表。テストデータ・フィクスチャ設計。

---

## WI-07: 第11章 ビルド・デプロイ詳細設計

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/11_build_deploy.md` を新規作成

Dockerfile: マルチステージビルド（builder→runtime）、gridflow-core用 + connector用
Docker Compose: 具体的YAML（コメント付き）
CI/CD: GitHub Actions 6ステージ（lint→typecheck→test→integration→build→publish）
pyproject.toml構成、SemVerルール

---

## WI-08: 付録

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/appendix.md` を新規作成

A. 全REQ-xxx → DD-xxx完全対応表（01_requirements.mdの1.2節を再掲・更新）
B. 用語集（基本設計書付録準拠 + 詳細設計固有: IPO, Protocol, dataclass等）
C. 参考文献（IPA共通フレーム2013, Clean Architecture, Python PEP 8等）
D. 更新ドキュメント一覧（全ファイルの作成日・更新日）
