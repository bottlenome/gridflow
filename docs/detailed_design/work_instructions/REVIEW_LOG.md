# レビューログ

## R1: 単章レビュー（第1回）
- 対象: ch02, ch03(前半), ch05
- 結果: ERROR 1件（Mermaid構文）, WARN 13件
- 対応: Mermaid構文修正済み、cancelイベント遷移追加済み

## R1: 単章レビュー（第2回）
- 対象: ch04, ch06, ch07, ch10, ch11, 付録
- 結果: ERROR 2件（REQ-UC-xxx, REQ-010）, WARN 9件
- 対応: 要件ID修正済み

## R2: 相互整合性レビュー（X1〜X4）
- 対象: ch03 vs ch04/ch05/ch08/ch10

### 課題1: 第3章のクラス定義不足（X2: ch03↔ch04）
第4章のシーケンス図に登場するが第3章に未定義のクラス:
CDLRepository, DataTranslator, CanonicalData, PluginDiscovery,
DebugManager, HealthChecker, InitHandler, UpdateHandler,
MigrationRunner, KPIAggregator, ConfigValidator, Formatter

**対応状況**: ✅ **対応済み（2026-04-06, DD-REV-101）**
- CDLRepository → 3.4.12節に Protocol 追加
- CanonicalData → 3.4.11節に Union 型定義追加
- DataTranslator → 3.5.4節で定義済み（対応不要）
- PluginDiscovery → 3.8.4節で定義済み（対応不要）
- DebugManager/InitHandler/UpdateHandler/KPIAggregator → 3.7.8節に CLIサブコマンドハンドラーとして統合追加
- HealthChecker → 3.9.6節に共通基盤クラスとして追加
- MigrationRunner → 3.9.7節に共通基盤クラスとして追加
- ConfigValidator → ConfigManager.validate() として統合済み（対応不要）
- Formatter → OutputFormatter として定義済み（対応不要）

### 課題2: 例外名の体系的不一致（X4: ch03↔ch08）
第3章: 操作固有名（PackNotFoundError, ContainerStartError, ExecutionError等）
第8章: カテゴリベース名（RegistryError, ContainerError, OrchestratorError等）

**対応状況**: ✅ **対応済み（2026-04-06, DD-REV-102）**
- 第3章 3.9.5節: 例外クラス階層を4層構造（DomainError/UseCaseError/AdapterError/InfraError）に再構成、全サブクラスを明記
- 第8章 8.1.5節: 具象クラス定義にサブクラス列を追加、エラーコードとの対応を明記

### 課題3: 状態属性の欠落（X3: ch03↔ch05）
第5章で状態遷移が定義されているが、第3章のクラスに状態属性がない。

**対応状況**: ✅ **対応済み（2026-04-06, DD-REV-103）**
- Orchestrator: state: OrchestratorState 追加
- ScenarioPack: status: PackStatus 追加
- ConnectorInterface: Protocolなので対応不要

## R2: 相互整合性レビュー（X5〜X7）
- 実施日: 2026-04-06

### X5: ch06（データ詳細設計）↔ ch03（クラス設計）

**結果**: ERROR 10件, WARNING 7件

**ERROR（修正必須）:**
1. CDLエンティティのID属性命名が不統一（第6章: `id`, 第3章: `{entity}_id`）— Topology, Node, Edge, Asset, TimeSeries, Event の6エンティティ
2. Metric 属性体系の不整合（第6章: `name` をPK、第3章: `metric_id` と `name` を分離）
3. ScenarioPack 属性定義の乖離（第6章: ER図に基本属性のみ、第3章: 詳細クラス定義）
4. PackMetadata の第6章での定義欠落
5. Event.target_id の参照対象の矛盾（第6章: Node/Edge、第3章: Asset）

**WARNING（改善推奨）:**
1. コンテナ型の不一致（tuple vs list）
2. 相互に属性欠落あり（name, source_bus, node_type, length_km, resolution_s 等）
3. ExperimentMetadata.seed 型の相違（int vs int|None）
4. Asset.node_id vs Asset.bus の属性名相違

### X6: ch07（アルゴリズム設計）↔ ch03（クラス設計）

**結果**: ERROR 8件, WARNING 4件

**ERROR（修正必須）:**
1. HELICSBroker クラスが第3章に未定義（Federation-driven 時間同期で必要）
2. SimulationResults クラスが未定義（メトリクス計算入力型）
3. Result 型群が未定義（NodeResult, BranchResult, LoadResult, GeneratorResult, RenewableResult）
4. Interruption クラスが第3章に未定義（IEEE 1366 指標計算で必要）
5. SimulationTask / TaskResult が未定義（バッチスケジューリングで必要）
6. ExperimentResult が第3章に未定義（Orchestrator.run() 戻り値、MetricCalculator 入力型）
7. TimeSyncStrategy 関連クラス（OrchestratorDriven/FederationDriven/HybridSync）が第3章に未定義
8. ConnectorInterface に execute_at メソッドが未定義（HELICS 連携時の時刻ベース実行）

**WARNING（改善推奨）:**
1. Connector クラス名の不統一（"Connector" vs "ConnectorInterface"）
2. メトリクス計算入力型の用語不統一（SimulationResults vs ExperimentResult）
3. 標準指標計算器の実装戦略が不明（クラス定義なし、表のみ）
4. execute_at の仕様明確化

### X7: ch09（設定管理設計）↔ ch11（ビルド・デプロイ設計）

**結果**: ERROR 0件, WARNING 4件

**WARNING（改善推奨）:**
1. ボリュームマウントパスの不整合（`/data` vs `/app/data`, `/scenario-packs` vs `/app/scenarios`）
2. CI 環境用 docker-compose.test.yml の設定仕様が第9章に未記載
3. Dockerfile 内のデフォルト値が ENV 指定されていない
4. パッケージバージョン指定と設定項目の関連が未記載

### X5〜X7 総合
- X5: ERROR 10件 — CDLエンティティの属性定義統一が最優先課題
- X6: ERROR 8件 — アルゴリズムで必要なクラスの第3章への追加が必要
- X7: ERROR 0件 — 基本的に整合。ボリュームパスの統一が推奨

## X5/X6 対応（2026-04-06）

### X5対応（DD-REV-201〜DD-REV-207）

| ID | 対応内容 | 対象ファイル |
|---|---|---|
| DD-REV-201 | ID命名統一: ch06の `id` → `{entity}_id`（topology_id, node_id, edge_id, asset_id, series_id, event_id） | 06_data_detail.md |
| DD-REV-202 | Event.target拡張: `target_asset` → `target_id` + `target_type`（node/edge/asset の3種参照に対応） | 03a_domain_classes.md, 06_data_detail.md |
| DD-REV-203 | Metric PK統一: `metric_id` 削除、`name` をPKに統一 | 03a_domain_classes.md |
| DD-REV-204 | ScenarioPack/PackMetadata: ch06のER図・属性表にPackMetadata追加、全属性を第3章と整合 | 06_data_detail.md |
| DD-REV-205 | Asset.bus → node_id: 第3章を `node_id` に統一（第6章と整合） | 03a_domain_classes.md |
| DD-REV-206 | 属性欠落補完: ch06に name, source_bus, node_type, length_km, resolution_s, rated_power_kw 追加 | 06_data_detail.md |
| DD-REV-207 | seed型統一: `int` → `int \| None`（デフォルト None）、tuple vs list 注記追加 | 06_data_detail.md, 03a_domain_classes.md |

### X6対応（DD-REV-301〜DD-REV-308）

| ID | 対応内容 | 対象ファイル |
|---|---|---|
| DD-REV-301 | ExperimentResult 正式定義追加（03a 3.4.13）、ch07 SimulationResults との対応注記 | 03a_domain_classes.md, 07_algorithm.md |
| DD-REV-302 | Result型群追加（NodeResult, BranchResult, LoadResult, GeneratorResult, RenewableResult）→ 03a 3.4.14〜3.4.18 | 03a_domain_classes.md |
| DD-REV-303 | Interruption dataclass追加（03a 3.4.19）— IEEE 1366 指標計算用 | 03a_domain_classes.md |
| DD-REV-304 | TimeSyncStrategy Protocol + 3実装（OrchestratorDriven/FederationDriven/HybridSync）追加 → 03b 3.3.6 | 03b_usecase_classes.md |
| DD-REV-305 | HELICSBroker 追加 → 03d 3.9.8 | 03d_infra_classes.md |
| DD-REV-306 | FederatedConnectorInterface Protocol 追加（execute_at メソッド）→ 03b 3.5.2a | 03b_usecase_classes.md |
| DD-REV-307 | SimulationTask / TaskResult 追加 → 03b 3.3.7 | 03b_usecase_classes.md |
| DD-REV-308 | ch07 BenchmarkCalculator/SimulationResults に第3章との対応注記追加 | 07_algorithm.md |

**クラス一覧更新**: DD-CLS-033〜DD-CLS-047（15クラス追加、全47クラス）
