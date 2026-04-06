# gridflow 基本設計書

**gridflow** — Power System Workflow Engine の基本設計書。IPA（独立行政法人情報処理推進機構）のソフトウェア開発ガイドラインに準拠し、アーキテクチャドキュメント（ACDM）を入力として外部仕様レベルの設計を記述する。

## 更新履歴

| 版数 | 日付 | 変更内容 | 変更者 |
|---|---|---|---|
| 0.1 | 2026-04-01 | 初版作成（全12章 + 付録） | bottlenome + Claude |
| 0.2 | 2026-04-06 | レビュー記録（review_record.md）追加 | Claude |

## 目次

| 章 | ファイル | 内容 |
|---|---|---|
| 第1章 | [01_requirements.md](01_requirements.md) | 要求一覧（REQ-xxx ID 付きトレーサビリティマトリクス） |
| 第2章 | [02_system_architecture.md](02_system_architecture.md) | システム方式設計（Docker 構成、環境定義） |
| 第3章 | [03_function_design.md](03_function_design.md) | 機能設計（Scenario Pack / Orchestrator / Connector / CDL / Benchmark / CLI） |
| 第4章 | [04_cli_design.md](04_cli_design.md) | CLI インターフェース設計（コマンド体系、入出力仕様、エラーメッセージ） |
| 第5章 | [05_data_design.md](05_data_design.md) | データ設計（CDL データモデル、Scenario Pack 構造、エクスポート形式） |
| 第6章 | [06_external_interface.md](06_external_interface.md) | 外部インターフェース設計（Connector IF / Plugin API / IPC） |
| 第7章 | [07_performance.md](07_performance.md) | 性能設計（オーバーヘッド目標、ボトルネック対策、スケーラビリティ） |
| 第8章 | [08_reliability.md](08_reliability.md) | 信頼性設計（エラーハンドリング、再現性保証、ログ、障害復旧） |
| 第9章 | [09_security.md](09_security.md) | セキュリティ設計（脅威モデル、コンテナセキュリティ、データ保護） |
| 第10章 | [10_deployment.md](10_deployment.md) | 移行・導入設計（導入手順、既存環境からの移行、バージョンアップ） |
| 第11章 | [11_test_policy.md](11_test_policy.md) | テスト方針（テストレベル、品質属性検証、CI/CD パイプライン） |
| 第12章 | [12_operation.md](12_operation.md) | 運用・保守設計（運用想定、監視、保守プロセス） |
| 付録 | [appendix.md](appendix.md) | 用語集、参考文献、更新ドキュメント一覧 |
| レビュー記録 | [review_record.md](review_record.md) | IPA 準拠性チェック、構造品質・整合性レビュー、指摘事項管理 |

## 参照ドキュメント

| ドキュメント | パス | 関係 |
|---|---|---|
| アーキテクチャドキュメント | [../architecture/](../architecture/) | 上位設計（入力） |
| 計画書 | [../gridtwin_lab_plan.md](../gridtwin_lab_plan.md) | 要件定義（入力） |
| 基本設計書作成計画 | [../basic_design_plan.md](../basic_design_plan.md) | 本ドキュメントの作成プロセス |
| 詳細設計書 | [../detailed_design/](../detailed_design/) | 下位設計（出力）— 本基本設計書の各 REQ-xxx を DD-xxx に展開 |

## 読み方

1. **要求の全体像:** 第1章（要求一覧）で REQ-xxx ID と全要求を把握する
2. **システム構成:** 第2章（システム方式）→ 第5章（データ設計）で構造を理解する
3. **機能の詳細:** 第3章（機能設計）→ 第4章（CLI 設計）で振る舞いを理解する
4. **外部連携:** 第6章（外部 IF）で Connector / Plugin API を理解する
5. **非機能要件:** 第7〜9章（性能・信頼性・セキュリティ）で品質面を確認する
6. **導入・運用:** 第10〜12章（導入・テスト・運用）で実運用を確認する
7. **トレーサビリティ検証:** 第1章の 1.7 対応表で各要求が設計で対応されているか確認する

## 設計方針

- **アーキテクチャドキュメントとの一貫性**: 用語・ID は ACDM に準拠
- **トレーサビリティ第一**: 全設計項目が REQ-xxx を通じてビジネス目標まで追跡可能
- **段階的詳細化**: アーキテクチャの抽象度を1段下げ、実装の詳細は詳細設計書に委ねる
- **IPA 準拠 + gridflow 最適化**: IPA 標準構成を基本とし、gridflow 固有の事情（CLI ベース、Docker 環境、研究用途）に合わせて読み替える
