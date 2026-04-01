# 5. ビュー間の対応の説明

本セクションは、静的ビュー（セクション 3）と動的ビュー（セクション 4）の要素を横断的に対応づけ、アーキテクチャドライバー（セクション 2）へのトレーサビリティを確保する。

---

## 5.1 静的ビューと動的ビューの要素対応表

### コンポーネント ↔ ユースケース ↔ シーケンス図の参加者

| 静的ビューのコンポーネント (3.2) | Clean Architecture 層 | 関与する UC | シーケンス図での参加者名 |
|---|---|---|---|
| **Orchestrator** | Use Cases | UC-01, UC-04, UC-06, UC-07 | Orchestrator / Orch |
| **ScenarioRegistry** | Use Cases | UC-01, UC-02, UC-07, UC-08 | Registry / Scenario Registry |
| **BenchmarkHarness** | Use Cases | UC-03 | Harness / Benchmark Harness |
| **Observability** | Use Cases | UC-01, UC-05, UC-06 | Logger / Observability |
| **Bootstrap** | Use Cases | UC-04, UC-07, UC-08 | Core / gridflow コア |
| **ConnectorInterface** | Interface Adapters | UC-01, UC-02(validate), UC-04, UC-07 | Connector / Connector I/F |
| **CLIApp** | Interface Adapters | UC-01〜UC-10 | CLI |
| **NotebookBridge** | Interface Adapters | UC-09 | （4.3.9 注記で言及） |
| **DataExport** | Interface Adapters | UC-03, UC-09 | Export / Data Export |
| **CanonicalDataLayer** | Entities (I/F) + Adapters (実装) | UC-01, UC-03, UC-06, UC-08, UC-09 | CDL |
| **ScenarioPack** | Entities | UC-01, UC-02, UC-03 | （データとして流通） |
| **MetricCalculator** | Use Cases (I/F) | UC-03 | Calculator / MetricCalculator |
| **PluginRegistry** | Use Cases | UC-01(L2 Plugin 呼出し) | （ExecutionContext 経由） |

### Connector 実装 ↔ 外部システム

| Connector 実装 (3.2.2) | 時間管理パターン (3.1.3) | シーケンス図での表現 |
|---|---|---|
| OpenDSSConnector | Orchestrator 駆動型 | ExtSys（4.3.1 の汎用表現） |
| HELICSConnector | フェデレーション駆動型 | 同上 |
| Grid2OpConnector | 環境駆動型 | 同上 |
| MockConnector | テスト用 | （テスト時にのみ使用） |

> **設計判断:** シーケンス図では個別の Connector 実装を描かず「Connector I/F」と「外部システム」の 2 参加者で抽象化している。これは AS-4（シミュレータと実系統の非区別）を図レベルで表現するためである。

---

## 5.2 ユースケースとコンポーネントのトレーサビリティ

各 UC が触れるコンポーネントを一覧化し、変更影響範囲の分析に使う。

| UC | Orchestrator | Registry | Harness | Observability | Bootstrap | Connector | CLI | CDL | Export | Plugin |
|---|---|---|---|---|---|---|---|---|---|---|
| UC-01 実験実行 | ● | ● | | ● | | ● | ● | ● | | ● |
| UC-02 Scenario Pack 管理 | | ● | | | | ○ | ● | | | |
| UC-03 ベンチマーク評価 | | | ● | | | | ● | ● | ● | ○ |
| UC-04 起動・終了 | ● | ● | | ● | ● | ● | ● | | | |
| UC-05 ログ・トレース | | | | ● | | | ● | | | |
| UC-06 デバッグ | ● | | | ● | | | ● | ● | | |
| UC-07 インストール | | ● | | | ● | ● | ● | | | |
| UC-08 アップデート | | ● | | | ● | | ● | ● | | |
| UC-09 結果参照 | | | | | | | ● | ● | ● | |
| UC-10 LLM 実験指示 | ○ | ○ | ○ | ○ | | ○ | ● | ○ | ○ | |

● = 直接関与、○ = 間接関与（UC-10 は委譲、UC-02 は validate 時のみ等）

> **分析:** CLI は全 UC に関与する唯一のコンポーネント（FR-05: CLI ファースト）。Orchestrator と CDL が次に多く、E2E 研究ループの「実行」と「結果」の中心であることを反映している。

---

## 5.3 アーキテクチャドライバーとビュー要素の対応

各ドライバー（FR/QA/CON/AC/AS）がどのビュー要素で実現されているかを追跡する。

### FR → コンポーネント → UC

| FR | 実現するコンポーネント | 関与する UC |
|---|---|---|
| FR-01 Scenario Pack + Registry | ScenarioPack (Entities), ScenarioRegistry (Use Cases) | UC-01, UC-02, UC-03, UC-07, UC-08 |
| FR-02 Orchestrator | Orchestrator (Use Cases), Scheduler | UC-01, UC-04, UC-06 |
| FR-03 CDL | CanonicalDataLayer (Entities + Adapters), DataExport | UC-01, UC-02, UC-03, UC-05, UC-06, UC-09 |
| FR-04 Benchmark Harness | BenchmarkHarness, MetricCalculator | UC-03 |
| FR-05 CLI + Notebook | CLIApp, NotebookBridge | UC-01〜UC-10 |
| FR-06 カスタムレイヤー | PluginRegistry, MetricCalculator | UC-01, UC-02, UC-03 |
| FR-07 Connectors | ConnectorInterface, 各 Connector 実装 | UC-01, UC-02, UC-04, UC-07 |

### QA → 実現戦術 → メカニズム

| QA | 戦術 (2.4.2) | 実現メカニズム (03b) | 検証方法 |
|---|---|---|---|
| QA-1 導入容易性 | ワンコマンドセットアップ | M-8（設定管理: 起動時バリデーション） | UC-07 の所要時間計測 |
| QA-2 初回利用効率 | サンプル Pack 事前登録 | M-8（設定管理）, M-7（バージョン管理） | UC-07 → UC-01 の TTFS 計測 |
| QA-3 再現性 | Seed 管理 + 環境固定 | M-7（バージョン管理: スキーマバージョン）, M-9（シリアライゼーション） | 再現性テスト（M-5） |
| QA-4 拡張性 | Interface Segregation + DI | M-10（DI: コンストラクタ注入）, 3.5（Plugin API） | L2 Plugin の統合テスト |
| QA-5 ワークフロー効率 | バッチ実行 + パイプライン | Orchestrator + Scheduler | UC-01 → UC-03 のサイクルタイム |
| QA-6 データエクスポート容易性 | 標準フォーマット出力 | M-9（シリアライゼーション: CSV/JSON/Parquet） | UC-09 のステップ数計測 |
| QA-7 ポータビリティ | コンテナ抽象化 | M-3（OS 抽象化: Docker 前提）, M-6（CI/CD: マルチアーキ） | CI での AMD64 + ARM64 テスト |
| QA-8 可観測性 | 構造化ログ + メトリクス | M-1（ログ: StructuredLogger）, M-2（エラー設計） | UC-05 で KPI 取得確認 |
| QA-9 LLM 親和性 | 構造化 I/O + Ubiquitous Language | M-1（ログ: JSON）, M-2（エラー: resolution 必須）, M-12（i18n） | UC-10 で LLM が操作可能か検証 |
| QA-10 性能効率 | ストリーミング + 非同期 I/O | 3.4（プロセスビュー: CDL I/O スレッド, Logger スレッド） | 性能テスト（M-5） |

### AS → 静的ビューでの具体化

| AS | 静的ビューでの表現 |
|---|---|
| AS-1 DDD | 3.2.3 ドメインモデル（Ubiquitous Language）、3.1.4 Bounded Context 対応表 |
| AS-2 Clean Architecture | 3.1.4 の 4 層構造、3.2.1 のインターフェース境界 ①②③ |
| AS-3 TDD | 3.2.2 MockConnector、M-5 テスト構成、M-10 DI（テスト容易性） |
| AS-4 Simulation-Real Equivalence | 3.1.3 外部システム分析、3.2.2 Connector 実装分類（同一 I/F） |
