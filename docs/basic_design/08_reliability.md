# 第8章 信頼性設計

本章では、gridflow の信頼性を支えるエラーハンドリング方針、再現性保証メカニズム、ログ設計、および障害復旧方針を示す。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |
| 0.2 | 2026-04-06 | GridflowError階層にサブクラスを追加、命名規則を明記（BD-REV-002） |

---

## 8.1 エラーハンドリング方針

### GridflowError 階層

すべての gridflow 例外は `GridflowError` 基底クラスを継承し、統一的な構造を持つ。

```
GridflowError
├── ConfigError          # 設定・Scenario Pack の検証エラー（CONF-xxx）
│   ├── ValidationError      # pack.yaml スキーマ検証失敗（CONF-001）
│   └── DuplicatePackError   # 同名・同バージョンの Pack 重複（CONF-002）
├── ConnectorError       # 外部シミュレータ連携エラー（CONN-xxx）
│   ├── ConnectorStartError      # Connector 起動失敗（CONN-001）
│   ├── ConnectorExecutionError  # ステップ実行エラー（CONN-002）
│   └── ConnectorTimeoutError    # タイムアウト（CONN-003）
├── ExecutionError       # ワークフロー実行中のエラー（EXEC-xxx）
├── DataError            # CDL データ変換・検証エラー（DATA-xxx）
└── SystemError          # Docker・ファイルシステム等の基盤エラー（SYS-xxx）
```

**命名規則**: カテゴリベースの親クラス（ConfigError, ConnectorError 等）の下に、操作固有のサブクラス（ValidationError, ConnectorStartError 等）を配置する。第3章の Protocol 定義で使用する例外名はサブクラス名を使用し、エラーコード（CONF-001 等）と1:1で対応する。

### エラー属性

| 属性 | 型 | 必須 | 説明 |
|---|---|---|---|
| `category` | `str` | Yes | エラー分類（CONF / CONN / EXEC / DATA / SYS） |
| `code` | `str` | Yes | エラーコード（例: `CONF-001`） |
| `message` | `str` | Yes | 人間可読なエラーメッセージ |
| `cause` | `Exception \| None` | No | 元例外（チェーン用） |
| `resolution` | `str` | Yes | ユーザーが取るべき対処手順 |

### エラーコード体系

| 接頭辞 | 分類 | 例 |
|---|---|---|
| `CONF-xxx` | 設定エラー | `CONF-001`: Scenario Pack スキーマ不正 |
| `CONN-xxx` | コネクタエラー | `CONN-001`: シミュレータ接続タイムアウト |
| `EXEC-xxx` | 実行エラー | `EXEC-001`: ステップ実行失敗 |
| `DATA-xxx` | データエラー | `DATA-001`: CDL 変換失敗 |
| `SYS-xxx` | システムエラー | `SYS-001`: Docker デーモン応答なし |

### 設計原則

- **resolution 必須**: すべてのエラーに対処手順を含め、ユーザーが次のアクションを判断できるようにする
- **例外チェーン**: `cause` により元例外を保持し、デバッグ時のトレーサビリティを確保する
- **CLI 出力**: エラーコード + メッセージ + resolution を構造化して表示する
- **ログ連携**: エラー発生時に `StructuredLogger` へ自動記録する（`REQ-Q-008`）

---

## 8.2 再現性保証メカニズム

`REQ-Q-003` に基づき、同一の Scenario Pack と seed を用いた実行が、異なるマシン上でも同一の結果を返すことを保証する。

### 再現性の三本柱

| 柱 | 仕組み | 保証内容 |
|---|---|---|
| Scenario Pack 不変性 | Pack はバージョン管理され、実行時にハッシュ検証を行う。実行後の Pack 改変は検出可能 | 入力条件の同一性 |
| seed 管理 | 乱数 seed を Scenario Pack 内で明示指定。未指定時は自動生成し、メタデータへ記録する | 確率的要素の再現 |
| Docker 環境固定 | コンテナイメージをダイジェスト付きでピン留め。ランタイム環境の差異を排除する | 実行環境の同一性 |

### スキーマバージョニング

- Scenario Pack のスキーマにバージョン番号を付与する
- スキーマ変更時は Migrator がマイグレーションパスを提供する
- 旧バージョンの Pack も明示的なマイグレーション手順で再現可能とする

### 検証フロー

1. `gridflow run` 実行時に Scenario Pack のハッシュを算出・記録する
2. seed を実験メタデータへ保存する
3. Docker イメージのダイジェストを実行ログへ記録する
4. 再実行時に上記 3 要素を比較し、差異があれば警告を出力する

---

## 8.3 ログ設計

### StructuredLogger インターフェース

| メソッド | 説明 |
|---|---|
| `info(msg, **ctx)` | 情報レベルログ出力 |
| `warning(msg, **ctx)` | 警告レベルログ出力 |
| `error(msg, **ctx)` | エラーレベルログ出力 |
| `debug(msg, **ctx)` | デバッグレベルログ出力 |
| `timed(label)` | コンテキストマネージャ。ブロックの所要時間を自動計測・記録する |

### JSON 構造化ログ

```json
{
  "timestamp": "2026-04-01T10:30:00.123Z",
  "level": "INFO",
  "experiment_id": "exp-20260401-001",
  "step": "opendss_simulation",
  "message": "Simulation completed",
  "duration_ms": 4523,
  "context": {
    "network": "ieee13",
    "variant": 3
  }
}
```

### 非同期出力

- `QueueHandler` を使用し、ログメッセージをキューへ投入する
- バックグラウンドスレッドがキューから取り出してファイルへ書き込む
- メインスレッドのブロックを回避し、`REQ-Q-010` のオーバーヘッド目標に寄与する

### フィルタリング

- `experiment_id` による実験単位のログ抽出が可能
- CLI で `gridflow logs --experiment <id>` として提供する
- ログレベルによるフィルタリングも対応する

---

## 8.4 障害復旧方針

### グレースフルシャットダウン

- SIGTERM / SIGINT 受信時に実行中ステップの完了を待機する（タイムアウト付き）
- 中間状態を CDL ストレージへ保存し、途中結果の損失を防ぐ
- 実行中コンテナを安全に停止する

### ステップ再開

- `--from-step` オプションにより、失敗したステップからワークフローを再開できる（`REQ-F-002`）
- 前ステップの CDL 出力が保存されていることを前提とする
- 再開時に Scenario Pack のハッシュ一致を検証する

### マイグレーション時のバックアップ

- Migrator によるスキーマ更新前に、対象データの自動バックアップを作成する
- マイグレーション失敗時はバックアップからのロールバックが可能
- バックアップの保持期間はユーザー設定で制御する

---

## 参照要求

| 要求 ID | 関連セクション |
|---|---|
| REQ-Q-003 | 8.2 |
| REQ-Q-008 | 8.1, 8.3 |
| REQ-Q-010 | 8.3 |
| REQ-F-002 | 8.4 |
