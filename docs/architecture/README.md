# gridflow アーキテクチャドキュメント

**gridflow** — Power System Workflow Engine のアーキテクチャを ACDM（Architecture Centric Design Method）に基づいて記述する。

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

## 参照ドキュメント

- [gridflow 計画書](../gridtwin_lab_plan.md) — プロダクト定義、機能要件、ロードマップ
- [アーキテクチャドキュメント作成計画](../architecture_document_plan.md) — 本ドキュメント群の作成プロセス

## 読み方

1. **全体像を掴む:** 01 → 02（2.1 ビジネス目標 + 2.3 戦略）→ 03（3.1.2 概念アーキテクチャ）
2. **設計判断を理解する:** 03（3.1.3 外部システム分析 + 3.1.4 サブシステム分割）→ 07（ADR）
3. **振る舞いを確認する:** 04（UC シナリオ + シーケンス図）
4. **横断的に検証する:** 05（ビュー間対応）→ 06（評価・リスク・トレードオフ）
5. **実装の詳細:** 03b（メカニズム）→ 03（3.5 Plugin API）
