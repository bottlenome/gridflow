# 実装メカニズム詳細

本ドキュメントはセクション 2.4.4 の補足として、各品質属性戦術を実現する具体的な実装メカニズムの設計判断を記録する。

---

## M-1: ログシステム

### 解決すべき問題

gridflow は QA-8（可観測性）と QA-9（LLM 親和性）を同時に満たすログシステムが必要である。具体的には:

- 実行パイプラインの各ステップの状態・所要時間を追跡可能にする
- KPI（計画書 10.1）をシステム内在の計測機構で取得可能にする
- CI/CD System と LLM Agent が構造化データとして取得可能にする
- 障害時にエラーの発生箇所と原因をログから 5 分以内に特定可能にする

### 設計判断

| 案 | 内容 | 判定 |
|---|---|---|
| 標準出力のみ | print/println で出力 | 構造化不可。フィルタリング・検索が困難。CI/CD/LLM が解析できない |
| 言語固有のログ機構 | 言語標準のログライブラリ | 言語選択（CON-1/ADR-001）が未確定のため、特定ライブラリには依存しない |
| **構造化ログインターフェース（採用）** | gridflow 独自の StructuredLogger インターフェースを定義し、実装を差替え可能にする | AS-2（DI）に準拠。言語非依存。テスト時はモック差替え |

### ログの構造

```
{
  "timestamp": "2026-04-01T12:00:00Z",
  "level": "INFO | WARN | ERROR | DEBUG",
  "component": "Orchestrator | Connector:OpenDSS | CDL | ...",
  "experiment_id": "exp-001",
  "step": "power_flow_run",
  "message": "Step completed",
  "duration_ms": 1234,
  "metadata": { ... }
}
```

**設計原則:**
- **構造化 JSON 形式:** LLM が解析可能（QA-9）。CI/CD が grep ではなく JSON パースで処理可能
- **コンポーネント名はドメイン用語:** AS-1（Ubiquitous Language）に準拠
- **experiment_id でフィルタ可能:** 複数実験が混在しても追跡可能
- **duration_ms を自動記録:** QA-10（性能効率）のオーバーヘッド計測が内在

### 出力先とスレッドモデル

- ログ書込みは **Logger スレッド** が非同期に行う（3.4.2）
- 出力先: ファイル（デフォルト）+ 標準出力（オプション）
- 出力先はインターフェース越しに差替え可能（Repository パターン）

### 実装での使い方

```
# コード上での使い方（言語非依存の擬似コード）
logger = context.logger
logger.info("Step started", step="power_flow", connector="OpenDSS")

# 自動的に以下が付与される:
#   timestamp, experiment_id, component, duration（スコープ終了時）
```

---

## M-2: エラー設計

### 解決すべき問題

- エラーが発生した箇所（Orchestrator? Connector? 外部ツール?）を即座に特定する（QA-8）
- エラーメッセージに原因と対処を含め、LLM が解析可能にする（QA-9）
- L1 研究者でも対処手順がわかるエラーメッセージにする

### エラー分類

| カテゴリ | 発生箇所 | 例 | ユーザーへの対処案 |
|---|---|---|---|
| **ConfigError** | Scenario Pack 検証 | 必須フィールド欠落、不正な値 | YAML の該当箇所と正しい形式を表示 |
| **ConnectorError** | Connector I/F | 外部ツール未起動、接続タイムアウト | セットアップ手順・ヘルスチェックコマンドを案内 |
| **ExecutionError** | ステップ実行中 | 外部ツールが返したエラー | 元のエラーメッセージ + gridflow としての解釈・対処 |
| **DataError** | CDL 読み書き | スキーマ不一致、ファイル破損 | データ修復手順・再実行案内 |
| **SystemError** | gridflow 内部 | 予期しない状態、メモリ不足 | バグレポート手順・回避策 |

### エラー型の設計

```
Error {
  category: ErrorCategory      # 上記5分類
  code: str                    # 一意のエラーコード（例: "CONN-001"）
  message: str                 # 人間可読な説明
  cause: str                   # 原因の説明
  resolution: str              # 対処手順
  context: {                   # 構造化コンテキスト
    experiment_id: str
    step: str
    connector: str
    raw_error: str             # 外部ツールの元エラー（保持）
  }
}
```

**設計判断:**
- **外部ツールのエラーを握りつぶさない:** `raw_error` フィールドに元のエラーを保持する（Anti-Corruption Layer は変換するが、元データは失わない）
- **エラーコード体系:** `カテゴリ略称-連番`（例: CONF-001, CONN-002）。エラーコードで検索可能
- **resolution フィールドの必須化:** エラーを出す側が対処案を考えることを強制する設計

---

## M-3: OS 抽象化と移植性

### 解決すべき問題

CON-2（Docker ベースのデプロイ）と CON-4（マルチアーキテクチャ）を満たしつつ、開発時のローカル実行も許容する。

### 設計判断

| 案 | 内容 | 判定 |
|---|---|---|
| POSIX API 直接使用 | ファイルパス、プロセス管理等を POSIX 前提で記述 | Docker 内は Linux なので動作する。ローカル開発で Windows 上は問題になる可能性 |
| **OSAL を作らない（採用）** | Docker コンテナ内は常に Linux。ホスト OS の違いは Docker が吸収。OS 抽象化層は不要 | CON-2 により、gridflow のコードはコンテナ内で動作する前提。OSAL は過剰な抽象化（CON-3: 1人+AI 開発に合わない） |
| OSAL を作る | OS 固有の API をラップする抽象化層 | ネイティブ実行を本格サポートする場合に必要だが、現時点では Docker が前提 |

**例外:**
- **ファイルパスの区切り文字:** パス操作には言語標準のパスライブラリを使用し、`/` のハードコーディングを避ける（ローカル開発で Windows を許容するため）
- **環境変数:** 設定は環境変数または設定ファイル経由で注入。OS 固有の設定方法には依存しない

---

## M-4: ミドルウェア

### 解決すべき問題

gridflow が外部ミドルウェア（DB、メッセージキュー、Web フレームワーク等）に依存するかどうか。

### 設計判断

| コンポーネント | ミドルウェア候補 | 判定 | 理由 |
|---|---|---|---|
| CDL 永続化 | DB（SQLite / PostgreSQL） | **P0 は不使用。ファイルシステムのみ** | Repository パターンで将来差替え可能。P0 段階で DB を導入する複雑さは CON-3 に合わない |
| Notebook → コア通信 | Web フレームワーク（HTTP API） | **最小限の HTTP サーバー** | Notebook 連携に必要。ただし重量フレームワーク（Django 等）は不使用。軽量な HTTP ライブラリまたは標準ライブラリで実装 |
| ログ基盤 | ELK / Grafana | **不使用** | 研究室の 1 台のマシンに過剰。ファイルベースのログ + CLI ビューアーで十分 |
| メッセージキュー | RabbitMQ / Redis | **不使用** | シングルプロセス設計（3.4.2）で不要。将来の並列 Scheduler でも OS レベルのプロセス間通信で十分 |
| コンテナオーケストレーション | Kubernetes | **不使用** | CON-3 に合わない。Docker Compose で十分 |

**原則: P0 段階ではミドルウェア依存を最小化し、全てをインターフェース越しに利用する。** 将来必要になったときに、Repository パターンや DI で差替える。

---

## M-5: テストフレームワーク

### 解決すべき問題

AS-3（TDD）を実践するためのテスト基盤。CON-1（言語未確定）のため、言語固有のフレームワーク名は確定しないが、**テスト戦略とテスト構成**はアーキテクチャレベルで決定する。

### テスト構成

| テスト層 | 対象 | 実行速度 | 外部依存 | 実行頻度 |
|---|---|---|---|---|
| **単体テスト** | Entities, Use Cases | 速い（ms） | なし（モック使用） | コミットごと |
| **統合テスト** | Connector × 外部ツール | 遅い（s〜min） | Docker コンテナ | PR ごと |
| **E2E テスト** | CLI → 全パイプライン | 遅い（min） | Docker Compose 全スタック | リリース前 |
| **再現性テスト** | 同一 Scenario Pack × 複数環境 | 遅い | AMD64 + ARM64 環境 | リリース前 |
| **性能テスト** | QA-10 のオーバーヘッド計測 | 遅い | 外部ツール | リリース前 |

### 設計判断

| 判断 | 内容 | 理由 |
|---|---|---|
| **テストフレームワークは言語選択と同時に決定** | ADR-001 で言語を選んだ後、その言語の標準的なテストフレームワークを採用 | CON-1 で言語未確定 |
| **Connector のモックを必須とする** | 全 Connector にモック実装を提供。単体テストで外部ツール不要にする | AS-3（TDD）+ AS-2（DI）。MockConnector は 3.2.2 で定義済み |
| **テストは CI で自動実行** | 全テスト通過を merge の前提条件にする | AS-3（TDD）|
| **カバレッジ目標は設けない** | TDD で書くとカバレッジは自然に高くなる。数値目標はテストの質を歪める | TDD のテストは仕様駆動であり、カバレッジ駆動ではない |

---

## M-6: CI/CD パイプライン

### 設計判断

| 判断 | 内容 | 理由 |
|---|---|---|
| **GitHub Actions を採用** | CON-5（OSS として公開）で GitHub を使用。GitHub Actions が最も統合度が高い | 無料枠で十分。セルフホストランナーは将来必要に応じて追加 |
| **マルチアーキビルド** | AMD64 + ARM64 で CI を実行（CON-4） | Apple Silicon 対応必須。GitHub Actions は ARM64 ランナーを提供 |

### パイプライン構成

```
PR 作成 / push
  ├── 単体テスト（全 OS アーキテクチャ）
  ├── 統合テスト（Docker ベース）
  └── lint / format チェック

merge to main
  ├── E2E テスト（Docker Compose 全スタック）
  ├── 再現性テスト（AMD64 + ARM64 で結果一致確認）
  ├── Docker イメージビルド + push
  └── ドキュメント生成

リリースタグ
  ├── 性能テスト（QA-10 オーバーヘッド計測）
  ├── リリースノート生成
  └── Docker イメージのバージョンタグ付け
```

---

## M-7: バージョン管理戦略

### 解決すべき問題

3 種類のバージョニング対象がある:

| 対象 | 何が変わるか | 影響範囲 |
|---|---|---|
| **gridflow 本体** | コード、インターフェース、CLI コマンド | 全ユーザー |
| **Scenario Pack** | 実験定義のスキーマ、パラメータ | 個別の実験 |
| **CDL** | データスキーマ、エクスポート形式 | 既存の実験結果 |

### 設計判断

| 判断 | 内容 | 理由 |
|---|---|---|
| **Semantic Versioning（SemVer）** | gridflow 本体は MAJOR.MINOR.PATCH で管理 | OSS の標準的な慣行（CON-5） |
| **Scenario Pack にバージョンを埋め込む** | Pack 内に `schema_version` フィールドを持つ | 古い Pack を新しい gridflow で読めるか判定するため |
| **CDL にスキーマバージョンを持つ** | 実験結果に `cdl_version` を記録 | UC-08（アップデート）のマイグレーション判定に使用 |
| **後方互換性の方針** | MINOR バージョンアップでは既存の Scenario Pack と CDL データの互換性を維持する。MAJOR で破壊的変更を許容するが、マイグレーションツールを提供する | QA-3（再現性）。古い実験が新バージョンでも再現できることを保証 |

### マイグレーション設計

UC-08 のシーケンス図（4.3.8）で示した通り:

```
アップデート時:
1. 現バージョンのバックアップ
2. 新バージョンのスキーマ差分を検出
3. Scenario Pack のスキーママイグレーション
4. CDL のスキーママイグレーション
5. 失敗時はバックアップからロールバック（all-or-nothing）
```

Bootstrap クラス（3.2.1）の `migrate()`, `backup()`, `rollback()` がこれを担う。

---

## M-8: 設定管理（Configuration）

### 解決すべき問題

gridflow には 3 層の設定がある:
- **gridflow 本体の設定** — ログレベル、データ保存先、HTTP ポート等
- **Connector 設定** — 各外部ツールの接続先、パラメータ
- **Scenario Pack の設定** — 実験固有の定義（FR-01）

L1 研究者が最初に触る部分であり、設定の混乱が導入の障壁になる（QA-1）。

### 設計判断

**設定の優先順位（低→高）:**
```
1. デフォルト値（コード内に定義）
2. 設定ファイル（gridflow.yaml）
3. 環境変数（GRIDFLOW_* プレフィックス）
4. CLI 引数（--option=value）
```

| 判断 | 内容 | 理由 |
|---|---|---|
| **設定形式は YAML** | JSON は冗長でコメント不可。TOML は電力系研究者に馴染みが薄い | L1 研究者にとって最も読み書きしやすい。Scenario Pack と同じ形式（一貫性） |
| **環境変数で上書き可能** | Docker 環境で設定を注入する標準的な手法 | CON-2（Docker ベース）との親和性。CI/CD での設定切替えも容易 |
| **Scenario Pack の設定は独立** | 本体設定と Scenario Pack 設定を混在させない | QA-3（再現性）。Scenario Pack は実験の再現に必要な全情報を自己完結で持つ |
| **設定のバリデーションを起動時に実行** | 設定ファイルのスキーマ検証を gridflow 起動時（UC-04）に行う | Fail-fast。実行時に設定エラーが発覚するのを防ぐ |

---

## M-9: シリアライゼーション / データフォーマット

### 解決すべき問題

CDL（Entities 層）のデータをどのような形式で永続化・エクスポートするか。性能・可読性・互換性のトレードオフがある。

### 設計判断

| 用途 | 形式 | 理由 |
|---|---|---|
| **Scenario Pack** | YAML | 人間が読み書きする（L1）。コメント可能。バージョン管理（diff）に適する |
| **CDL 永続化（内部）** | JSON | 構造化済み。LLM が読める（QA-9）。スキーマ検証が容易。性能要件がない場所（QA-10: ボトルネックは外部ツール） |
| **CDL エクスポート（外部向け）** | CSV / JSON / Parquet（ユーザー選択） | CSV: 表計算ソフト。JSON: プログラム処理。Parquet: 大規模データ・高速読込み |
| **ログ** | JSON Lines（1行1レコード） | 追記が高速。行単位でパース可能。構造化済み（M-1） |
| **プロセス間通信（M-13）** | JSON | デバッグ容易性を優先。バイナリプロトコルは CON-3 に合わない |

| 判断 | 内容 | 理由 |
|---|---|---|
| **内部永続化にバイナリ形式を使わない** | MessagePack, Protocol Buffers 等は不使用 | CON-3（1人+AI 開発）。デバッグ困難。QA-9（LLM が読めない）。QA-10 分析で I/O はボトルネックではない |
| **Parquet はエクスポート専用** | CDL 内部は JSON で保持し、エクスポート時のみ Parquet 変換 | Parquet は追記が困難（ステップ毎の flush と相性が悪い）。読込み性能が必要なのはエクスポート後の分析段階 |

---

## M-10: 依存性注入（DI）の実現方式

### 解決すべき問題

AS-2（Clean Architecture）で DI を方針としたが、具体的にどう注入するか。

### 設計判断

| 案 | 内容 | 判定 |
|---|---|---|
| DI フレームワーク | 言語固有の DI コンテナ（例: Python の inject/dependency-injector） | 言語未確定（CON-1）。フレームワーク依存は AS-2 に反する |
| **コンストラクタ注入 + ファクトリ（採用）** | 各クラスが依存をコンストラクタ引数で受け取る。生成はファクトリ関数/クラスで一箇所に集約 | 最もシンプル。フレームワーク不要。テスト時にモックを渡すだけ。言語非依存 |
| Service Locator | グローバルなレジストリから依存を取得 | テストが困難（隠れた依存）。AS-3（TDD）に反する |

### 具体的な実現イメージ

```
# ファクトリ（アプリケーション起動時に1回だけ構築）
def create_orchestrator(config):
    cdl = FileSystemCDL(config.data_dir)          # Repository パターン
    logger = StructuredLogger(config.log_dir)       # M-1
    connector = OpenDSSConnector(config.opendss)    # Strategy パターン
    registry = FileSystemRegistry(config.pack_dir)  # Repository パターン
    return Orchestrator(cdl, logger, connector, registry)

# テスト時
def test_orchestrator():
    cdl = MockCDL()
    logger = MockLogger()
    connector = MockConnector(responses={...})
    registry = MockRegistry(packs={...})
    orch = Orchestrator(cdl, logger, connector, registry)  # 同じコンストラクタ
    result = orch.run("test-pack")
    assert result.status == SUCCESS
```

**ポイント:**
- **コンストラクタの引数がインターフェースのリスト** = そのクラスの依存関係が明示的
- テスト時にモックを渡すだけ。DI フレームワーク不要
- 「テストが書きにくい＝依存が多すぎるシグナル」（AS-3）がコンストラクタ引数の数で即座にわかる
