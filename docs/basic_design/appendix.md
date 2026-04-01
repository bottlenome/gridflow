# 付録

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |

---

## A. 用語集

本用語集は基本設計書内で使用される主要な用語を定義する。アーキテクチャドキュメントの付録（`docs/architecture/08_appendix.md`）も参照のこと。

| 用語 | 定義 |
|---|---|
| **Scenario Pack** | 実験 1 件を構成する全データ（ネットワーク定義、時系列データ、シミュレータ設定、評価指標、seed、expected outputs、可視化テンプレート）をパッケージ化したもの。再現性の単位。（REQ-F-001） |
| **Orchestrator** | Docker ベースの統合実行ランタイム。Scenario Pack を受け取り、Connector 群を制御して実験を実行する。実行順序管理、コンテナ起動・管理、時間同期、バッチ実行を担う。（REQ-F-002） |
| **Connector** | 外部シミュレーションツール（OpenDSS、pandapower、HELICS 等）との統一インターフェース。各ツール固有のプロトコルを CDL との変換で吸収する。（REQ-F-007） |
| **CDL (Canonical Data Layer)** | ツール固有フォーマットを共通表現（topology, asset, timeseries, event, metric, experiment metadata）に変換する正規化データ層。（REQ-F-003） |
| **Benchmark Harness** | 電圧逸脱率、thermal overload 時間、ENS 等の標準メトリクスで実験結果を定量的に採点・比較するフレームワーク。（REQ-F-004） |
| **Registry** | Scenario Pack の登録・検索・バージョン管理を行うコンポーネント。（REQ-F-001） |
| **Migrator** | バージョンアップ時のスキーマ移行を管理するコンポーネント。バックアップ・移行・検証・ロールバックを一括処理する。（REQ-Q-007） |
| **Plugin API** | 段階的カスタマイズレベル（L1-L4）に応じた拡張インターフェース。YAML 設定変更から Python Protocol 実装、ソースフォークまでを統一的に提供する。（REQ-F-006） |
| **ACDM** | Architecture Centric Design Method。アーキテクチャ上重要な要求（ASR）を起点に設計判断を行う手法。 |
| **DDD** | Domain-Driven Design。ドメインモデルを中心にソフトウェアを設計する手法。Ubiquitous Language やバウンデッドコンテキスト等の概念を含む。 |
| **TDD** | Test-Driven Development。テストを先に書き、実装・リファクタリングのサイクルで開発を進める手法。 |
| **Ubiquitous Language** | DDD におけるドメインエキスパートと開発者が共有する統一用語体系。本プロジェクトでは用語集の用語がこれに該当する。 |

### Clean Architecture レイヤー

| レイヤー | 役割 | 主要コンポーネント |
|---|---|---|
| **Entities** | ドメインモデル・ビジネスルール | Scenario Pack 定義、CDL スキーマ、Metric 定義 |
| **UseCases** | アプリケーション固有のビジネスロジック | RunSimulation, CompareBenchmark, ImportScenario |
| **Interface Adapters** | 外部とのインターフェース変換 | CLI コマンド、Connector インターフェース、Registry API |
| **Frameworks & Drivers** | 外部フレームワーク・ツール | Docker, OpenDSS, pandapower, ファイルシステム |

### カスタマイズレベル (L1-L4)

| レベル | 名称 | 対象ユーザ | 必要スキル | 変更範囲 |
|---|---|---|---|---|
| **L1** | 設定変更 | 全研究者 | YAML/TOML 編集 | パラメータ値の変更 |
| **L2** | プラグイン開発 | 中級研究者 | Python 基礎 | カスタム Connector / Metric の追加 |
| **L3** | パイプライン構成 | 上級研究者 | Python + Docker | ワークフローの再構成 |
| **L4** | ソース改変 | 開発者 | フルスタック | コア機能の変更（フォーク） |

---

## B. 参考文献

| # | 文献名 | 種別 | 備考 |
|---|---|---|---|
| 1 | IPA「機能要件の合意形成ガイド」 | ガイドライン | 基本設計書の構成に準拠 |
| 2 | IPA「非機能要求グレード」 | ガイドライン | 品質要求の分類・定義に参照 |
| 3 | Architecture Decision Making for Large-Scale Software Systems (ACDM) | 手法 | アーキテクチャ意思決定プロセスに参照 |
| 4 | gridflow アーキテクチャドキュメント (`docs/architecture/`) | プロジェクト文書 | 要求定義・システム構成の原典 |
| 5 | gridflow 計画書 (`docs/basic_design_plan.md`) | プロジェクト文書 | 基本設計の計画・スコープ定義 |
| 6 | Semantic Versioning 2.0.0 (semver.org) | 規格 | バージョニング規則 |
| 7 | The Clean Architecture (Robert C. Martin) | アーキテクチャパターン | レイヤー構成の設計指針 |
| 8 | Docker Compose Specification | 規格 | デプロイメント構成の基盤 |

---

## C. 更新ドキュメント一覧

本基本設計プロジェクトで作成・更新された全ドキュメントの一覧。

| 日付 | ファイルパス | 変更内容 |
|---|---|---|
| 2026-04-01 | `docs/architecture/README.md` | 更新履歴セクション追加 |
| 2026-04-01 | `docs/basic_design_plan.md` | 基本設計計画書 初版作成 |
| 2026-04-01 | `docs/basic_design/README.md` | 基本設計書 README 初版作成 |
| 2026-04-01 | `docs/basic_design/01_requirements.md` | 第1章 要求一覧 初版作成 |
| 2026-04-01 | `docs/basic_design/02_system_architecture.md` | 第2章 システム方式設計 初版作成 |
| 2026-04-01 | `docs/basic_design/03_function_design.md` | 第3章 機能設計 初版作成 |
| 2026-04-01 | `docs/basic_design/05_data_design.md` | 第5章 データ設計 初版作成 |
| 2026-04-01 | `docs/basic_design/06_external_interface.md` | 第6章 外部インターフェース設計 初版作成 |
| 2026-04-01 | `docs/basic_design/07_performance.md` | 第7章 性能設計 初版作成 |
| 2026-04-01 | `docs/basic_design/08_reliability.md` | 第8章 信頼性設計 初版作成 |
| 2026-04-01 | `docs/basic_design/09_security.md` | 第9章 セキュリティ設計 初版作成 |
| 2026-04-01 | `docs/basic_design/10_deployment.md` | 第10章 移行・導入設計 初版作成 |
| 2026-04-01 | `docs/basic_design/11_test_policy.md` | 第11章 テスト方針 初版作成 |
| 2026-04-01 | `docs/basic_design/12_operation.md` | 第12章 運用・保守設計 初版作成 |
| 2026-04-01 | `docs/basic_design/appendix.md` | 付録 初版作成 |
