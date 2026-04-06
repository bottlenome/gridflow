# gridflow アーキテクチャドキュメント

**gridflow** — Power System Workflow Engine のアーキテクチャを ACDM（Architecture Centric Design Method）に基づいて記述する。

## 更新履歴

| 版数 | 日付 | 変更内容 | 変更者 |
|---|---|---|---|
| 0.1 | 2026-03-31 | 初版作成（Round 0〜3: 導入、重要事項、静的ビュー、動的ビュー） | bottlenome + Claude |
| 0.2 | 2026-04-01 | 実装メカニズム（03b）追加、不整合修正 | bottlenome + Claude |
| 0.3 | 2026-04-01 | Round 4 完了（ビュー間対応、評価、ADR、付録、README） | bottlenome + Claude |
| 0.4 | 2026-04-01 | デザインレビュー反映（Bounded Context Map、開発ルール、ADR-001 確定） | bottlenome + Claude |
| 0.5 | 2026-04-01 | AS-5（論文生産性戦略）追加、QA-11 追加、全ビュー反映 | bottlenome + Claude |
| 0.6 | 2026-04-06 | アーキテクチャレビュー記録（09_review_record.md）追加 | Claude |

## ドキュメント構成

| ファイル | 内容 |
|---|---|
| [01_introduction.md](01_introduction.md) | はじめに（目的、対象読者、スコープ、用語定義、計画書からの変更点） |
| [02_architecture_significance.md](02_architecture_significance.md) | アーキテクチャの重要事項（ビジネス目標、ドライバー、戦略、パターン・戦術） |
| [03_static_view.md](03_static_view.md) | 静的ビュー（ブロック図、クラス図、配置図、プロセスビュー、拡張性戦略） |
| [03b_mechanisms.md](03b_mechanisms.md) | 実装メカニズム詳細（ログ、エラー、設定管理、テスト、CI/CD 等 14 項目） |
| [04_dynamic_view.md](04_dynamic_view.md) | 動的ビュー（ユースケース図、シナリオ UC-01〜UC-10、シーケンス図） |
| [05_view_mapping.md](05_view_mapping.md) | ビュー間の対応（コンポーネント↔UC↔シーケンス図、ドライバー→ビュー要素トレーサビリティ） |
| [06_architecture_evaluation.md](06_architecture_evaluation.md) | アーキテクチャ評価（QA 達成見込み、リスク、感度点、トレードオフ、未解決事項） |
| [07_adr.md](07_adr.md) | 設計判断の記録（ADR-001〜ADR-007） |
| [08_appendix.md](08_appendix.md) | 付録（計画書対応表、QA 一覧、用語集、参考文献） |
| [09_review_record.md](09_review_record.md) | アーキテクチャレビュー記録（ACDM 準拠性チェック、構造品質・整合性レビュー、指摘事項） |

## 参照ドキュメント

- [gridflow 計画書](../gridtwin_lab_plan.md) — プロダクト定義、機能要件、ロードマップ
- [アーキテクチャドキュメント作成計画](../architecture_document_plan.md) — 本ドキュメント群の作成プロセス
- [基本設計書](../basic_design/) — 本 ACDM を入力とした外部仕様設計
- [詳細設計書](../detailed_design/) — 基本設計書を入力とした内部仕様設計（REQ-xxx → DD-xxx 展開）

## 読み方

1. **全体像を掴む:** 01 → 02（2.1 ビジネス目標 + 2.3 戦略）→ 03（3.1.2 概念アーキテクチャ）
2. **設計判断を理解する:** 03（3.1.3 外部システム分析 + 3.1.4 サブシステム分割）→ 07（ADR）
3. **振る舞いを確認する:** 04（UC シナリオ + シーケンス図）
4. **横断的に検証する:** 05（ビュー間対応）→ 06（評価・リスク・トレードオフ）
5. **実装の詳細:** 03b（メカニズム）→ 03（3.5 Plugin API）
