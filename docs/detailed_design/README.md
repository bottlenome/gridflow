# gridflow 詳細設計書

**gridflow** — Power System Workflow Engine の詳細設計書。IPA（独立行政法人情報処理推進機構）のソフトウェア開発ガイドラインに準拠し、基本設計書（外部仕様）を入力として内部仕様（実装可能な設計）レベルの設計を記述する。基本設計書が「何をするか（What）」を定義したのに対し、本詳細設計書は「どのように実現するか（How）」を定義する。

## 更新履歴

| 版数 | 日付 | 変更内容 | 変更者 |
|---|---|---|---|
| 0.1 | 2026-04-03 | 初版作成（全11章 + 付録） | bottlenome + Claude |
| 0.2 | 2026-04-04 | 第3章後半追記、Phase 6 整合性確認完了 | bottlenome + Claude |
| 0.3 | 2026-04-06 | レビュー記録（review_record.md）追加 | Claude |

## 目次

| 章 | ファイル | 内容 |
|---|---|---|
| 第1章 | [01_requirements.md](01_requirements.md) | 要件一覧（DD-xxx ID 体系、REQ-xxx → DD-xxx トレーサビリティマトリクス） |
| 第2章 | [02_module_structure.md](02_module_structure.md) | モジュール構成設計（パッケージ構成、依存関係、レイヤー配置、命名規則） |
| 第3章 | [03_class_design.md](03_class_design.md) | クラス設計（Scenario Pack / Orchestrator / CDL / Connector / Benchmark / CLI / Plugin API / 共通基盤） |
| 第4章 | [04_process_flow.md](04_process_flow.md) | 処理フロー設計（UC-01〜UC-10 シーケンス図・アクティビティ図、バッチ処理設計） |
| 第5章 | [05_state_transition.md](05_state_transition.md) | 状態遷移設計（Orchestrator / Connector / Scenario Pack / バッチジョブの状態遷移図・状態遷移表） |
| 第6章 | [06_data_detail.md](06_data_detail.md) | データ詳細設計（ER 図、CDL 属性定義、JSON Schema、入出力設計、物理ストレージ設計） |
| 第7章 | [07_algorithm.md](07_algorithm.md) | アルゴリズム設計（時間同期、メトリクス計算、スケジューリング、性能設計） |
| 第8章 | [08_error_design.md](08_error_design.md) | エラー設計（例外クラス階層、エラーコード E-xxxx 体系、リトライ・フォールバック、ログ出力仕様） |
| 第9章 | [09_config_management.md](09_config_management.md) | 設定管理設計（設定項目一覧、優先順位ルール、デフォルト値、Docker Compose テンプレート） |
| 第10章 | [10_test_detail.md](10_test_detail.md) | テスト詳細設計（テストケース設計、単体・統合・E2E・品質属性テスト、フィクスチャ設計） |
| 第11章 | [11_build_deploy.md](11_build_deploy.md) | ビルド・デプロイ詳細設計（Dockerfile、Docker Compose、CI/CD パイプライン、パッケージング、SemVer） |
| 付録 | [appendix.md](appendix.md) | 完全対応表（REQ-xxx → DD-xxx）、用語集、参考文献、更新ドキュメント一覧 |
| レビュー記録 | [review_record.md](review_record.md) | IPA 準拠性チェック、構造品質・整合性レビュー、既存レビュー統合、指摘事項管理 |

## 参照ドキュメント

| ドキュメント | パス | 関係 |
|---|---|---|
| アーキテクチャドキュメント | [../architecture/](../architecture/) | 上位設計（設計判断の根拠） |
| 基本設計書 | [../basic_design/](../basic_design/) | 外部仕様（直接入力） |
| 計画書 | [../gridtwin_lab_plan.md](../gridtwin_lab_plan.md) | プロダクト定義・ロードマップ |
| 詳細設計書作成計画 | [../detailed_design_plan.md](../detailed_design_plan.md) | 本ドキュメントの作成プロセス |

## 読み方

1. **トレーサビリティの確認:** 第1章（要件一覧）で DD-xxx ID 体系と REQ-xxx からの追跡関係を把握する
2. **構造の理解:** 第2章（モジュール構成）→ 第6章（データ詳細設計）でパッケージ構成・データモデルを理解する
3. **クラスの詳細:** 第3章（クラス設計）で全コンポーネントのクラス・メソッド（IPO 形式）を理解する
4. **振る舞いの理解:** 第4章（処理フロー）→ 第5章（状態遷移）でシーケンス図・状態遷移図を確認する
5. **アルゴリズム:** 第7章（アルゴリズム設計）で時間同期・メトリクス計算等の具体的ロジックを確認する
6. **エラー・設定:** 第8章（エラー設計）→ 第9章（設定管理）でエラーハンドリングと設定体系を確認する
7. **テスト・デプロイ:** 第10章（テスト詳細）→ 第11章（ビルド・デプロイ）で品質保証と配布を確認する
8. **トレーサビリティ検証:** 付録 A の完全対応表で各要求が詳細設計で対応されているか確認する

## 設計方針

- **基本設計書との一貫性**: 用語・ID は基本設計書および ACDM に準拠する。詳細設計書独自の用語は付録で定義する
- **トレーサビリティ第一**: 全設計項目が DD-xxx → REQ-xxx → BG-xxx まで追跡可能であること
- **実装可能な粒度**: クラス・メソッドシグネチャ・型定義レベルまで具体化する。ただし実装コードそのものは書かない（疑似コード・型ヒント付きシグネチャまで）
- **IPA 準拠 + gridflow 最適化**: IPA のプログラム設計書・モジュール設計書の標準構成を基本とし、Python / Clean Architecture / Docker 環境に合わせて読み替える
- **章単位の独立作成**: 各章は独立してレビュー可能な粒度とし、Phase 順に完成させる
- **Mermaid 図の活用**: クラス図・シーケンス図・アクティビティ図・状態遷移図・ER 図を Mermaid 記法で記述し、ドキュメント内で直接レンダリング可能とする
- **IPO 形式の徹底**: 全メソッドの定義に Input（引数・型）→ Process（処理概要）→ Output（戻り値・型・例外）を明記し、実装者が迷わない粒度とする
