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

### 最重要課題（未対応）

#### 課題1: 第3章のクラス定義不足（X2: ch03↔ch04）
第4章のシーケンス図に登場するが第3章に未定義のクラス:
CDLRepository, DataTranslator, CanonicalData, PluginDiscovery,
DebugManager, HealthChecker, InitHandler, UpdateHandler,
MigrationRunner, KPIAggregator, ConfigValidator, Formatter

**対応方針**: 第3章に不足クラスを追加。ただし全てが独立クラスである必要はなく、
既存クラスのメソッドとして統合できるものは統合する。
- CDLRepository → 3.4節に追加（UseCase層Protocol）
- DataTranslator → 3.5節で定義済み（WI-01に含まれている）
- PluginDiscovery → 3.8節で定義済み（WI-01に含まれている）
- DebugManager/HealthChecker/InitHandler/UpdateHandler/MigrationRunner/KPIAggregator
  → CLIのサブコマンドハンドラーとして3.7節に統合
- ConfigValidator → 3.9節 ConfigManager.validate() として統合
- Formatter → 3.7節 OutputFormatter として既に定義済み

#### 課題2: 例外名の体系的不一致（X4: ch03↔ch08）
第3章: 操作固有名（PackNotFoundError, ContainerStartError, ExecutionError等）
第8章: カテゴリベース名（RegistryError, ContainerError, OrchestratorError等）

**対応方針**: 第8章のカテゴリベース例外を親クラスとし、第3章の操作固有例外を
サブクラスとして第8章に追加する。
例: RegistryError → PackNotFoundError(RegistryError)
    ContainerError → ContainerStartError(ContainerError)

#### 課題3: 状態属性の欠落（X3: ch03↔ch05）
第5章で状態遷移が定義されているが、第3章のクラスに状態属性がない。

**対応方針**: 第3章の以下クラスにstate属性を追加:
- Orchestrator: state: OrchestratorState (Enum)
- ScenarioPack: status: PackStatus (Enum)
- ConnectorInterface: （Protocolなので状態はConnector実装側で管理）

## R2: 相互整合性レビュー（X5〜X7）
- 未実施
