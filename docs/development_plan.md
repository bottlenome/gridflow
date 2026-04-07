# gridflow 開発計画書（Phase 0 / Phase 1）

## 更新履歴

| 版数 | 日付 | 変更内容 | 変更者 |
|---|---|---|---|
| 0.1 | 2026-04-04 | 初版作成 | bottlenome + Claude |
| 0.2 | 2026-04-07 | 1.4 に Phase 0 完了時点でサブパッケージ構成へ変更済みの注記を追加（論点6.5）。詳細設計 2.1 を参照とする | Claude |

---

## 0. PM観点レビュー所見

### 0.1 現状評価

| 項目 | 状態 | 評価 |
|---|---|---|
| アーキテクチャドキュメント | 全8章完成（v0.5） | 十分 |
| 基本設計書 | 全12章完成（v0.1） | 十分 |
| 詳細設計書 | 全11章+付録完成（v0.2） | 十分 |
| 実装コード | **0行** | 未着手 |
| テスト | **0件** | 未着手 |
| CI/CD | **未構築** | 未着手 |

### 0.2 リスク認識

| リスク | 影響 | 対策 |
|---|---|---|
| 設計先行・実装遅延 | 設計と実装の乖離が拡大 | Phase 0で早期にE2Eパスを通す |
| スコープ膨張 | P0全機能を同時に作ろうとして完成しない | MVPを「1本の実験が回る」に絞る |
| OpenDSS接続の技術不確実性 | DSS-Python/py-dss-interfaceのARM64動作未検証 | Phase 0で技術検証を最優先 |
| Docker Compose環境の複雑化 | 初回セットアップ30分目標未達 | 最小構成から開始し、段階的に拡張 |

### 0.3 PM判断: MVP定義

計画書のPhase 0（技術検証）とPhase 1（MVP）を以下の原則で定義する。

**原則:**
1. **最小E2Eパス優先**: 「Scenario Packを作り、OpenDSSで実行し、結果を見る」が1コマンドで回ること
2. **選択肢B（Hybrid absorption）前提**: 外部solverは使い、周辺は自前
3. **ユーザー価値の早期検証**: 研究者が「これ使える」と判断できる最小セット
4. **設計書との整合**: 詳細設計のクラス・モジュール構成に従う（ただしMVP外は後回し）

---

## 1. Phase 0: 開発前準備（1〜2週間）

### 1.1 ゴール

> **開発基盤が整い、OpenDSSで1ステップのパワーフロー計算がPythonから実行できる状態**

### 1.2 完了条件

- [ ] `pyproject.toml` でパッケージ構成が定義され、`pip install -e .` が通る
- [ ] pytest が動作し、空のテストスイートが PASS する
- [ ] CI（GitHub Actions）で lint + test が自動実行される
- [ ] Domain層のコアデータモデル（ScenarioPack, CDLエンティティ）が型定義済み
- [ ] OpenDSS（DSS-Python）がDockerコンテナ内で動作確認済み（ARM64含む）
- [ ] IEEE 13ノードフィーダーでパワーフロー計算が成功するスモークテスト

### 1.3 タスク一覧

| # | タスク | 成果物 | 対応DD | 見積LOC |
|---|---|---|---|---:|
| 0-1 | プロジェクト骨格作成 | `pyproject.toml`, `src/gridflow/__init__.py`, ディレクトリ構成 | DD-MOD-001〜010 | 200 |
| 0-2 | 開発ツール設定 | `ruff.toml`, `mypy.ini`, `.pre-commit-config.yaml` | DD-BLD-003 | 100 |
| 0-3 | CI パイプライン構築 | `.github/workflows/ci.yml` (lint + test + type-check) | DD-BLD-004 | 150 |
| 0-4 | Dockerfile作成 | `Dockerfile` (マルチステージ, AMD64+ARM64) | DD-BLD-001 | 80 |
| 0-5 | Docker Compose最小構成 | `docker-compose.yml` (gridflow + OpenDSS) | DD-BLD-002 | 50 |
| 0-6 | Domain層データモデル | `domain/scenario.py`, `domain/cdl.py`, `domain/error.py` | DD-CLS-001〜006, DD-CLS-025〜029 | 400 |
| 0-7 | OpenDSS技術検証 | `tests/spike/test_opendss_smoke.py` — IEEE 13ノードで潮流計算 | DD-CLS-019 | 200 |
| 0-8 | サンプルScenario Pack | `examples/ieee13/` — pack.yaml + ネットワーク定義 | DD-DAT-001 | 100 |

**合計見積: 約1,300 LOC**

### 1.4 パッケージ構成（Phase 0時点）

> **歴史的経緯（v0.7 注記、論点6.5）:** 本節の構成図は **計画策定時点の見込み** であり、フラットな単一ファイル構成で記載していた。**Phase 0 実装完了時点で、詳細設計 `docs/detailed_design/02_module_structure.md` 2.1 のサブパッケージ構成（`domain/scenario/scenario_pack.py`, `domain/cdl/topology.py` 等）に変更済み**。最新の正確な構成は詳細設計 2.1 を参照のこと。本節は計画段階のスナップショットとして残す。詳細経緯は `docs/detailed_design/review_record.md` 論点6.5 参照。

```
src/gridflow/
├── __init__.py
├── domain/
│   ├── __init__.py
│   ├── scenario.py      # ScenarioPack, PackMetadata
│   ├── cdl.py            # Topology, Node, Edge, Asset, TimeSeries, Event, Metric, ExperimentMetadata
│   └── error.py          # GridflowError 基底例外
├── usecase/
│   └── __init__.py       # 空（Phase 1で実装）
├── adapter/
│   └── __init__.py       # 空（Phase 1で実装）
└── infra/
    └── __init__.py       # 空（Phase 1で実装）
```

### 1.5 技術検証項目

| 項目 | 検証内容 | 判定基準 | 失敗時の代替案 |
|---|---|---|---|
| DSS-Python ARM64 | Apple Silicon Docker内でdss-pythonがimport可能か | `import dss` が成功 | py-dss-interface、またはAMD64エミュレーション |
| DSS-Python パワーフロー | IEEE 13ノードフィーダーの潮流計算 | 収束+ノード電圧取得 | pandapowerをP0コネクタに変更 |
| Docker Compose起動時間 | `docker compose up` の所要時間 | 5分以内 | イメージプリビルド |

---

## 2. Phase 1: MVP作成（3〜4週間）

### 2.1 ゴール

> **研究者が `gridflow run` で実験を実行し、`gridflow benchmark` で結果を評価できる状態**

### 2.2 ユーザーストーリー（MVPスコープ）

| # | ストーリー | 受入条件 | 対応REQ |
|---|---|---|---|
| US-1 | 研究者はScenario Packを作成・登録できる | `gridflow scenario create` → `gridflow scenario register` | REQ-F-001 |
| US-2 | 研究者はOpenDSSシミュレーションを実行できる | `gridflow run <pack_id>` → 結果が保存される | REQ-F-002, REQ-F-007 |
| US-3 | 研究者はCDL形式で結果を参照・エクスポートできる | `gridflow results <exp_id> --format json` | REQ-F-003 |
| US-4 | 研究者は2実験の結果を定量比較できる | `gridflow benchmark --compare exp-001 exp-002` | REQ-F-004 |
| US-5 | 研究者は同一seed・同一packで結果が再現することを確認できる | 3回実行で結果一致 | REQ-B-003, REQ-Q-003 |
| US-6 | 研究者は30分以内にセットアップを完了できる | README手順に従い `docker compose up` → 動作 | REQ-Q-001 |

### 2.3 MVPスコープ判断

| P0機能 | MVP含む？ | 理由 |
|---|---|---|
| REQ-F-001 Scenario Pack + Registry | **含む（最小）** | packの作成・登録・取得。バージョン管理は後回し |
| REQ-F-002 Orchestrator | **含む（最小）** | 単一コネクタの逐次実行。バッチ・並列は後回し |
| REQ-F-003 CDL | **含む（最小）** | Topology, Asset, TimeSeries, Metric。エクスポートはJSON/CSV |
| REQ-F-004 Benchmark | **含む（最小）** | voltage_deviation + runtime の2指標。比較レポート |
| REQ-F-005 CLI | **含む（最小）** | run, scenario, benchmark, results の4コマンド |
| REQ-F-006 Plugin API | **含まない** | MVP後。L1（YAML設定変更）は自然に対応 |
| REQ-F-007 Connectors | **含む（OpenDSSのみ）** | 単一コネクタで十分 |

### 2.4 タスク一覧

#### Sprint 1: コア基盤（1週間）

| # | タスク | 成果物 | 対応DD | 見積LOC |
|---|---|---|---|---:|
| 1-1 | ScenarioRegistry実装 | `infra/registry.py` — register, get, list, validate | DD-CLS-003 | 300 |
| 1-2 | ConfigManager実装 | `infra/config.py` — YAML読込, get/set, 優先順位解決 | DD-CLS-022, DD-CFG-001 | 400 |
| 1-3 | StructuredLogger実装 | `infra/logging.py` — structlog, JSON Lines | DD-CLS-021 | 200 |
| 1-4 | GridflowError階層実装 | `domain/error.py` 拡充 — ConfigError, ConnectorError等 | DD-ERR-001 | 200 |
| 1-5 | テスト: Domain + Infra | 単体テスト 20件 | DD-TST-001 | 500 |

#### Sprint 2: Connector + Orchestrator（1週間）

| # | タスク | 成果物 | 対応DD | 見積LOC |
|---|---|---|---|---:|
| 2-1 | ConnectorInterface定義 | `usecase/interfaces.py` — Protocol定義 | DD-CLS-018, DD-CLS-020 | 100 |
| 2-2 | OpenDSSConnector実装 | `adapter/connector/opendss.py` — initialize, execute, teardown | DD-CLS-019 | 600 |
| 2-3 | OpenDSSTranslator実装 | `adapter/connector/opendss_translator.py` — DSS→CDL変換 | DD-CLS-020 | 400 |
| 2-4 | Orchestrator最小実装 | `infra/orchestrator.py` — 単一コネクタ逐次実行 | DD-CLS-007〜009 | 500 |
| 2-5 | テスト: Connector + Orchestrator | 統合テスト 10件 | DD-TST-002 | 400 |

#### Sprint 3: CLI + Benchmark（1週間）

| # | タスク | 成果物 | 対応DD | 見積LOC |
|---|---|---|---|---:|
| 3-1 | CLIApp実装 | `adapter/cli/app.py` — typer使用, 4コマンド | DD-CLS-010〜012 | 500 |
| 3-2 | OutputFormatter実装 | `adapter/cli/formatter.py` — table/json/plain | DD-CLS-012 | 200 |
| 3-3 | BenchmarkHarness最小実装 | `adapter/benchmark/harness.py` — run, compare | DD-CLS-013 | 300 |
| 3-4 | MetricCalculator 2種 | `adapter/benchmark/metrics/` — voltage_deviation, runtime | DD-CLS-014, DD-ALG-002 | 200 |
| 3-5 | ReportGenerator最小実装 | `adapter/benchmark/report.py` — JSON出力 | DD-CLS-015 | 150 |
| 3-6 | テスト: CLI + Benchmark | E2Eテスト 5件 | DD-TST-003 | 300 |

#### Sprint 4: 統合 + 仕上げ（1週間）

| # | タスク | 成果物 | 対応DD | 見積LOC |
|---|---|---|---|---:|
| 4-1 | E2Eパス結合 | 全コンポーネントを結合し `gridflow run` が通る | DD-SEQ-001 | 300 |
| 4-2 | サンプルScenario Pack 3本 | IEEE 13ノード, IEEE 34ノード, マイクログリッド | DD-DAT-001 | 300 |
| 4-3 | Docker Compose完成版 | 本番用compose, 開発用compose | DD-BLD-002 | 100 |
| 4-4 | README + Quick Start | セットアップ手順, チュートリアル | — | 200 |
| 4-5 | E2Eテスト: 再現性検証 | 同一seed 3回実行で結果一致 | DD-TST-004, REQ-Q-003 | 200 |
| 4-6 | CI 完成版 | lint + test + E2E + Docker build | DD-BLD-004 | 100 |

### 2.5 LOC見積サマリ

| Phase | LOC（プロダクション） | LOC（テスト） | 合計 |
|---|---:|---:|---:|
| Phase 0 | 1,100 | 200 | 1,300 |
| Sprint 1 | 1,100 | 500 | 1,600 |
| Sprint 2 | 1,600 | 400 | 2,000 |
| Sprint 3 | 1,350 | 300 | 1,650 |
| Sprint 4 | 1,000 | 200 | 1,200 |
| **合計** | **6,150** | **1,600** | **7,750** |

計画書の Phase 0（2-4万LOC）より控えめだが、これは意図的。
**理由:** 最初のE2Eパスを素早く通し、そこから肉付けする方が手戻りが少ない。

### 2.6 MVP完了後の検証

| KPI | 目標 | 計測方法 |
|---|---|---|
| セットアップ完了時間 | < 30分 | 別環境で手順を実測 |
| Time to First Simulation | < 1時間 | サンプルpackでの実測 |
| 再現性 | 3回実行で結果一致 | E2Eテスト |
| CLIコマンド数（1実験） | < 5 | コマンド数カウント |

---

## 3. Phase 0 → Phase 1 の移行判定

Phase 0完了後、以下を確認して Phase 1 に進む。

| 判定項目 | 合否基準 |
|---|---|
| OpenDSS技術検証 | Docker内でIEEE 13ノードの潮流計算が成功 |
| ARM64対応 | Apple Silicon環境でDockerビルド+実行が成功（またはエミュレーション許容判断） |
| CI動作 | GitHub ActionsでPASSし、PRマージフローが回る |
| Domain型定義 | ScenarioPack, CDLエンティティの型が確定し、テストがPASS |

**全項目クリアで Phase 1 開始。OpenDSS ARM64 が失敗した場合は pandapower を初期コネクタに切り替え。**

---

## 4. 設計書との対応

| 設計書 | Phase 0 | Phase 1 |
|---|---|---|
| 第1章 要件一覧 | — | REQ-F-001〜005, 007 の最小実装 |
| 第2章 モジュール構成 | ディレクトリ構成 | 全モジュール骨格 |
| 第3章 クラス設計 | Domain層のみ | 全レイヤーの主要クラス |
| 第4章 処理フロー | — | UC-01（シナリオ実行）のE2Eパス |
| 第5章 状態遷移 | — | Orchestrator最小状態遷移 |
| 第6章 データ設計 | CDL型定義 | pack.yaml, CDLエンティティ |
| 第7章 アルゴリズム | — | 時間同期（lockstep最小）, voltage_deviation |
| 第8章 エラー設計 | GridflowError基底 | 例外階層, エラーコード |
| 第9章 設定管理 | — | ConfigManager, gridflow.yaml |
| 第10章 テスト | smokeテスト | 単体+統合+E2E |
| 第11章 ビルド | Dockerfile, CI | Docker Compose, CI完成版 |
