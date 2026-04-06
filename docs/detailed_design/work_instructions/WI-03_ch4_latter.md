# WI-03: 第4章後半（4.6〜4.15）

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/04_process_flow.md` に追記
**前提**: 4.1〜4.5が既に書かれている。Readで既存内容を読み、末尾に追記した全体をWriteする。
**共通ルール**: `WI-00_common.md` 参照

---

## 4.6 ログ・実行トレースフロー（UC-05）
`gridflow logs [--level ERROR] [--follow]` → StructuredLogger → ログファイル読み込み → フィルタ → CLI出力
`gridflow trace <exp_id>` → CDLRepository → 実行トレース取得 → タイムライン表示
`gridflow metrics` → KPIメトリクス集計 → テーブル/JSON出力
シーケンス図で記述。

## 4.7 デバッグ・エラー対応フロー（UC-06）
`gridflow debug` → Docker状態確認 → Connectorヘルスチェック → 設定検証 → 診断レポート出力
シーケンス図で記述。

## 4.8 インストール・セットアップフロー（UC-07）
pip install gridflow → gridflow init → 設定ファイル生成(~/.gridflow/config.yaml) → docker compose pull → ヘルスチェック → 完了
目標: 30分以内（QA-1）。シーケンス図で記述。

## 4.9 アップデート・アンインストールフロー（UC-08）
`gridflow update` → 最新バージョン確認 → pip upgrade → Dockerイメージ更新 → マイグレーション実行 → 完了
シーケンス図で記述。

## 4.10 結果参照・データエクスポートフロー（UC-09）
`gridflow results show <exp_id>` → CDLRepository.get_result() → テーブル表示
`gridflow results export <exp_id> --format parquet -o ./out/` → CDLRepository.export() → ファイル書き出し
シーケンス図で記述。

## 4.11 LLM による実験指示フロー（UC-10）
LLM → 構造化JSON/YAMLコマンド → CLIApp解析 → 通常のコマンドフローに委譲
入力: {"command": "run", "pack": "microgrid-01", "options": {"seed": 42}}
出力: {"status": "success", "experiment_id": "exp-001", "metrics": {...}}
シーケンス図で記述。

## 4.12 Connector 初期化・実行フロー
ContainerManager.start() → ConnectorInterface.initialize(config) → ヘルスチェック待ち → ステップループ[execute(step,context)→StepResult] → teardown()
シーケンス図で記述。

## 4.13 CDL 変換フロー
外部ツール出力(raw) → DataTranslator.to_canonical(raw) → CanonicalData → CDLRepository.store()
CDLRepository.get() → CanonicalData → DataTranslator.from_canonical(data) → ツールネイティブ形式
シーケンス図で記述。

## 4.14 Plugin ロード・実行フロー
起動時: PluginDiscovery.discover(plugin_dir) → PluginInfo一覧 → PluginRegistry.register() → 各Plugin.initialize()
実行時: PluginRegistry.get(name) → Plugin.execute()
シーケンス図で記述。

## 4.15 エラーハンドリングフロー
Domain例外発生 → UseCase層キャッチ(文脈追加) → Adapter層キャッチ(ユーザーメッセージ変換) → CLI出力(exit code + エラーメッセージ)
Mermaid flowchartで例外伝播フローを記述。
