# gridflow アーキテクチャドキュメント作成計画

## 目的

本計画は、gridflow のアーキテクチャドキュメントを**アーキテクチャ中心設計手法（Architecture Centric Design Method）**に基づいて作成するための段階的な進め方を定義する。

---

## ドキュメント全体構成（目次案）

```
1. はじめに
   1.1 ドキュメントの目的
   1.2 対象読者
   1.3 スコープ
   1.4 用語定義

2. アーキテクチャの重要事項
   2.1 アーキテクチャドライバー
       - ビジネスドライバー
       - 技術的制約
       - 品質属性要求（再現性、拡張性、導入容易性、性能）

3. ビュー間の対応の説明
   3.1 静的ビューと動的ビューの対応関係
   3.2 各ビューがカバーする関心事のマッピング

4. 静的ビュー
   4.1 ブロック図（システム全体の構成要素と依存関係）
   4.2 クラス図（主要モジュールの内部構造）
       - Core Runtime
       - Simulator Connectors
       - Data Model (Canonical Data Layer)
       - Evaluation (Benchmark Harness)
       - UX (CLI / Notebook Bridge)
   4.3 配置図（Docker コンテナ・ホスト環境の物理配置）

5. 動的ビュー
   5.1 ユースケース図
       5.1.1 起動・終了
       5.1.2 ログ
       5.1.3 デバッグ
   5.2 ユースケースシナリオ（主要ユースケースのテキスト記述）
   5.3 シーケンス図
       - シミュレーション実行フロー
       - Scenario Pack ロード〜結果出力
       - ベンチマーク評価フロー

付録
   A. 計画書との対応表
   B. 参考文献
```

---

## 作成ステップ

### Step 1: アーキテクチャの重要事項（セクション 1〜2）

**作成内容:**
- はじめに（目的・対象読者・スコープ・用語定義）
- アーキテクチャドライバーの整理
  - ビジネスドライバー: 計画書のセクション 0〜2 から抽出（E2E 研究ループの高速化、教育導入、再現性確保）
  - 技術的制約: セクション 5 から抽出（Python 統一、Docker ベース、マルチアーキテクチャ）
  - 品質属性要求: 計画書全体から横断的に抽出（再現性、拡張性 L1-L4、導入容易性 < 30分、性能）

**情報源:** 計画書セクション 0, 1, 2, 5

**成果物:** `docs/architecture/01_introduction.md`, `docs/architecture/02_architecture_drivers.md`

---

### Step 2: 静的ビュー — ブロック図（セクション 4.1）

**作成内容:**
- システム全体のブロック図（Mermaid）
  - 計画書セクション 5 の flowchart を精緻化
  - サブシステム境界の明確化（Core Runtime / Connectors / Data Model / Evaluation / UX）
  - 外部システムとの境界の明示

**情報源:** 計画書セクション 5, 6

**成果物:** `docs/architecture/04_static_view.md`（ブロック図セクション）

---

### Step 3: 静的ビュー — クラス図（セクション 4.2）

**作成内容:**
- 各サブシステムの主要クラス・インターフェースを Mermaid クラス図で表現
  - Core Runtime: Orchestrator, Scheduler, ExperimentRegistry, ExecutionState
  - Connectors: ConnectorBase（抽象）, OpenDSSConnector, GridLABDConnector, ...
  - Data Model: CanonicalSchema, Topology, Asset, TimeSeries, Event, Metric
  - Evaluation: BenchmarkEngine, MetricLibrary, RegressionChecker
  - UX: CLIInterface, NotebookBridge, ResultComparator
- L1〜L4 カスタムレイヤーの拡張ポイントを図中に明示

**情報源:** 計画書セクション 3, 5, 6

**成果物:** `docs/architecture/04_static_view.md`（クラス図セクション追記）

---

### Step 4: 静的ビュー — 配置図（セクション 4.3）

**作成内容:**
- Docker Compose 構成の配置図（Mermaid）
  - ホスト OS / Docker Desktop / コンテナ群の関係
  - ツール別コンテナ戦略の反映（OpenDSS: pip, GridLAB-D: 専用コンテナ 等）
  - データボリュームの配置
  - ネットワーク構成

**情報源:** 計画書セクション 5.1

**成果物:** `docs/architecture/04_static_view.md`（配置図セクション追記）

---

### Step 5: ビュー間の対応の説明（セクション 3）

**作成内容:**
- 静的ビューのコンポーネントと動的ビューのアクターの対応表
- ブロック図の各ブロックがどのユースケースに関与するかのマッピング
- クラス図の主要クラスとシーケンス図のライフラインの対応

**情報源:** Step 2〜4 の成果物を横断的に参照

**成果物:** `docs/architecture/03_view_mapping.md`

**備考:** 静的ビューと動的ビューの両方が揃ってから記述する方が整合性が取りやすいため、動的ビューの後に最終化する（Step 5 では骨格のみ作成し、Step 8 で完成させる）

---

### Step 6: 動的ビュー — ユースケース図（セクション 5.1）

**作成内容:**
- ユースケース図（Mermaid）
  - アクター: 研究者（L1〜L4）、学生、教員、CI/CD
  - 起動・終了ユースケース: `docker compose up/down`, CLI 初期化、Orchestrator ライフサイクル
  - ログユースケース: 実験ログ出力、実行トレース、メトリクス記録
  - デバッグユースケース: エラーハンドリング、再実行、中間状態検査

**情報源:** 計画書セクション 3, 5

**成果物:** `docs/architecture/05_dynamic_view.md`（ユースケース図セクション）

---

### Step 7: 動的ビュー — ユースケースシナリオ + シーケンス図（セクション 5.2, 5.3）

**作成内容:**
- 主要ユースケースのテキストシナリオ（事前条件・基本フロー・代替フロー・事後条件）
  - シナリオ 1: シミュレーション実行（Scenario Pack → 結果出力）
  - シナリオ 2: ベンチマーク比較評価
  - シナリオ 3: 起動・終了
  - シナリオ 4: エラー発生時のデバッグ
- 各シナリオに対応するシーケンス図（Mermaid）
  - User → CLI → Orchestrator → Connector → Simulator → CDL → Benchmark → Report

**情報源:** 計画書セクション 3, 5, 6

**成果物:** `docs/architecture/05_dynamic_view.md`（シナリオ + シーケンス図セクション追記）

---

### Step 8: 最終統合・ビュー間対応の完成

**作成内容:**
- ビュー間の対応表を最終化（Step 5 の骨格を完成）
- 全セクション間の用語・表記の統一確認
- 付録（計画書との対応表、参考文献）作成
- 目次と相互参照の整理

**成果物:** 全ファイルの最終版、`docs/architecture/README.md`（インデックス）

---

## ファイル構成

```
docs/architecture/
├── README.md                    # インデックス・ナビゲーション
├── 01_introduction.md           # はじめに
├── 02_architecture_drivers.md   # アーキテクチャの重要事項
├── 03_view_mapping.md           # ビュー間の対応の説明
├── 04_static_view.md            # 静的ビュー（ブロック図・クラス図・配置図）
├── 05_dynamic_view.md           # 動的ビュー（ユースケース図・シナリオ・シーケンス図）
└── 06_appendix.md               # 付録
```

---

## 作業の進め方

1. **本計画をレビュー** → 構成・粒度・不足項目を確認
2. **Step 1 から順に作成** → 各ステップ完了後にレビュー可能
3. **Step 5 と Step 8 で横断的な整合性を確保**
4. 図は全て **Mermaid 記法** で記述し、GitHub 上でレンダリング可能にする
5. 言語は **日本語** とする（コード中のクラス名等は英語）

---

## 留意事項

- 現時点では実装コードが存在しないため、クラス図・シーケンス図は計画書の設計意図に基づく**設計時アーキテクチャ**として記述する
- 実装が進んだ段階で、実装との差異を反映する改訂を想定する
- アーキテクチャ中心設計手法に従い、**アーキテクチャドライバーが設計判断を駆動する**構造を維持する
