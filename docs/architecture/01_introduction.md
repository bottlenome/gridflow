# 1. はじめに

## 1.1 ドキュメントの目的

本ドキュメントは、**gridflow**（Power System Workflow Engine）のソフトウェアアーキテクチャを記述する。

gridflow は電力系統の研究ワークフローエンジンとして出発するが、アーキテクチャレベルではシミュレータと実系統制御を区別しない。Connector インターフェースの背後にあるものがシミュレータか実機かは、実装の差異であってアーキテクチャの差異ではない。

アーキテクチャ中心設計手法（Architecture Centric Design Method: ACDM）に基づき、以下を目的とする。

- アーキテクチャドライバー（ビジネス目標・品質属性・制約・主要機能）を明確にし、設計判断の根拠を文書化する
- 静的ビュー（構造）と動的ビュー（振る舞い）の両面からシステムを記述し、ステークホルダー間の共通理解を形成する
- 設計判断のトレードオフとリスクを可視化し、将来の改訂・拡張時の判断基盤を提供する

## 1.2 対象読者

| 読者 | 関心事 |
|---|---|
| gridflow 開発者（本人 + AI） | 設計判断の根拠、モジュール間の責務分割、拡張ポイント |
| 将来の contributor | システム全体像の把握、コード変更の影響範囲 |
| 導入検討する研究者 | システムの能力と制約、自身の研究への適合性 |
| 共同研究者 | 連携ポイント（Connector、Plugin API）の理解 |

## 1.3 スコープ

本ドキュメントが対象とする範囲は以下の通り。

**対象:**
- gridflow のコアアーキテクチャ（Orchestrator、Connector、Scenario Registry、Canonical Data Layer、Benchmark Harness、CLI/Notebook）
- 計画書で P0（最小必須機能）として定義された機能の設計
- P1/P2 機能のうち、P0 のアーキテクチャ設計に影響するもの（設計時に考慮すべき拡張ポイントとして）
- Docker ベースの実行環境とその配置構成

**対象（設計考慮のみ・詳細設計は将来）:**
- P1 機能: record/replay、experiment diff、cache/resume、profiling、sensitivity sweep 等 — アーキテクチャ上の拡張ポイントとインターフェースを定義する
- P2 機能: HIL 連携、cyber co-simulation、標準プロトコル対応等 — 将来の統合を阻害しない設計制約として考慮する

**対象外:**
- 個別シミュレータ（OpenDSS、GridLAB-D 等）の内部設計
- 収益化モデルの詳細

## 1.4 用語定義

| 用語 | 定義 |
|---|---|
| Scenario Pack | 実験1件をパッケージとして扱う単位。ネットワーク定義、時系列データ、シミュレータ設定、評価指標、seed、expected outputs、可視化テンプレートを含む |
| Orchestrator | 各シミュレータ・解析ツールの統合実行を管理するランタイム。実行順序管理、コンテナ起動、時間同期、バッチ実行、結果収集を担う |
| Connector | 外部システム（シミュレータ、実機 SCADA、HIL テストベンチ等）と gridflow を接続するアダプタ。アーキテクチャ上、シミュレータと実系統を区別しない |
| Scenario Registry | Scenario Pack を登録・検索・バージョン管理するストア。Orchestrator への入力元となる |
| Canonical Data Layer (CDL) | ツールごとの独自フォーマットを吸収する共通データ表現。topology、asset、timeseries、event、metric、experiment metadata を含む |
| Benchmark Harness | 実験結果を定量的に評価・比較する採点機構 |
| カスタムレイヤー L1-L4 | 研究者のスキルレベルに応じた拡張段階。L1: 設定変更、L2: Plugin API、L3: モジュール拡張、L4: ソース改変 |
| Bounded Context | DDD の概念。明確な境界を持つドメインモデルの適用範囲。gridflow では Orchestrator / Connector / Evaluation / UX 等がそれぞれ Bounded Context を形成する |
| Ubiquitous Language | DDD の概念。ドメインエキスパート（研究者）と開発者が共有する統一語彙。コード上のクラス名・変数名がドメイン用語と一致することを目指す |
| co-simulation | 複数のシミュレータを連成して同時実行する手法 |
| DER | Distributed Energy Resource（分散型エネルギーリソース）。PV、BESS、EV 等 |
| BESS | Battery Energy Storage System（蓄電池システム） |

## 1.5 参照ドキュメント

| ドキュメント | 場所 | 説明 |
|---|---|---|
| gridflow 計画書 | `docs/gridtwin_lab_plan.md` | プロダクト定義、機能要件、技術アーキテクチャ構想、ロードマップを含むコンセプトドキュメント |

## 1.6 計画書からの変更点

アーキテクチャ設計の過程で、計画書（`docs/gridtwin_lab_plan.md`）の記述から意図的に変更・発展させた事項を以下に記録する。計画書も合わせて更新済みである。

| # | 計画書の記述 | 本ドキュメントでの変更 | 変更理由 |
|---|---|---|---|
| 1 | **Simulation Workflow Engine** for Power System Research（1.1） | **Power System Workflow Engine** | AS-4（シミュレータと実系統の非区別）により、アーキテクチャレベルでシミュレーションに限定しない |
| 2 | 研究・**教育**・実験基盤（1.1） | 研究・実験基盤。教育は教員パートナーに委ねる（BG-2, AC-3） | 開発者に教育設計の専門知識がないため。教材化可能な拡張性の確保に留める |
| 3 | 教育用演習が初期主戦場の一つ（2.3） | 共同研究の再現実験基盤が主軸（BG-2） | 研究者として自然に実行できる go-to-market に集中する |
| 4 | course pack / grading がロードマップに含まれる（11） | gridflow のコア責務外（AC-3） | 教育パッケージ化は教員パートナーの裁量に委ねる |
| 5 | 「シミュレーションワークフローエンジン」（13） | 電力系統ワークフローエンジン | #1 と同じ理由 |
| 6 | LLM 連携は「将来的な拡張」で「初期スコープ外」（3.4） | UC-10 としてアーキテクチャ上の契約を定義。P0 での完全実装は含めないが、LLM Agent が操作しやすいインターフェース設計（QA-9）は P0 から組み込む。計画書 3.4 にも反映済み | CON-3（1人+AI 開発）の生産性に直結。AS-4 と同様、設計で将来を阻害しない |
