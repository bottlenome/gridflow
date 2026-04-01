# 第10章 移行・導入設計

本章では、gridflow の導入手順、既存研究環境からの移行方針、およびバージョンアップ方針を定義する。

## 更新履歴

| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-01 | 初版作成 |

---

## 10.1 導入手順

**関連要求:** REQ-Q-001 (セットアップ30分以内), REQ-Q-002 (TTFS 1時間以内)

### 前提条件

| 項目 | 要件 |
|---|---|
| Docker Desktop | v4.x 以上（Docker Engine 24+, Compose v2+） |
| git | v2.30 以上 |
| ネットワーク | Docker Hub および GitHub へのアクセス |
| OS | Windows 10/11, macOS 12+, Ubuntu 22.04+（Docker Desktop 対応） |

### 導入フロー（UC-07）

```
1. git clone https://github.com/gridflow/gridflow.git
2. cd gridflow
3. docker compose up
   └─ auto-setup が自動実行:
      a. Python 依存パッケージのインストール
      b. CDL スキーマの初期化
      c. デフォルト Connector イメージのビルド
      d. サンプル Scenario Pack のダウンロード
4. gridflow run sample-ieee13  ← サンプルシナリオ実行で動作確認
```

### 導入完了基準

| 基準 | 目標値 | 測定方法 |
|---|---|---|
| セットアップ所要時間 | < 30 分 | clone 開始から sample 実行完了まで |
| 初回成功率 | > 90% | CI/CD 上の E2E セットアップテスト |
| TTFS（Time To First Simulation） | < 1 時間 | セットアップ完了から独自シナリオ実行まで |

### トラブルシューティング

- `gridflow doctor` コマンドで環境診断を実行
- Docker リソース不足時の推奨設定（CPU 4+, Memory 8GB+）を表示
- ネットワークプロキシ環境向けの設定ガイドを提供

---

## 10.2 既存研究環境からの移行方針

**関連要求:** REQ-Q-002 (TTFS), REQ-Q-007 (後方互換性)

### 基本方針

gridflow は既存ツールの**置き換え**ではなく**統合**を目指す。研究者が使い慣れた OpenDSS / pandapower スクリプトを活かしつつ、gridflow のワークフロー管理機能を段階的に導入する。

### 移行パス

| 段階 | 内容 | 対象研究者 |
|---|---|---|
| 共存 | gridflow を既存環境と並行インストール。既存スクリプトはそのまま利用 | 全研究者 |
| インポート | `gridflow import` で既存スクリプトを Scenario Pack に変換 | 移行希望者 |
| 統合 | gridflow のオーケストレーション・ベンチマーク機能をフル活用 | 習熟後 |

### インポートツール

| 対象形式 | コマンド | 変換内容 |
|---|---|---|
| OpenDSS (.dss) | `gridflow import opendss <path>` | ネットワーク定義 → CDL topology + asset |
| pandapower (.json/.py) | `gridflow import pandapower <path>` | ネットワーク + 時系列 → Scenario Pack |
| CSV 時系列データ | `gridflow import timeseries <path>` | 時系列 → CDL timeseries 形式 |

### Scenario Pack テンプレート

- 既存スクリプトの構造を分析し、対応する Scenario Pack テンプレートを提案
- `gridflow scaffold --from-script <path>` で既存スクリプトから Pack 雛形を生成
- 強制移行なし: gridflow の Connector 経由で既存ツールをそのまま呼び出し可能

---

## 10.3 バージョンアップ方針

**関連要求:** REQ-Q-007 (後方互換性), REQ-Q-001 (セットアップ容易性)

### バージョニング規則（UC-08）

gridflow は Semantic Versioning 2.0.0 に従う。

| バージョン要素 | 変更契機 | 例 |
|---|---|---|
| MAJOR (X.0.0) | 後方互換性を破る変更 | CDL スキーマの非互換変更 |
| MINOR (0.X.0) | 後方互換な機能追加 | 新 Connector 追加 |
| PATCH (0.0.X) | バグ修正 | Connector の不具合修正 |

### 管理対象バージョン

| 対象 | バージョンキー | 管理場所 |
|---|---|---|
| gridflow 本体 | `version` | `pyproject.toml` |
| Scenario Pack スキーマ | `schema_version` | Scenario Pack メタデータ |
| CDL スキーマ | `cdl_version` | CDL 定義ファイル |

### スキーマ互換性マトリクス

| gridflow | schema_version | cdl_version | 互換性 |
|---|---|---|---|
| 1.x | 1.0 - 1.x | 1.0 - 1.x | 完全互換 |
| 2.x | 1.0 - 2.x | 1.0 - 2.x | 1.x は Migrator で自動変換 |

### Migrator コンポーネント

バージョンアップ時のデータ移行は Migrator が一括管理する。

```
gridflow upgrade
  ├─ 1. バックアップ作成 (gridflow backup create)
  ├─ 2. スキーマ移行実行 (Migrator.migrate())
  ├─ 3. 整合性検証 (Migrator.verify())
  └─ 4. 失敗時ロールバック (Migrator.rollback())
```

| ステップ | 処理内容 | 失敗時の動作 |
|---|---|---|
| バックアップ | Scenario Pack・CDL データ・設定ファイルの zip 保存 | アップグレード中止 |
| 移行 | スキーマ変換スクリプトの順次適用 | ロールバック実行 |
| 検証 | 移行後データの整合性チェック | ロールバック実行 |
| ロールバック | バックアップからの復元 | 手動復旧ガイド表示 |

### バージョンアップ通知

- `gridflow version --check` で最新バージョンとの差分を確認
- MAJOR アップデート時は移行ガイドを自動表示
- 破壊的変更は最低 1 MINOR バージョン前に非推奨警告を出力
