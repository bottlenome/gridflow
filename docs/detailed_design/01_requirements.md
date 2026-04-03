# 第1章 要件一覧

本章では、基本設計書の全要求（REQ-xxx）を詳細設計 ID（DD-xxx）に対応付け、基本設計から詳細設計へのトレーサビリティを確立する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |

---

## 1.1 詳細設計 ID 体系

基本設計書の REQ-xxx 体系を継承し、詳細設計固有の ID を追加する。

| 接頭辞 | 分類 | 例 | 説明 |
|---|---|---|---|
| `DD-MOD-xxx` | モジュール設計 | DD-MOD-001 | パッケージ・モジュール定義 |
| `DD-CLS-xxx` | クラス設計 | DD-CLS-001 | クラス・属性・メソッド定義 |
| `DD-SEQ-xxx` | シーケンス設計 | DD-SEQ-001 | 内部処理フロー定義 |
| `DD-STT-xxx` | 状態遷移設計 | DD-STT-001 | 状態遷移図・遷移条件 |
| `DD-DAT-xxx` | データ詳細設計 | DD-DAT-001 | 型定義・制約・バリデーション |
| `DD-ALG-xxx` | アルゴリズム設計 | DD-ALG-001 | 計算ロジック・疑似コード |
| `DD-ERR-xxx` | エラー設計 | DD-ERR-001 | 例外クラス・エラーコード |
| `DD-CFG-xxx` | 設定管理設計 | DD-CFG-001 | 設定項目・デフォルト値 |
| `DD-TST-xxx` | テスト設計 | DD-TST-001 | テストケース・期待値 |
| `DD-BLD-xxx` | ビルド・デプロイ設計 | DD-BLD-001 | Dockerfile・CI/CD 定義 |

### トレーサビリティチェーン

```
REQ-B-001 (BG-1)
  → REQ-F-001 (FR-01)                    ← 基本設計書 要求一覧
    → FN-001 (Scenario Pack 管理)         ← 基本設計書 第3章 機能設計
      → DD-CLS-001 (ScenarioPack)         ← 詳細設計書 第3章 クラス設計
      → DD-CLS-002 (ScenarioRegistry)     ← 詳細設計書 第3章 クラス設計
      → DD-SEQ-001 (Pack 作成フロー)       ← 詳細設計書 第4章 処理フロー設計
      → DD-DAT-001 (pack.yaml スキーマ)   ← 詳細設計書 第6章 データ詳細設計
      → DD-TST-001 (Pack 作成テスト)       ← 詳細設計書 第10章 テスト設計
```

---

## 1.2 要件一覧表（REQ-xxx → DD-xxx 対応）

### 1.2.1 ビジネス要求

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-B-001 | E2E ループ高速化 | DD-SEQ-001, DD-SEQ-002, DD-CLS-007〜009 | Orchestrator・Connector による実行自動化で対応 |
| REQ-B-002 | 共同研究基盤として普及 | DD-CLS-010〜012, DD-BLD-001 | CLI の導入容易性、Plugin による拡張性で対応 |
| REQ-B-003 | 再現性の制度的担保 | DD-CLS-001〜002, DD-DAT-001, DD-ALG-004 | Scenario Pack + seed 管理 + バージョン管理で対応 |
| REQ-B-004 | 研究フロー・評価の標準化 | DD-CLS-013〜015, DD-ALG-002 | BenchmarkHarness + 標準メトリクスで対応 |

### 1.2.2 機能要求（P0: 最小必須機能）

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-F-001 | Scenario Pack + Registry | DD-CLS-001 (ScenarioPack), DD-CLS-002 (PackMetadata), DD-CLS-003 (ScenarioRegistry), DD-DAT-001 (pack.yaml スキーマ), DD-SEQ-003 (Pack 作成・登録フロー), DD-STT-003 (Pack ライフサイクル) | FN-001 対応 |
| REQ-F-002 | Orchestrator | DD-CLS-007 (Orchestrator), DD-CLS-008 (ExecutionPlan), DD-CLS-009 (ContainerManager), DD-CLS-024 (TimeSync), DD-SEQ-001 (シナリオ実行フロー), DD-STT-001 (Orchestrator 状態遷移), DD-SEQ-005 (バッチ実行フロー) | FN-002 対応 |
| REQ-F-003 | Canonical Data Layer | DD-CLS-004 (Topology), DD-CLS-005 (Asset), DD-CLS-006 (TimeSeries), DD-CLS-025 (Event), DD-CLS-026 (Metric), DD-CLS-027 (ExperimentMetadata), DD-DAT-002〜007 (CDL エンティティ定義), DD-SEQ-013 (CDL 変換フロー) | FN-004 対応 |
| REQ-F-004 | Benchmark Harness | DD-CLS-013 (BenchmarkHarness), DD-CLS-014 (MetricCalculator), DD-CLS-015 (ReportGenerator), DD-ALG-002 (メトリクス計算), DD-SEQ-004 (ベンチマーク実行フロー) | FN-005 対応 |
| REQ-F-005 | CLI + Notebook Bridge | DD-CLS-010 (CLIApp), DD-CLS-011 (CommandHandler), DD-CLS-012 (OutputFormatter), DD-SEQ-009〜011 (CLI 関連フロー) | FN-006, FN-007 対応 |
| REQ-F-006 | 段階的カスタムレイヤー | DD-CLS-016 (PluginRegistry), DD-CLS-017 (PluginDiscovery), DD-SEQ-014 (Plugin ロードフロー), DD-ALG-005 (Plugin 依存解決) | FN-009 対応 |
| REQ-F-007 | Connectors | DD-CLS-018 (ConnectorInterface), DD-CLS-019 (OpenDSSConnector), DD-CLS-020 (DataTranslator), DD-SEQ-012 (Connector 初期化・実行フロー), DD-STT-002 (Connector 状態遷移), DD-DAT-006 (データ変換マッピング) | FN-003 対応 |

### 1.2.3 機能要求（P1: 実用性向上機能）

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-F-008 | Record / Replay | — | P1 スコープ（本版では対象外） |
| REQ-F-009 | Experiment Diff | — | P1 スコープ（本版では対象外） |
| REQ-F-010 | Result Lineage | — | P1 スコープ（本版では対象外） |
| REQ-F-011 | Cache / Resume | — | P1 スコープ（本版では対象外） |
| REQ-F-012 | Profiling | — | P1 スコープ（本版では対象外） |
| REQ-F-013 | Leaderboard | — | P1 スコープ（本版では対象外） |
| REQ-F-014 | Team Workspace | — | P1 スコープ（本版では対象外） |
| REQ-F-015 | Fault Injection | — | P1 スコープ（本版では対象外） |
| REQ-F-016 | Sensitivity Sweep | — | P1 スコープ（本版では対象外） |

### 1.2.4 機能要求（P2: 高度化機能）

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-F-017 | HIL 連携 | — | P2 スコープ（本版では対象外） |
| REQ-F-018 | Cyber Co-simulation | — | P2 スコープ（本版では対象外） |
| REQ-F-019 | 標準プロトコル対応 | — | P2 スコープ（本版では対象外） |
| REQ-F-020 | Standards Validation | — | P2 スコープ（本版では対象外） |
| REQ-F-021 | Operator HMI | — | P2 スコープ（本版では対象外） |

### 1.2.5 品質要求

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-Q-001 | 導入容易性 | DD-BLD-001 (Dockerfile), DD-BLD-002 (Docker Compose), DD-CFG-001 (設定項目) | セットアップ < 30分、成功率 > 90% |
| REQ-Q-002 | 初回利用効率 | DD-CLS-010〜012 (CLI 設計), DD-SEQ-008 (セットアップフロー) | Time to First Simulation < 1時間 |
| REQ-Q-003 | 再現性 | DD-CLS-001 (ScenarioPack), DD-DAT-001 (pack.yaml), DD-ALG-004 (バージョン管理) | seed + Docker による環境固定 |
| REQ-Q-004 | 拡張性 | DD-CLS-016〜017 (Plugin 設計), DD-CLS-018 (ConnectorInterface) | L2 Plugin < 100行 |
| REQ-Q-005 | ワークフロー効率 | DD-SEQ-001 (シナリオ実行), DD-SEQ-004 (ベンチマーク実行) | ベースライン再現 < 1時間 |
| REQ-Q-006 | データエクスポート容易性 | DD-CLS-015 (ReportGenerator), DD-DAT-004 (エクスポート仕様) | 変換ステップ < 3 |
| REQ-Q-007 | ポータビリティ | DD-BLD-001 (Dockerfile マルチアーキテクチャ), DD-TST-005 (クロスアーキテクチャテスト) | AMD64 + ARM64 |
| REQ-Q-008 | 可観測性 | DD-CLS-021 (StructuredLogger), DD-ERR-001 (ログ出力仕様) | FN-008 対応 |
| REQ-Q-009 | LLM 親和性 | DD-CLS-012 (OutputFormatter), DD-ERR-002 (構造化エラー) | JSON/YAML 構造化 I/O |
| REQ-Q-010 | 性能効率 | DD-ALG-001 (時間同期), DD-ALG-003 (バッチスケジューリング), DD-TST-006 (性能テスト) | オーバーヘッド < 5% |
| REQ-Q-011 | 論文生産性 | DD-CLS-013〜015 (Benchmark 設計), DD-DAT-004 (エクスポート仕様) | 年間 10本以上 |

### 1.2.6 制約

| 要求 ID | 制約名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-C-001 | Python 実装 | DD-MOD-001〜010 (全モジュール設計) | Python 3.11+ |
| REQ-C-002 | Docker 環境 | DD-BLD-001〜002 (Dockerfile, Docker Compose), DD-CFG-004 (Docker Compose 設定) | Docker Compose 標準デプロイ |
| REQ-C-003 | 1人 + AI 開発 | DD-MOD-001 (パッケージ構成), DD-CLS-全般 | アーキテクチャ複雑さの上限規定 |
| REQ-C-004 | マルチアーキテクチャ | DD-BLD-001 (Dockerfile マルチステージ), DD-TST-005 (クロスアーキテクチャテスト) | AMD64 + ARM64 |
| REQ-C-005 | OSS 公開 | DD-DAT-001 (Scenario Pack format), DD-DAT-002〜007 (CDL スキーマ), DD-CLS-018 (Connector SDK) | 公開フォーマット仕様 |
| REQ-C-006 | 英語標準 | DD-ERR-001〜002 (エラーメッセージ), DD-CLS-012 (OutputFormatter) | ドキュメント・メッセージ英語 |

---

## 1.3 基本設計 → 詳細設計 トレーサビリティマトリクス

基本設計書の各章が詳細設計書のどの章・セクションに展開されるかを示す。

| 基本設計書の章 | 内容 | 詳細設計書 展開先 | 詳細化の内容 |
|---|---|---|---|
| 第1章 要求一覧 | REQ-xxx 定義 | 第1章 要件一覧 | DD-xxx ID 追加、FN-xxx → モジュール → クラス対応表追加 |
| 第2章 システム方式設計 | Docker 構成・ネットワーク | 第2章 モジュール構成 + 第9章 設定管理 + 第11章 ビルド・デプロイ | Docker 構成 → Dockerfile・Compose 具体設計、ネットワーク設定 |
| 第3章 機能設計 | FN-001〜FN-009 | 第3章 クラス設計 + 第4章 処理フロー設計 + 第8章 エラー設計 | 機能 → クラス・メソッド（IPO 形式）・処理フロー（全 FN 展開） |
| 第4章 CLI 設計 | コマンド体系 | 第3章 3.7 CLI クラス設計 + 第4章 処理フロー設計 | コマンド体系 → CLI パーサー・ハンドラー・出力フォーマット実装設計 |
| 第5章 データ設計 | CDL スキーマ | 第3章 3.4 CDL クラス + 第6章 データ詳細設計 + 第9章 設定管理 | CDL スキーマ → 型定義・制約・バリデーション・エクスポータ設計 |
| 第6章 外部 IF 設計 | Connector・Plugin IF | 第3章 3.5 Connector + 第3章 3.8 Plugin API + 第4章 4.12〜4.14 | Protocol 仕様 → 具体クラス・API 仕様・シーケンス |
| 第7章 性能設計 | 性能目標・ボトルネック | 第7章 アルゴリズム設計 + 第10章 テスト設計 | ボトルネック対策 → 最適化アルゴリズム + 性能テスト設計 |
| 第8章 信頼性設計 | 信頼性方針 | 第5章 状態遷移 + 第8章 エラー設計 | 信頼性方針 → 例外階層・リトライ・再現性保証の具体設計 |
| 第9章 セキュリティ設計 | 脅威モデル | 第9章 設定管理 + 第11章 Dockerfile | 脅威モデル → コンテナ設定・非 root 実行・secrets 管理 |
| 第10章 移行・導入設計 | 導入手順 | 第11章 ビルド・デプロイ + 第6章 データ詳細設計 + 第9章 設定管理 | 導入手順 → Dockerfile・スクリプト・マイグレーション具体設計 |
| 第11章 テスト方針 | テスト戦略 | 第10章 テスト詳細設計 | テスト方針 → テストケース・フィクスチャ設計 |
| 第12章 運用・保守設計 | 運用方針 | 第8章 ログ出力仕様 + 第9章 設定管理 + 第10章 テスト + 第11章 ビルド・デプロイ | 運用方針 → 監視設定・ログフォーマット・リリースサイクル具体設計 |

---

## 1.4 機能 ID → モジュール → クラス 対応表

FN-001〜FN-009（基本設計書 第3章）から、Clean Architecture に基づくモジュール・クラスへの展開を示す。

| 機能 ID | 機能名 | モジュール | 主要クラス |
|---|---|---|---|
| FN-001 | Scenario Pack 管理 | `gridflow.domain.scenario` | ScenarioPack, PackMetadata |
| | | `gridflow.infra.registry` | ScenarioRegistry |
| FN-002 | 実験実行オーケストレーション | `gridflow.infra.orchestrator` | Orchestrator, ExecutionPlan, ContainerManager, TimeSync |
| FN-003 | Connector 統合 | `gridflow.adapter.connector` | ConnectorInterface, OpenDSSConnector, DataTranslator |
| FN-004 | Canonical Data Layer | `gridflow.domain.cdl` | Topology, Asset, TimeSeries, Event, Metric, ExperimentMetadata |
| FN-005 | ベンチマーク評価 | `gridflow.adapter.benchmark` | BenchmarkHarness, MetricCalculator, ReportGenerator |
| FN-006 | CLI インターフェース | `gridflow.adapter.cli` | CLIApp, CommandHandler, OutputFormatter |
| FN-007 | Notebook Bridge | `gridflow.adapter.cli` | CLIApp（共有）|
| | | `gridflow.usecase` | RunSimulation, CompareBenchmark, ImportScenario |
| FN-008 | ロギング・トレーシング | `gridflow.infra.logging` | StructuredLogger |
| FN-009 | 段階的カスタムレイヤー | `gridflow.infra.plugin` | PluginRegistry, PluginDiscovery |
| （共通） | 設定管理 | `gridflow.infra.config` | ConfigManager |

### Clean Architecture レイヤー別モジュール配置

```
Domain 層（ビジネスルール）
├── gridflow.domain.scenario    — ScenarioPack, PackMetadata
└── gridflow.domain.cdl         — Topology, Asset, TimeSeries, Event, Metric, ExperimentMetadata

Use Case 層（アプリケーションロジック）
└── gridflow.usecase            — RunSimulation, CompareBenchmark, ImportScenario

Adapter 層（外部変換）
├── gridflow.adapter.connector  — ConnectorInterface, OpenDSSConnector, DataTranslator
├── gridflow.adapter.cli        — CLIApp, CommandHandler, OutputFormatter
└── gridflow.adapter.benchmark  — BenchmarkHarness, MetricCalculator, ReportGenerator

Infrastructure 層（技術基盤）
├── gridflow.infra.orchestrator — Orchestrator, ExecutionPlan, ContainerManager, TimeSync
├── gridflow.infra.registry     — ScenarioRegistry
├── gridflow.infra.plugin       — PluginRegistry, PluginDiscovery
├── gridflow.infra.logging      — StructuredLogger
└── gridflow.infra.config       — ConfigManager
```

### 依存方向

```
Adapter 層 → Use Case 層 → Domain 層
Infrastructure 層 → Use Case 層 → Domain 層
```

Domain 層は他のどの層にも依存しない。Use Case 層は Domain 層のみに依存する。Adapter 層・Infrastructure 層は Use Case 層と Domain 層に依存するが、相互には依存しない。
