# WI-08: 付録

**対象ファイル**: `/home/user/gridflow/docs/detailed_design/appendix.md` を新規作成
**共通ルール**: `WI-00_common.md` 参照
**入力**: `/home/user/gridflow/docs/detailed_design/01_requirements.md` の1.2節（要件対応表）を読んで、付録Aに再掲する。

冒頭:
```markdown
# 付録
## 更新履歴
| 版数 | 日付 | 変更内容 |
|---|---|---|
| 0.1 | 2026-04-03 | 初版作成 |
```

---

## A. 要件一覧（全 REQ-xxx → DD-xxx 完全対応表）
01_requirements.mdの1.2節の内容を再掲・参照リンク。

## B. 用語集
基本設計書付録の用語に加え、詳細設計固有の用語:
- IPO: Input-Process-Output。メソッド定義の記述形式
- Protocol: typing.Protocolによる構造的部分型（DIP実現手法）
- dataclass: Python dataclassesモジュールのイミュータブルデータ構造
- Clean Architecture: Uncle Bob提唱の4層アーキテクチャ（Entities/UseCases/InterfaceAdapters/Frameworks）
- Strategy パターン: アルゴリズムを交換可能にするGoFデザインパターン
- Mermaid: Markdownベースの図表記述言語
- structlog: Python構造化ログライブラリ
- JSON Lines: 1行1JSONオブジェクトのログ形式

## C. 参考文献
1. IPA「共通フレーム2013」
2. IPA「機能要件の合意形成ガイド」
3. Robert C. Martin "Clean Architecture"
4. Python PEP 8 Style Guide
5. Semantic Versioning 2.0.0 (semver.org)
6. Docker Compose Specification
7. pytest documentation
8. structlog documentation

## D. 更新ドキュメント一覧
全ファイルの作成日・更新日を表形式で。01_requirements.md〜11_build_deploy.md + appendix.md。
