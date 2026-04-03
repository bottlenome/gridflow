# 第8章 エラー設計

本章では、gridflow の例外クラス階層、エラーコード体系、およびエラーハンドリングの詳細設計を示す。基本設計書 第8章（信頼性設計）の方針を具体化し、レイヤー別の例外クラスとエラーコードを定義する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（8.1〜8.2） |

---

## 8.1 例外クラス階層設計

**関連要件**: REQ-Q-008 / DD-ERR-001

### 8.1.1 クラス階層図

すべての gridflow 例外は `GridflowError` 基底クラスを継承する。基本設計書 8.1 の 5 分類（CONF / CONN / EXEC / DATA / SYS）を Clean Architecture の 4 レイヤーに再編成し、各レイヤーに具体的な派生クラスを配置する。

```mermaid
classDiagram
    class GridflowError {
        +error_code: str
        +message: str
        +context: dict
        +cause: Exception | None
        +to_dict() dict
        +__str__() str
    }

    class DomainError {
        +error_code: str
        +message: str
        +context: dict
        +cause: Exception | None
    }

    class UseCaseError {
        +error_code: str
        +message: str
        +context: dict
        +cause: Exception | None
    }

    class AdapterError {
        +error_code: str
        +message: str
        +context: dict
        +cause: Exception | None
    }

    class InfraError {
        +error_code: str
        +message: str
        +context: dict
        +cause: Exception | None
    }

    %% Domain 層
    class ScenarioPackError {
        +pack_id: str
    }
    class CDLValidationError {
        +field_path: str
        +expected_type: str
    }
    class MetricCalculationError {
        +metric_name: str
        +step_name: str
    }

    %% UseCase 層
    class SimulationError {
        +experiment_id: str
        +step_name: str
    }
    class BenchmarkError {
        +experiment_ids: list~str~
        +metric_name: str
    }

    %% Adapter 層
    class ConnectorError {
        +connector_name: str
        +endpoint: str
    }
    class OpenDSSError {
        +dss_command: str
        +dss_error_text: str
    }
    class CLIError {
        +command: str
        +exit_code: int
    }
    class PluginError {
        +plugin_name: str
        +plugin_version: str
    }

    %% Infra 層
    class OrchestratorError {
        +workflow_id: str
        +step_index: int
    }
    class ContainerError {
        +container_id: str
        +image_ref: str
    }
    class RegistryError {
        +registry_url: str
        +resource_key: str
    }
    class ConfigError {
        +config_path: str
        +key: str
    }

    GridflowError <|-- DomainError
    GridflowError <|-- UseCaseError
    GridflowError <|-- AdapterError
    GridflowError <|-- InfraError

    DomainError <|-- ScenarioPackError
    DomainError <|-- CDLValidationError
    DomainError <|-- MetricCalculationError

    UseCaseError <|-- SimulationError
    UseCaseError <|-- BenchmarkError

    AdapterError <|-- ConnectorError
    AdapterError <|-- OpenDSSError
    AdapterError <|-- CLIError
    AdapterError <|-- PluginError

    InfraError <|-- OrchestratorError
    InfraError <|-- ContainerError
    InfraError <|-- RegistryError
    InfraError <|-- ConfigError
```

### 8.1.2 基底クラス属性定義

`GridflowError` およびすべての派生クラスは以下の共通属性を持つ。

| 属性 | 型 | 必須 | 説明 |
|---|---|---|---|
| `error_code` | `str` | Yes | エラーコード（E-xxxx 体系、8.2 節参照） |
| `message` | `str` | Yes | 人間可読なエラーメッセージ。テンプレートに `context` を埋め込んで生成する |
| `context` | `dict` | Yes | エラー発生時の文脈情報。キー・値はサブクラスごとに定義する。空辞書を許容する |
| `cause` | `Exception \| None` | No | 元例外への参照。例外チェーンにより根本原因のトレーサビリティを確保する |

### 8.1.3 基底クラスメソッド定義

| メソッド | 戻り値 | 説明 |
|---|---|---|
| `to_dict()` | `dict` | `error_code`, `message`, `context` を辞書化して返す。ログ出力・API レスポンスで使用する |
| `__str__()` | `str` | `[{error_code}] {message}` 形式の文字列を返す。CLI 出力で使用する |

### 8.1.4 レイヤー別中間クラス定義

| 中間クラス | レイヤー | 説明 |
|---|---|---|
| `DomainError` | Domain | ビジネスルール違反に起因するエラー。Scenario Pack 構造不正、CDL バリデーション失敗、メトリクス計算異常を包含する |
| `UseCaseError` | UseCase | アプリケーションロジックの実行失敗。シミュレーション実行エラー、ベンチマーク比較エラーを包含する |
| `AdapterError` | Adapter | 外部システムとの連携失敗。コネクタ接続エラー、OpenDSS 実行エラー、CLI パースエラー、プラグインエラーを包含する |
| `InfraError` | Infra | 基盤レイヤーの障害。オーケストレータエラー、コンテナエラー、レジストリエラー、設定読込エラーを包含する |

### 8.1.5 具象クラス定義

#### Domain 層

| クラス | 固有属性 | 説明 |
|---|---|---|
| `ScenarioPackError` | `pack_id: str` | Scenario Pack のスキーマ不正、ハッシュ不一致、バージョン非互換など |
| `CDLValidationError` | `field_path: str`, `expected_type: str` | CDL データモデルのバリデーション失敗。不正フィールド・型不一致を報告する |
| `MetricCalculationError` | `metric_name: str`, `step_name: str` | メトリクス計算中の異常。ゼロ除算、NaN 検出、値域超過など |

#### UseCase 層

| クラス | 固有属性 | 説明 |
|---|---|---|
| `SimulationError` | `experiment_id: str`, `step_name: str` | シミュレーション実行中の失敗。ステップ実行タイムアウト、依存ステップ未完了など |
| `BenchmarkError` | `experiment_ids: list[str]`, `metric_name: str` | ベンチマーク比較処理の失敗。比較対象不足、メトリクス欠損など |

#### Adapter 層

| クラス | 固有属性 | 説明 |
|---|---|---|
| `ConnectorError` | `connector_name: str`, `endpoint: str` | 外部シミュレータへの接続失敗。タイムアウト、認証エラー、プロトコル不一致など |
| `OpenDSSError` | `dss_command: str`, `dss_error_text: str` | OpenDSS 固有のエラー。DSS コマンド実行失敗、モデル収束不良など |
| `CLIError` | `command: str`, `exit_code: int` | CLI コマンドのパースエラー、不正な引数組み合わせ、権限不足など |
| `PluginError` | `plugin_name: str`, `plugin_version: str` | プラグインのロード失敗、インターフェース不一致、バージョン非互換など |

#### Infra 層

| クラス | 固有属性 | 説明 |
|---|---|---|
| `OrchestratorError` | `workflow_id: str`, `step_index: int` | ワークフロー実行制御の異常。DAG 構築失敗、ステップスケジューリングエラーなど |
| `ContainerError` | `container_id: str`, `image_ref: str` | Docker コンテナの起動失敗、イメージ取得エラー、リソース制限超過など |
| `RegistryError` | `registry_url: str`, `resource_key: str` | Scenario Pack レジストリへのアクセス失敗。認証エラー、リソース未発見など |
| `ConfigError` | `config_path: str`, `key: str` | 設定ファイルの読込失敗、必須キー欠損、値の型不正、環境変数未定義など |

### 8.1.6 例外チェーンポリシー

- レイヤー境界を跨ぐ際は、下位レイヤーの例外を `cause` に格納し、上位レイヤーの例外でラップする
- 例: OpenDSS の `RuntimeError` → `OpenDSSError(cause=e)` → `SimulationError(cause=opendss_err)`
- `cause` チェーンは `to_dict()` で再帰的に展開し、ログへ全階層を記録する

---

## 8.2 エラーコード一覧（E-xxxx 体系）

**関連要件**: REQ-Q-008 / DD-ERR-002

### 8.2.1 コード体系

エラーコードは `E-{レイヤー2桁}{連番3桁}` の形式で付番する。

| レイヤー接頭辞 | レイヤー | 範囲 |
|---|---|---|
| `E-10` | Domain 層 | E-10001 〜 E-10999 |
| `E-20` | UseCase 層 | E-20001 〜 E-20999 |
| `E-30` | Adapter 層 | E-30001 〜 E-30999 |
| `E-40` | Infrastructure 層 | E-40001 〜 E-40999 |

### 8.2.2 重大度定義

| 重大度 | ラベル | 説明 |
|---|---|---|
| CRITICAL | 致命的 | システム全体の継続実行が不可能。即時停止が必要 |
| ERROR | 重大 | 当該処理は失敗するが、他の処理への影響は限定的 |
| WARNING | 警告 | 処理は継続可能だが、結果の正確性に影響する可能性がある |

### 8.2.3 エラーコード一覧

#### Domain 層（E-10xxx）

| コード | 例外クラス | メッセージテンプレート | 重大度 | 対処方針 |
|---|---|---|---|---|
| E-10001 | ScenarioPackError | Scenario Pack '{pack_id}' のスキーマが不正です | ERROR | pack.yaml のスキーマバージョンを確認し、必要に応じて `gridflow migrate` を実行する |
| E-10002 | ScenarioPackError | Scenario Pack '{pack_id}' のハッシュが一致しません（期待: {expected}, 実際: {actual}） | ERROR | Scenario Pack ファイルが改変されていないか確認する。再ダウンロードまたは再作成を行う |
| E-10003 | ScenarioPackError | Scenario Pack '{pack_id}' のバージョン '{version}' は非対応です | ERROR | `gridflow migrate` でスキーマを最新バージョンへ移行する |
| E-10004 | ScenarioPackError | Scenario Pack '{pack_id}' に必須フィールド '{field}' が存在しません | ERROR | pack.yaml に必須フィールドを追加する。スキーマ定義を参照のこと |
| E-10005 | CDLValidationError | CDL フィールド '{field_path}' の型が不正です（期待: {expected_type}, 実際: {actual_type}） | ERROR | 入力データの型を修正する。CDL スキーマ定義を参照のこと |
| E-10006 | CDLValidationError | CDL フィールド '{field_path}' の値が許容範囲外です（値: {value}, 範囲: {range}） | ERROR | 入力値を許容範囲内に修正する |
| E-10007 | CDLValidationError | CDL トポロジの接続グラフに孤立ノードが検出されました（ノード: {node_ids}） | WARNING | トポロジ定義を確認し、孤立ノードを接続するか削除する |
| E-10008 | CDLValidationError | CDL 時系列データの時刻インデックスに重複があります（フィールド: {field_path}） | ERROR | 入力時系列データの重複タイムスタンプを除去する |
| E-10009 | MetricCalculationError | メトリクス '{metric_name}' の計算でゼロ除算が発生しました（ステップ: {step_name}） | ERROR | 入力データを確認し、分母がゼロにならない条件を検証する |
| E-10010 | MetricCalculationError | メトリクス '{metric_name}' の計算結果が NaN です（ステップ: {step_name}） | ERROR | 入力データに欠損値・無効値がないか確認する |
| E-10011 | MetricCalculationError | メトリクス '{metric_name}' の計算結果が閾値を超過しました（値: {value}, 閾値: {threshold}） | WARNING | 入力データおよびシミュレーション設定を見直す |

#### UseCase 層（E-20xxx）

| コード | 例外クラス | メッセージテンプレート | 重大度 | 対処方針 |
|---|---|---|---|---|
| E-20001 | SimulationError | シミュレーション '{experiment_id}' のステップ '{step_name}' がタイムアウトしました | ERROR | タイムアウト値を延長するか、シミュレーション規模を縮小する |
| E-20002 | SimulationError | シミュレーション '{experiment_id}' の依存ステップ '{step_name}' が未完了です | ERROR | 依存ステップを先に実行するか、`--from-step` で再開する |
| E-20003 | SimulationError | シミュレーション '{experiment_id}' のステップ '{step_name}' で予期しないエラーが発生しました | CRITICAL | ログを確認し、`cause` チェーンから根本原因を特定する |
| E-20004 | SimulationError | シミュレーション '{experiment_id}' の seed が未指定です。自動生成された seed: {seed} | WARNING | 再現性が必要な場合は Scenario Pack に seed を明示指定する |
| E-20005 | BenchmarkError | ベンチマーク比較に必要な実験数が不足しています（必要: {required}, 現在: {actual}） | ERROR | 比較対象の実験を追加実行する |
| E-20006 | BenchmarkError | ベンチマーク比較でメトリクス '{metric_name}' が実験 '{experiment_id}' に存在しません | ERROR | 対象実験で当該メトリクスが算出されているか確認する |
| E-20007 | BenchmarkError | ベンチマーク比較で実験間のスキーマバージョンが一致しません | ERROR | 同一スキーマバージョンの実験同士で比較する |
| E-20008 | SimulationError | シミュレーション '{experiment_id}' の中間結果の復元に失敗しました | ERROR | 中間ファイルの破損を確認し、最初のステップから再実行する |

#### Adapter 層（E-30xxx）

| コード | 例外クラス | メッセージテンプレート | 重大度 | 対処方針 |
|---|---|---|---|---|
| E-30001 | ConnectorError | コネクタ '{connector_name}' がエンドポイント '{endpoint}' への接続に失敗しました | ERROR | ネットワーク接続およびエンドポイントの稼働状態を確認する |
| E-30002 | ConnectorError | コネクタ '{connector_name}' の認証に失敗しました（エンドポイント: {endpoint}） | ERROR | 認証情報（API キー・トークン）を確認・更新する |
| E-30003 | ConnectorError | コネクタ '{connector_name}' のレスポンスが不正です（ステータス: {status_code}） | ERROR | コネクタのバージョン互換性を確認する。サーバー側ログも参照する |
| E-30004 | OpenDSSError | OpenDSS コマンド '{dss_command}' の実行に失敗しました: {dss_error_text} | ERROR | DSS コマンドの構文および入力モデルを確認する |
| E-30005 | OpenDSSError | OpenDSS の潮流計算が収束しませんでした（コマンド: {dss_command}） | ERROR | ネットワークモデルのパラメータを見直す。収束条件の緩和を検討する |
| E-30006 | OpenDSSError | OpenDSS のバージョンが非対応です（検出: {detected}, 要求: {required}） | ERROR | 対応バージョンの OpenDSS をインストールする |
| E-30007 | CLIError | CLI コマンド '{command}' の引数が不正です | ERROR | `gridflow {command} --help` でヘルプを参照する |
| E-30008 | CLIError | CLI コマンド '{command}' の実行に権限が不足しています | ERROR | 適切な権限でコマンドを再実行する |
| E-30009 | PluginError | プラグイン '{plugin_name}' のロードに失敗しました | ERROR | プラグインのインストール状態とバージョン互換性を確認する |
| E-30010 | PluginError | プラグイン '{plugin_name}' ({plugin_version}) のインターフェースが不一致です | ERROR | プラグインを対応バージョンに更新する |

#### Infrastructure 層（E-40xxx）

| コード | 例外クラス | メッセージテンプレート | 重大度 | 対処方針 |
|---|---|---|---|---|
| E-40001 | OrchestratorError | ワークフロー '{workflow_id}' の DAG 構築に失敗しました（循環依存を検出） | CRITICAL | ワークフロー定義のステップ依存関係を見直し、循環を解消する |
| E-40002 | OrchestratorError | ワークフロー '{workflow_id}' のステップ {step_index} のスケジューリングに失敗しました | ERROR | リソース制約およびステップ定義を確認する |
| E-40003 | ContainerError | Docker コンテナの起動に失敗しました（イメージ: {image_ref}） | CRITICAL | Docker デーモンの稼働状態とイメージの存在を確認する |
| E-40004 | ContainerError | Docker イメージ '{image_ref}' の取得に失敗しました | ERROR | レジストリへの接続およびイメージ名・タグを確認する |
| E-40005 | ContainerError | コンテナ '{container_id}' がリソース制限を超過しました（メモリ上限超過） | ERROR | コンテナのリソース制限値を引き上げるか、処理規模を縮小する |
| E-40006 | RegistryError | Scenario Pack レジストリ '{registry_url}' への接続に失敗しました | ERROR | レジストリの URL およびネットワーク接続を確認する |
| E-40007 | RegistryError | リソース '{resource_key}' がレジストリ '{registry_url}' に見つかりません | ERROR | リソースキーの綴りおよびレジストリの内容を確認する |
| E-40008 | ConfigError | 設定ファイル '{config_path}' の読込に失敗しました | CRITICAL | ファイルの存在およびアクセス権限を確認する |
| E-40009 | ConfigError | 設定ファイル '{config_path}' の必須キー '{key}' が未定義です | ERROR | 設定ファイルに必須キーを追加する。設定スキーマを参照のこと |
| E-40010 | ConfigError | 設定ファイル '{config_path}' のキー '{key}' の値が不正です（期待型: {expected_type}） | ERROR | 設定値を正しい型に修正する |
| E-40011 | ConfigError | 環境変数 '{env_var}' が未定義です | ERROR | 必要な環境変数を設定する。`.env.example` を参照のこと |

### 8.2.4 基本設計エラーコードとの対応

基本設計書 8.1 節のエラーコード体系（CONF / CONN / EXEC / DATA / SYS）と詳細設計の E-xxxx 体系の対応を以下に示す。

| 基本設計コード | 基本設計分類 | 詳細設計コード範囲 | 対応例外クラス群 |
|---|---|---|---|
| CONF-xxx | 設定エラー | E-10001〜E-10004, E-40008〜E-40011 | ScenarioPackError, ConfigError |
| CONN-xxx | コネクタエラー | E-30001〜E-30006 | ConnectorError, OpenDSSError |
| EXEC-xxx | 実行エラー | E-20001〜E-20008, E-40001〜E-40002 | SimulationError, BenchmarkError, OrchestratorError |
| DATA-xxx | データエラー | E-10005〜E-10011 | CDLValidationError, MetricCalculationError |
| SYS-xxx | システムエラー | E-40003〜E-40007 | ContainerError, RegistryError |
