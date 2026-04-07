# 詳細設計書 レビュー記録

## 更新履歴

| 版数 | 日付 | 変更内容 | レビュアー |
|---|---|---|---|
| 1.0 | 2026-04-06 | 初版作成（IPA 準拠性レビュー + 構造品質・整合性チェック + 既存レビュー統合） | Claude |
| 1.1 | 2026-04-06 | DD-REV-101/102/103 対応完了、X5〜X7 相互整合性レビュー実施結果を反映 | Claude |
| 1.2 | 2026-04-07 | 第8章「Phase 0 結果レビューに基づく設計書修正ディスカッション」を追記（論点6.1〜6.5）。bottlenome × Claude の対話形式で論点提示 → 選択肢 pros/cons → ユーザ判断 → 決定の流れを記録 | Claude |

---

## 1. レビュー概要

| 項目 | 内容 |
|---|---|
| **対象ドキュメント** | `docs/detailed_design/` 全11章 + 付録 + README |
| **対象版数** | v0.2（2026-04-04） |
| **レビュー手法** | IPA（情報処理推進機構）プログラム設計書ガイドライン準拠性チェック + 構造品質・整合性レビュー |
| **レビュー日** | 2026-04-06 |
| **上位ドキュメント** | 基本設計書 v0.1、アーキテクチャドキュメント（ACDM）v0.5 |
| **既存レビュー** | `work_instructions/REVIEW_LOG.md`（R1: 単章レビュー2回、R2: 相互整合性レビュー X1〜X4 実施済み） |

---

## 2. IPA 準拠性チェック

IPA のプログラム設計書（詳細設計書）の標準構成に対する適合状況を評価する。

| # | IPA 標準構成要素 | 対応ファイル | 判定 | コメント |
|---|---|---|---|---|
| 1 | **要件一覧・トレーサビリティ** | `01_requirements.md` | ✅ | DD-xxx 10分類・179件。REQ-xxx → DD-xxx トレーサビリティチェーン完備 |
| 2 | **モジュール構成設計** | `02_module_structure.md` | ✅ | Clean Architecture 4層構成、パッケージツリー完全定義、DIP 原則（Protocol層）明示 |
| 3 | **クラス設計（IPO形式）** | `03_class_design.md` | ✅ | DD-CLS-001〜032（32クラス）。IPO形式メソッド定義53箇所。Mermaid classDiagram 11図 |
| 4 | **処理フロー設計** | `04_process_flow.md` | ✅ | DD-SEQ-001〜014。sequenceDiagram 12図 + flowchart。UC-01〜UC-10 対応 |
| 5 | **状態遷移設計** | `05_state_transition.md` | ✅ | DD-STT-001〜003。Orchestrator/Connector/ScenarioPack の状態遷移図。v0.1 から 26→14 状態に削減（設計判断記録あり） |
| 6 | **データ詳細設計** | `06_data_detail.md` | ✅ | ER図、CDL 8エンティティ定義、pack.yaml スキーマ。DD-DAT 系 |
| 7 | **アルゴリズム設計** | `07_algorithm.md` | ✅ | DD-ALG-001〜005。時間同期3方式、メトリクス計算（EN 50160/IEEE 1366）、疑似コード付き |
| 8 | **エラー設計** | `08_error_design.md` | ✅ | E-10xxx〜E-40xxx レイヤー別エラーコード体系。例外クラス階層、設計判断（ADR形式）あり |
| 9 | **設定管理設計** | `09_config_management.md` | ✅ | DD-CFG-001〜004。25設定項目、優先順位ルール、Docker Compose テンプレート |
| 10 | **テスト詳細設計** | `10_test_detail.md` | ✅ | DD-TST-001〜007。UT/IT/E2E/QA テストケース設計、カバレッジ目標（Line 80%、Branch 75%） |
| 11 | **ビルド・デプロイ設計** | `11_build_deploy.md` | ✅ | DD-BLD-001〜002。Dockerfile（マルチステージ）、Docker Compose、CI/CD パイプライン |
| 12 | **付録** | `appendix.md` | ✅ | REQ → DD 完全対応表、用語集 |

**IPA 準拠性の総合判定: 良好（12/12 項目が充足）**

---

## 3. 構造品質レビュー

### 3.1 ドキュメント統計

| 項目 | 数値 |
|---|---|
| 総行数 | 約 7,191 行 |
| 最大ファイル | `03_class_design.md`（64KB、1,811行） |
| Mermaid 図 | 49図 |
| DD-ID 総数 | 179件 |
| IPO 形式メソッド定義 | 53箇所（第3章） |

### 3.2 ドキュメント構成

| # | チェック項目 | 判定 | コメント |
|---|---|---|---|
| S-1 | 全11章 + 付録が揃っているか | ✅ | IPA プログラム設計書標準に準拠。Python/Clean Architecture/Docker 環境に最適化 |
| S-2 | README に目次・読み方・設計方針があるか | ✅ | 8ステップの読み方ガイド、設計方針7項目（IPO形式徹底、章単位独立作成等） |
| S-3 | 全章に更新履歴があるか | ✅ | 全13ファイルに表形式の更新履歴あり |
| S-4 | IPO 形式が適用されているか | ✅ | 第3章で53箇所、第4章・第7章で部分適用。データ定義・設定定義の章はIPO不要で妥当 |
| S-5 | Mermaid 図の種類が適切か | ✅ | classDiagram(15), sequenceDiagram(12), stateDiagram(5), flowchart(12), erDiagram(1), 他(4) |

### 3.3 DD-xxx ID 体系の一貫性

| ID分類 | 件数 | 対応章 | 判定 |
|---|---|---|---|
| DD-MOD-001〜011 | 11件 | 第2章 モジュール構成 | ✅ |
| DD-CLS-001〜032 | 32件 | 第3章 クラス設計 | ✅ |
| DD-SEQ-001〜014 | 14件 | 第4章 処理フロー | ✅ |
| DD-STT-001〜003 | 3件 | 第5章 状態遷移 | ✅ |
| DD-DAT-001〜007 | 7件 | 第6章 データ詳細 | ✅ |
| DD-ALG-001〜005 | 5件 | 第7章 アルゴリズム | ✅ |
| DD-ERR-001〜005 | 5件 | 第8章 エラー設計 | ✅ |
| DD-CFG-001〜004 | 4件 | 第9章 設定管理 | ✅ |
| DD-TST-001〜007 | 7件 | 第10章 テスト詳細 | ✅ |
| DD-BLD-001〜002 | 2件 | 第11章 ビルド・デプロイ | ✅ |

### 3.4 版数推移

| 章 | 最新版 | コメント |
|---|---|---|
| 第3章 | v0.3 | 最多更新。後半追記 + Phase 6 整合性確認 |
| 第8章 | v0.3 | エラー設計の反復改善 |
| 第4〜7章、第10章、付録 | v0.2 | 追記・整合性修正 |
| 第1〜2章、第9章、第11章 | v0.1 | 初版のまま |

---

## 4. 整合性レビュー

### 4.1 上位ドキュメント（基本設計書）との整合性

| # | チェック項目 | 判定 | コメント |
|---|---|---|---|
| C-1 | 全 REQ-B（4件）が DD にマッピングされているか | ✅ | 第1章トレーサビリティで確認 |
| C-2 | 全 REQ-F P0（7件）が DD にマッピングされているか | ✅ | REQ-F-001〜007 → DD-CLS/SEQ/DAT 等に展開 |
| C-3 | REQ-F P1/P2（14件）はスコープ外として明記されているか | ✅ | 第1章で明示 |
| C-4 | 全 REQ-Q（11件）が DD にマッピングされているか | ✅ | テスト設計（DD-TST）で QA-1〜11 対応 |
| C-5 | 全 REQ-C（6件）が DD にマッピングされているか | ✅ | モジュール構成（DD-MOD）、ビルド（DD-BLD）等で対応 |
| C-6 | 基本設計書の Protocol 定義と第3章のクラス設計が一致しているか | ✅ | ConnectorInterface, ScenarioRegistry 等が展開・詳細化 |
| C-7 | トレーサビリティチェーンが完全か | ✅ | 例: REQ-B-001 → REQ-F-001 → FN-001 → DD-CLS-001/002/003 → DD-SEQ-003 → DD-DAT-001 |

### 4.2 章間の整合性（既存レビュー結果の統合）

既存の `REVIEW_LOG.md` での R1（単章レビュー）・R2（相互整合性レビュー）の結果を統合する。

#### R1: 単章レビュー（実施済み・対応済み）

| 回 | 対象 | ERROR | WARNING | 対応状況 |
|---|---|---|---|---|
| 第1回 | ch02, ch03(前半), ch05 | 1件（Mermaid構文） | 13件 | ✅ 修正済み |
| 第2回 | ch04, ch06, ch07, ch10, ch11, 付録 | 2件（REQ-UC-xxx, REQ-010） | 9件 | ✅ 修正済み |

#### R2: 相互整合性レビュー

| ペア | 対象 | 実施状況 | 結果 |
|---|---|---|---|
| X1 | ch03 ↔ ch10（クラス設計 ↔ テスト詳細） | ✅ 実施済み | REVIEW_LOG 参照 |
| X2 | ch03 ↔ ch04（クラス設計 ↔ 処理フロー） | ✅ 実施済み | **課題1**: クラス定義不足（12クラス） |
| X3 | ch03 ↔ ch05（クラス設計 ↔ 状態遷移） | ✅ 実施済み | **課題3**: 状態属性の欠落 |
| X4 | ch03 ↔ ch08（クラス設計 ↔ エラー設計） | ✅ 実施済み | **課題2**: 例外名の体系的不一致 |
| X5 | ch06 ↔ ch03（データ詳細 ↔ クラス設計） | ✅ 実施・対応済み（2026-04-06） | ERROR 10件→**全件対応済み**（DD-REV-201〜207）。WARNING 7件→対応済み |
| X6 | ch07 ↔ ch03（アルゴリズム ↔ クラス設計） | ✅ 実施・対応済み（2026-04-06） | ERROR 8件→**全件対応済み**（DD-REV-301〜308）。WARNING 4件→対応済み |
| X7 | ch09 ↔ ch11（設定管理 ↔ ビルド・デプロイ） | ✅ 実施済み（2026-04-06） | **ERROR 0件**。**WARNING 4件**: ボリュームマウントパス不整合, CI用設定未記載等 |

---

## 5. 指摘事項一覧

### 重要度の定義

| 重要度 | 意味 |
|---|---|
| ❌ ERROR | 整合性の破綻、情報の欠落。修正必須 |
| ⚠️ WARNING | 改善推奨。現時点では致命的ではないが、実装時に問題になる可能性 |
| 💡 INFO | 品質向上のための提案 |

### 5.1 新規指摘

| ID | 重要度 | 対象 | 指摘内容 | 推奨対応 |
|---|---|---|---|---|
| DD-REV-001 | ⚠️ | 全体 | IPA 形式の正式なレビュー記録が独立文書として存在していなかった。REVIEW_LOG.md は簡易ログ形式 | 本文書（review_record.md）の追加で対応済み |
| DD-REV-002 | ✅ 対応済み | R2 | 相互整合性レビュー X5〜X7 を実施完了 | X5: ERROR 10件→対応済み, X6: ERROR 8件→対応済み, X7: ERROR 0件/WARN 4件。詳細は REVIEW_LOG.md 参照 |
| DD-REV-003 | ✅ 対応済み | 第3章 | 03_class_design.md が 64KB・1,811行と非常に大きい | Clean Architecture レイヤー別に4ファイルへ分割済み（03a/03b/03c/03d + Index） |
| DD-REV-004 | 💡 | 第1章 / 第9章 / 第11章 | 第1章・第9章・第11章が v0.1 のまま。R1/R2 レビュー後の修正が反映されていない可能性 | 第9章・第11章は X7 レビュー実施後に更新。第1章は DD-ID の追加・変更があれば更新 |

### 5.2 既存課題の統合（REVIEW_LOG.md からの引継ぎ）

以下は `work_instructions/REVIEW_LOG.md` で既に識別されている課題を、本レビュー記録に正式に統合したものである。

| ID | 重要度 | 出典 | 指摘内容 | 対応方針 | 対応状況 |
|---|---|---|---|---|---|
| DD-REV-101 | ✅ 対応済み | R2-X2 課題1 | **第3章のクラス定義不足**: 第4章シーケンス図に登場するが第3章に未定義のクラスが12件 | CDLRepository(3.4.12), CanonicalData(3.4.11), CLIサブコマンドハンドラー4種(3.7.8), HealthChecker(3.9.6), MigrationRunner(3.9.7) を追加。既存定義済み5件は対応不要と確認 | ✅ **対応完了** |
| DD-REV-102 | ✅ 対応済み | R2-X4 課題2 | **例外名の体系的不一致**: 第3章と第8章の例外名が不一致 | 第3章 3.9.5: 4層構造の例外階層に再構成、全サブクラス明記。第8章 8.1.5: 具象クラスにサブクラス列追加 | ✅ **対応完了** |
| DD-REV-103 | ✅ 対応済み | R2-X3 課題3 | **状態属性の欠落**: 第3章のクラスに state 属性がない | Orchestrator に state: OrchestratorState、ScenarioPack に status: PackStatus を追加 | ✅ **対応完了** |

---

## 6. 総合評価

| 評価観点 | 判定 | コメント |
|---|---|---|
| **IPA 準拠性** | ✅ 良好 | 全12構成要素が充足。IPO形式53箇所、Mermaid図49個と図表が充実 |
| **構造品質** | ✅ 良好 | DD-xxx 179件を10分類で体系管理。全章に更新履歴。設計判断記録あり |
| **上位整合性（基本設計書）** | ✅ 良好 | REQ-xxx → DD-xxx のトレーサビリティチェーンが完全。P1/P2 スコープ外を明示 |
| **章間整合性** | ✅ 良好 | R2 X1〜X7 全ペアでレビュー実施済み。X5 ERROR 10件・X6 ERROR 8件を全件対応完了。X7 は ERROR 0件 |
| **完成度** | ✅ 良好 | 全章が揃い実装可能な粒度。DD-REV-101〜103 対応完了。X5/X6 対応（DD-REV-201〜308）完了。クラス数 32→47 に拡充 |
| **レビュープロセス** | ✅ 良好 | WI-R1/R2 によるレビュー指示書方式、REVIEW_LOG による追跡は優れたプラクティス |

**総合判定: 承認**

### 対応完了した全課題

1. ~~**DD-REV-101**: 第3章への不足クラス追加~~ → ✅ 対応完了
2. ~~**DD-REV-102**: 例外クラス階層の統一~~ → ✅ 対応完了
3. ~~**DD-REV-103**: 状態属性の追加~~ → ✅ 対応完了
4. ~~**DD-REV-002**: X5〜X7 相互整合性レビューの実施~~ → ✅ 実施完了
5. ~~**DD-REV-003**: 第3章ファイル分割~~ → ✅ 対応完了（03a/03b/03c/03d + Index）
6. ~~**X5 ERROR 10件**: CDL属性統一~~ → ✅ DD-REV-201〜207 で全件対応完了
7. ~~**X6 ERROR 8件**: アルゴリズム用クラス追加~~ → ✅ DD-REV-301〜308 で全件対応完了

### 残存課題（WARNING のみ）

- **X7 WARNING 4件**: ボリュームマウントパス不整合、CI設定仕様未記載等。軽微であり実装フェーズで対応可能

---

## 7. 既存 REVIEW_LOG.md との関係

本文書は `work_instructions/REVIEW_LOG.md` を置き換えるものではなく、IPA 形式のレビュー記録として正式化したものである。

| ドキュメント | 役割 |
|---|---|
| `work_instructions/REVIEW_LOG.md` | 作業レベルのレビューログ（R1/R2 の実施記録、未対応課題のトラッキング） |
| `review_record.md`（本文書） | IPA 形式の正式レビュー記録（準拠性チェック、構造品質評価、指摘事項管理、総合判定） |

今後のレビューでは:
- 作業レベルの記録は引き続き `REVIEW_LOG.md` に追記
- 正式なレビュー判定は本文書に版数を上げて追記

---

## 8. Phase 0 結果レビューに基づく設計書修正ディスカッション（2026-04-07）

### 8.0 概要

| 項目 | 内容 |
|---|---|
| **対象** | `docs/phase0_result.md` section 6 で指摘された設計書の不整合・要対応項目（論点6.1〜6.5） |
| **手法** | bottlenome × Claude の対話形式。Claude が問題提示と選択肢の pros/cons を提示し、ユーザが判断する。判断の根拠と思想を記録に残す |
| **進行順** | 6.4 → 6.1 → 6.3 → 6.2 → 6.5（依存関係順） |
| **成果物** | 03a / 03b / 03d / 03e（新規）/ 08 / 02 / development_plan / phase0_result の更新。本記録 |

### 8.1 論点 6.4: StepResult のクラス設計欠落

**問題:** `ExperimentResult.steps: list[StepResult]` が必須属性として宣言されているが、StepResult 自体のクラス設計が設計書のどこにも存在しない（08_error_design.md 8.0.5 で 3 フィールドのみ概要記述）。配置レイヤー、status の型、frozen 化、追加属性すべて未定義。実装者が独自判断する余地が大きく、Phase 1 で実装が割れるリスク。

**サブ論点と決定:**

| サブ論点 | 採択 | 理由 |
|---|---|---|
| (a) 配置レイヤー | **A2 (UseCase 層)** + 解消1 (ExperimentResult ごと UseCase へ移設) | 「実験結果は実行の産物」という意味的整合。Domain → UseCase 依存違反を ExperimentResult 移設で解消。NodeResult 等の Result 型は Domain に残す |
| (b) status の型 | **B3 (enum.Enum: StepStatus)** | 型安全性最強、IDE 補完、誤値防止 |
| (c) data の型 | **C4 (論点6.1 に従う)** → 結果として `tuple[tuple[str, object], ...]` | 6.1 と一貫させる |
| (d) frozen 化 | **D1 (`@dataclass(frozen=True)`)** | 3.4.1 Domain 原則と整合、ハッシュ可能、スレッドセーフ |
| (e) 追加属性 | **E2** (step_id / timestamp / error: GridflowError\|None を追加) | エラー伝搬経路の明示、デバッグ・ログ実用性 |
| (f) 章配置 | **新ファイル `03e_usecase_results.md`** | 「クラスとオーケストレーターを分けるのは自然」というユーザの方針。既存 `03d_infra_classes.md` と衝突しないよう 03e 命名 |

**ユーザ発言抜粋:**
- 「a a2で、依存方向違反はしないように修正してね」
- 「f4かなクラスとオーゲストレーターでわけるのはしぜんだとおもっている」
- 「ファイル数が増えるのは適切な抽象化や構造化ができているということでその間の関係がリンクや概要などで明示されていれば良い方向です」

### 8.2 論点 6.1: `parameters: dict` と frozen 不変原則の矛盾

**問題:** 03a 3.4.1 で「frozen dataclass の内部属性には不変コンテナ tuple を使用」と明記されているのに、Asset / Event / ExperimentMetadata / PackMetadata の `parameters` が `dict` 定義。`@dataclass(frozen=True)` は再代入を禁止するだけで dict 中身書き換えは防げず、ハッシュ可能性も失われる。3.4.1 ルールとの自己矛盾。

**ディスカッションの本質:** 「なぜ不変にしたいのか？」を整理。一般論として (1) 値オブジェクト等価性、(2) ハッシュ可能性、(3) 共有時の安全性、(4) スレッド安全、(5) **再現性**、(6) デバッグ容易性、(7) テスト容易性、(8) 意図表明の 8 つを提示。本プロジェクト（電力系統シミュレーション、研究系ツール）では特に **(5) 再現性** と **(1) 値オブジェクト等価性** が本命と整理した上で判断。

**決定:** **対応案 B (`tuple[tuple[str, object], ...]`)** を採択。

| 評価軸 | A: dict例外 | B: tuple-of-tuples | C: Mapping型ヒント | D: MappingProxy | E: frozendict | F: 自作 |
|---|:---:|:---:|:---:|:---:|:---:|:---:|
| 再現性 | ✗ | ◎ | △ | ○ | ◎ | ◎ |
| ハッシュ可能 | ✗ | ◎ | ✗ | ✗ | ◎ | ◎ |
| 値オブジェクト等価性 | ✗ | ◎ | △ | △ | ◎ | ◎ |
| 外部依存 | なし | なし | なし | なし | あり | なし |

**ユーザ発言抜粋:** 「単に後段の設計ミスだと思います」「不変にしたかった理由ってなんですかね？実際にふへんだからですかね」

**含意:** StepResult.data, ExperimentResult.metrics 等にも同じ方針を適用（論点6.4 (c)）。

### 8.3 論点 6.3: PackNotFoundError のレイヤー配置

**問題:** PackNotFoundError は ScenarioRegistry の `get()`（Infra 層）が送出するが、08 8.1.5 では Domain 層 `ScenarioPackError` 配下に置かれている。「Pack の存在保証は誰の責務か？」が未定義。

**ディスカッションの本質:** 「Domain がエラー契約を持つ」という設計思想を具体例（ScenarioRegistry / UserRepository / InsufficientBalanceError 等）で説明。Domain エラーは「ビジネスルール違反の表明」、Infra エラーは「技術的失敗の表明」という区別が本質。

**決定:** **対応案 D 採択**。Domain 層に `PackNotFoundError` を残しつつ、`ScenarioRegistry` を **Domain Protocol** として `gridflow.domain.scenario.registry` に定義し、`get()` の戻り値仕様で `PackNotFoundError` 送出を契約として明示する。実装は Infra 層（`FileScenarioRegistry`）が Protocol を実装し、契約に従ってエラーを raise する。

**ユーザ発言抜粋:**
- 「ドメインがエラー契約を持つってつまりはどういうことですか？例とか挙げてください」
- 「理解できましたdでいきましょう」

**指針追加:** 08 8.1 冒頭に「Domain ルール違反系は Domain、技術的失敗系は Infra」の使い分け基準を明文化。今後追加される `XxxNotFoundError` 系列の配置判断に使う。

### 8.4 論点 6.2: 03b ファイル名と内容のレイヤー混乱

**問題:** `03b_usecase_classes.md` に Infra 層クラス（Orchestrator / ContainerManager / TimeSync / OrchestratorDriven 等）が混在。02 では `gridflow.infra.orchestrator` に配置されており、ファイル名と内容のレイヤーが不一致。

**決定:** **対応案 B 採択**。Orchestrator 系を既存 `03d_infra_classes.md` の新節 §3.8 へ移設（当初案では新ファイル 03e_infra_orchestrator.md を作る予定だったが、03d_infra_classes.md が既存だったため統合するよう調整）。03b は純粋な UseCase クラスのみに整理。各ファイル冒頭に「本ファイルの責務」と関連ファイルへのリンクを明示。

**TimeSyncStrategy の扱い:** Protocol 自体は UseCase 層 (`gridflow.usecase.interfaces`) に属するが、実装 (OrchestratorDriven 等) は Orchestrator と密結合のため、設計記述としては 03d §3.8.6 に集約。Protocol/実装の依存方向は維持される。

**ユーザ発言抜粋:** 「ファイル数が増えるのは適切な抽象化や構造化ができているということで…良い方向です」

### 8.5 論点 6.5: 開発計画書 1.4 と詳細設計 2.1 のディレクトリ構成不一致

**問題:** development_plan.md 1.4 がフラット構成 (`domain/scenario.py`)、02 2.1 がサブパッケージ構成 (`domain/scenario/scenario_pack.py`) と異なる記述。Phase 0 実装は詳細設計に従っており、計画書だけが古い。

**決定:** **対応案 D 採択**。development_plan.md 1.4 はフラット構成記述を残し、「Phase 0 完了時点でサブパッケージ構成に変更済み。最新は詳細設計 2.1 を参照」と注記を追加。詳細設計 2.1 が Single Source of Truth として機能する。

**ユーザ発言抜粋:** 「dで。開発の結果変わることはよくある。歴史的経緯が重要」

### 8.6 修正ファイル一覧

| # | ファイル | 主な変更 |
|---|---|---|
| 1 | `docs/detailed_design/03a_domain_classes.md` | parameters tuple 化（PackMetadata/Asset/Event/ExperimentMetadata）、3.4.1 補足追記、3.4.13 ExperimentResult を 03e へ移設の通知に置換、ScenarioRegistry を Domain Protocol として再定義、CLS 一覧に StepResult/StepStatus 追加 |
| 2 | `docs/detailed_design/03b_usecase_classes.md` | §3.3 Orchestrator 関連の本文を削除（コメントアウト）し 03d §3.8 への移設通知に置換、§3.5.5 StepResult を 03e へ移設の通知に置換、ファイル冒頭に責務記述追加 |
| 3 | `docs/detailed_design/03d_infra_classes.md` | §3.8 Orchestrator 関連を新設（03b §3.3 からの移設）、ExecutionPlan.parameters を tuple 化 |
| 4 | `docs/detailed_design/03e_usecase_results.md` | **新規作成**。StepStatus / StepResult / ExperimentResult の詳細クラス設計 |
| 5 | `docs/detailed_design/08_error_design.md` | 8.0.5 StepResult を Enum 化＋属性拡張、8.1 冒頭にレイヤー配置指針追記、8.1.5 PackNotFoundError に Domain 契約の説明追記 |
| 6 | `docs/detailed_design/02_module_structure.md` | パッケージ構成図に `domain/scenario/registry.py`, `domain/scenario/errors.py`, `usecase/result.py`, `infra/scenario/file_registry.py` を追加 |
| 7 | `docs/development_plan.md` | 1.4 に Phase 0 完了時点でサブパッケージ構成に変更済みの注記を追加 |
| 8 | `docs/phase0_result.md` | 7.1 チェックリストを完了に更新、7.2 Phase 1 残課題を追加（5.4: ScenarioRegistry Protocol 化、5.5: ExperimentResult 移設） |
| 9 | `docs/detailed_design/review_record.md`（本文書） | 第8章として本記録を追加 |

### 8.7 Phase 1 への持ち越し

設計書修正は完了したが、**Phase 0 で実装済みの Domain クラス群は旧仕様（dict ベース、ExperimentResult が Domain 配置）のまま**である。phase0_result.md 7.2 に追記したとおり、Phase 1 で以下を実装する：

- 5.2: parameters dict → tuple-of-tuples 移行
- 5.3: StepResult / StepStatus / 拡張 ExperimentResult の実装
- 5.4: ScenarioRegistry Protocol 化と FileScenarioRegistry 実装
- 5.5: ExperimentResult を `gridflow.domain.result` → `gridflow.usecase.result` に移設

