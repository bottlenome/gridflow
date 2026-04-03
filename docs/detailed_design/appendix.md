# 付録
## 更新履歴
| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |

---

## A. 要件一覧（全 REQ-xxx → DD-xxx 完全対応表）

> 本節は `01_requirements.md` 1.2節の内容を再掲したものである。正式版は [第1章 要件一覧](./01_requirements.md#12-要件一覧表req-xxx--dd-xxx-対応) を参照のこと。

### A.1 ビジネス要求

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-B-001 | E2E ループ高速化 | DD-SEQ-001, DD-SEQ-002, DD-CLS-007〜009 | Orchestrator・Connector による実行自動化で対応 |
| REQ-B-002 | 共同研究基盤として普及 | DD-CLS-010〜012, DD-BLD-001 | CLI の導入容易性、Plugin による拡張性で対応 |
| REQ-B-003 | 再現性の制度的担保 | DD-CLS-001〜002, DD-DAT-001, DD-ALG-004 | Scenario Pack + seed 管理 + バージョン管理で対応 |
| REQ-B-004 | 研究フロー・評価の標準化 | DD-CLS-013〜015, DD-ALG-002 | BenchmarkHarness + 標準メトリクスで対応 |

### A.2 機能要求（P0: 最小必須機能）

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-F-001 | Scenario Pack + Registry | DD-CLS-001 (ScenarioPack), DD-CLS-002 (PackMetadata), DD-CLS-003 (ScenarioRegistry), DD-DAT-001 (pack.yaml スキーマ), DD-SEQ-003 (Pack 作成・登録フロー), DD-STT-003 (Pack ライフサイクル) | FN-001 対応 |
| REQ-F-002 | Orchestrator | DD-CLS-007 (Orchestrator), DD-CLS-008 (ExecutionPlan), DD-CLS-009 (ContainerManager), DD-CLS-024 (TimeSync), DD-SEQ-001 (シナリオ実行フロー), DD-STT-001 (Orchestrator 状態遷移), DD-SEQ-005 (バッチ実行フロー) | FN-002 対応 |
| REQ-F-003 | Canonical Data Layer | DD-CLS-004 (Topology), DD-CLS-005 (Asset), DD-CLS-006 (TimeSeries), DD-CLS-025 (Event), DD-CLS-026 (Metric), DD-CLS-027 (ExperimentMetadata), DD-DAT-002〜007 (CDL エンティティ定義), DD-SEQ-013 (CDL 変換フロー) | FN-004 対応 |
| REQ-F-004 | Benchmark Harness | DD-CLS-013 (BenchmarkHarness), DD-CLS-014 (MetricCalculator), DD-CLS-015 (ReportGenerator), DD-ALG-002 (メトリクス計算), DD-SEQ-004 (ベンチマーク実行フロー) | FN-005 対応 |
| REQ-F-005 | CLI + Notebook Bridge | DD-CLS-010 (CLIApp), DD-CLS-011 (CommandHandler), DD-CLS-012 (OutputFormatter), DD-SEQ-009〜011 (CLI 関連フロー) | FN-006, FN-007 対応 |
| REQ-F-006 | 段階的カスタムレイヤー | DD-CLS-016 (PluginRegistry), DD-CLS-017 (PluginDiscovery), DD-SEQ-014 (Plugin ロードフロー), DD-ALG-005 (Plugin 依存解決) | FN-009 対応 |
| REQ-F-007 | Connectors | DD-CLS-018 (ConnectorInterface), DD-CLS-019 (OpenDSSConnector), DD-CLS-020 (DataTranslator), DD-SEQ-012 (Connector 初期化・実行フロー), DD-STT-002 (Connector 状態遷移), DD-DAT-006 (データ変換マッピング) | FN-003 対応 |

### A.3 機能要求（P1: 実用性向上機能）

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

### A.4 機能要求（P2: 高度化機能）

| 要求 ID | 要求名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-F-017 | HIL 連携 | — | P2 スコープ（本版では対象外） |
| REQ-F-018 | Cyber Co-simulation | — | P2 スコープ（本版では対象外） |
| REQ-F-019 | 標準プロトコル対応 | — | P2 スコープ（本版では対象外） |
| REQ-F-020 | Standards Validation | — | P2 スコープ（本版では対象外） |
| REQ-F-021 | Operator HMI | — | P2 スコープ（本版では対象外） |

### A.5 品質要求

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

### A.6 制約

| 要求 ID | 制約名 | 対応 DD-xxx | 備考 |
|---|---|---|---|
| REQ-C-001 | Python 実装 | DD-MOD-001〜010 (全モジュール設計) | Python 3.11+ |
| REQ-C-002 | Docker 環境 | DD-BLD-001〜002 (Dockerfile, Docker Compose), DD-CFG-004 (Docker Compose 設定) | Docker Compose 標準デプロイ |
| REQ-C-003 | 1人 + AI 開発 | DD-MOD-001 (パッケージ構成), DD-CLS-全般 | アーキテクチャ複雑さの上限規定 |
| REQ-C-004 | マルチアーキテクチャ | DD-BLD-001 (Dockerfile マルチステージ), DD-TST-005 (クロスアーキテクチャテスト) | AMD64 + ARM64 |
| REQ-C-005 | OSS 公開 | DD-DAT-001 (Scenario Pack format), DD-DAT-002〜007 (CDL スキーマ), DD-CLS-018 (Connector SDK) | 公開フォーマット仕様 |
| REQ-C-006 | 英語標準 | DD-ERR-001〜002 (エラーメッセージ), DD-CLS-012 (OutputFormatter) | ドキュメント・メッセージ英語 |

---

## B. 用語集

| 用語 | 説明 |
|---|---|
| IPO | Input-Process-Output。メソッド定義の記述形式 |
| Protocol | typing.Protocol による構造的部分型（DIP 実現手法） |
| dataclass | Python dataclasses モジュールのイミュータブルデータ構造 |
| Clean Architecture | Uncle Bob 提唱の4層アーキテクチャ（Entities / UseCases / InterfaceAdapters / Frameworks） |
| Strategy パターン | アルゴリズムを交換可能にする GoF デザインパターン |
| Mermaid | Markdown ベースの図表記述言語 |
| structlog | Python 構造化ログライブラリ |
| JSON Lines | 1行1JSON オブジェクトのログ形式 |

---

## C. 参考文献

1. IPA「共通フレーム2013」
2. IPA「機能要件の合意形成ガイド」
3. Robert C. Martin "Clean Architecture"
4. Python PEP 8 Style Guide
5. Semantic Versioning 2.0.0 (semver.org)
6. Docker Compose Specification
7. pytest documentation
8. structlog documentation

---

## D. 更新ドキュメント一覧

| ファイル名 | 内容 | 作成日 | 最終更新日 |
|---|---|---|---|
| 01_requirements.md | 第1章 要件一覧 | 2026-04-03 | 2026-04-03 |
| 02_module_structure.md | 第2章 モジュール構成 | 2026-04-03 | 2026-04-03 |
| 03_class_design.md | 第3章 クラス設計 | 2026-04-03 | 2026-04-03 |
| 04_process_flow.md | 第4章 処理フロー設計 | 2026-04-03 | 2026-04-03 |
| 05_state_transition.md | 第5章 状態遷移設計 | 2026-04-03 | 2026-04-03 |
| 06_data_detail.md | 第6章 データ詳細設計 | 2026-04-03 | 2026-04-03 |
| 07_algorithm.md | 第7章 アルゴリズム設計 | 2026-04-03 | 2026-04-03 |
| 08_error_design.md | 第8章 エラー設計 | 2026-04-03 | 2026-04-03 |
| 09_config_management.md | 第9章 設定管理 | 2026-04-03 | 2026-04-03 |
| 10_test_detail.md | 第10章 テスト詳細設計 | 2026-04-03 | 2026-04-03 |
| 11_build_deploy.md | 第11章 ビルド・デプロイ | 2026-04-03 | 2026-04-03 |
| appendix.md | 付録 | 2026-04-03 | 2026-04-03 |
