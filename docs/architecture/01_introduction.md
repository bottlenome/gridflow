# 1. はじめに

## 1.1 ドキュメントの目的

本ドキュメントは、**gridflow**（Simulation Workflow Engine for Power System Research）のソフトウェアアーキテクチャを記述する。

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
- gridflow のコアアーキテクチャ（Orchestrator、Connector、Canonical Data Layer、Benchmark Harness、CLI/Notebook）
- 計画書で P0（最小必須機能）として定義された機能の設計
- Docker ベースの実行環境とその配置構成

**対象外:**
- P1/P2 機能（record/replay、cache/resume、HIL 連携等）の詳細設計 — 将来の改訂で追加。ただし P0 設計に影響する P1 機能（cache/resume 等）はアーキテクチャ関心事（AC-5）として言及する
- 個別シミュレータ（OpenDSS、GridLAB-D 等）の内部設計
- LLM 連携機能 — 計画書で初期スコープ外と明記
- 収益化モデルの詳細

## 1.4 用語定義

| 用語 | 定義 |
|---|---|
| Scenario Pack | 実験1件をパッケージとして扱う単位。ネットワーク定義、時系列データ、シミュレータ設定、評価指標、seed、expected outputs、可視化テンプレートを含む |
| Orchestrator | 各シミュレータ・解析ツールの統合実行を管理するランタイム。実行順序管理、コンテナ起動、時間同期、バッチ実行、結果収集を担う |
| Connector | 外部シミュレータ（OpenDSS、GridLAB-D、HELICS 等）と gridflow を接続するアダプタ |
| Scenario Registry | Scenario Pack を登録・検索・バージョン管理するストア。Orchestrator への入力元となる |
| Canonical Data Layer (CDL) | ツールごとの独自フォーマットを吸収する共通データ表現。topology、asset、timeseries、event、metric、experiment metadata を含む |
| Benchmark Harness | 実験結果を定量的に評価・比較する採点機構 |
| カスタムレイヤー L1-L4 | 研究者のスキルレベルに応じた拡張段階。L1: 設定変更、L2: Plugin API、L3: モジュール拡張、L4: ソース改変 |
| co-simulation | 複数のシミュレータを連成して同時実行する手法 |
| DER | Distributed Energy Resource（分散型エネルギーリソース）。PV、BESS、EV 等 |
| BESS | Battery Energy Storage System（蓄電池システム） |

## 1.5 参照ドキュメント

| ドキュメント | 場所 | 説明 |
|---|---|---|
| gridflow 計画書 | `docs/gridtwin_lab_plan.md` | プロダクト定義、機能要件、技術アーキテクチャ構想、ロードマップを含むコンセプトドキュメント |
