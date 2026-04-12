# Phase 1 実装結果レポート

## 更新履歴

| 版数 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-07 | 初版作成。Phase 1 全スプリント (1〜4) と Phase 0 持ち越し項目 (5.1〜5.8) を実装 | Claude |
| 0.2 | 2026-04-11 | §7 追記: Phase 1 事後監査で発見された設計 ⇔ 実装の乖離 (運用環境方針 / domain 不変性 / Docker HEALTHCHECK / REST connector architecture) を TDD で是正。CLAUDE.md §0.5 追加・詳細設計 03b §3.5.6 深化・ContainerOrchestratorRunner 本実装までを記録 | Claude |
| 0.3 | 2026-04-11 | §7.11 追記: MVP 研究シナリオ (IEEE 13 × DER 浸透率 sweep, `test/mvp_try1/`) で end-to-end 実証。先行研究課題 C-1 / C-3 / C-7 / C-10 に対する定量的な達成を記録。§7.12 で論文化可能性を正直に評価 | Claude |
| 0.4 | 2026-04-11 | §7.12 を **ユーザー視点 (研究者が gridflow を使って論文を書けるか) で全面 revise**。tool-developer 視点 (SoftwareX 論文) は MVP 検証として不適切だったことを明記。ユーザー視点評価では MVP 未達と判定。§7.13 追記: 是正案として機能 A (sweep) + B (pandapower connector) + C (custom metric plugin) を理想設計で一括実装する方針と、`test/mvp_try2/` での再検証 scenario を定義 | Claude |

---

## 1. 概要

開発計画書 `docs/development_plan.md` Phase 1 (Sprint 1〜4) および
`docs/phase0_result.md` §7.2 の持ち越し項目 8 件をまとめて実装した。

ブランチ: `claude/implement-phase-1-dSET5`

---

## 2. 完了条件達成状況

### 2.1 Phase 0 持ち越し (phase0_result §7.2)

| # | 項目 | 状態 | 実装場所 |
|---|---|:---:|---|
| 5.1 | `ScenarioPack.to_dict()` / `validate()` | ✅ | `domain/scenario/scenario_pack.py` |
| 5.2 | 付帯属性全てを `tuple[tuple[str, object], ...]` に統一 | ✅ | `domain/cdl/*.py`, `domain/scenario/scenario_pack.py` |
| 5.3 | `StepResult` / `StepStatus` | ✅ | `usecase/result.py` |
| 5.4 | `ScenarioRegistry` Domain Protocol | ✅ | `domain/scenario/registry.py` |
| 5.5 | `ExperimentResult` を usecase へ移設 | ✅ | `usecase/result.py` |
| 5.6 | Orchestrator 責務分割 (UseCase / Infra) | ✅ | `usecase/orchestrator.py`, `infra/orchestrator.py` |
| 5.7 | `ScenarioPack` / `PackMetadata` frozen 化 + `with_status()` | ✅ | `domain/scenario/scenario_pack.py` |
| 5.8 | tuple-of-tuples ヘルパー | ✅ | `domain/util/params.py` |

### 2.2 Sprint 1 (コア基盤)

| # | タスク | 状態 | 実装場所 |
|---|---|:---:|---|
| 1-1 | ScenarioRegistry (Domain Protocol + Filesystem 実装) | ✅ | `domain/scenario/registry.py`, `infra/scenario/file_registry.py` |
| 1-2 | ConfigManager (YAML + env + precedence) | ✅ | `infra/config.py` |
| 1-3 | StructuredLogger (structlog, JSON Lines, stderr) | ✅ | `infra/logging.py` |
| 1-4 | GridflowError 階層 (Phase 0 で完了) | ✅ | `domain/error.py` |
| 1-5 | 単体テスト | ✅ | `tests/unit/domain/`, `tests/unit/infra/` |

### 2.3 Sprint 2 (Connector + Orchestrator)

| # | タスク | 状態 | 実装場所 |
|---|---|:---:|---|
| 2-1 | ConnectorInterface Protocol | ✅ | `usecase/interfaces.py` |
| 2-2 | OpenDSSConnector | ✅ | `adapter/connector/opendss.py` |
| 2-3 | OpenDSSTranslator | ✅ | `adapter/connector/opendss_translator.py` |
| 2-4 | Orchestrator (UseCase) + InProcess / Container Runner (Infra) | ✅ | `usecase/orchestrator.py`, `infra/orchestrator.py` |
| 2-5 | 統合テスト | ✅ | `tests/unit/usecase/test_orchestrator.py`, `tests/unit/adapter/test_opendss_connector.py` |

### 2.4 Sprint 3 (CLI + Benchmark)

| # | タスク | 状態 | 実装場所 |
|---|---|:---:|---|
| 3-1 | CLIApp (typer, 4 コマンド + scenario サブコマンド) | ✅ | `adapter/cli/app.py` |
| 3-2 | OutputFormatter (plain / json / table) | ✅ | `adapter/cli/formatter.py` |
| 3-3 | BenchmarkHarness (evaluate / compare) | ✅ | `adapter/benchmark/harness.py` |
| 3-4 | MetricCalculator (voltage_deviation / runtime) | ✅ | `adapter/benchmark/metrics/` |
| 3-5 | ReportGenerator (JSON + text) | ✅ | `adapter/benchmark/report.py` |
| 3-6 | CLI + Benchmark テスト | ✅ | `tests/unit/adapter/` |

### 2.5 Sprint 4 (統合 + 仕上げ)

| # | タスク | 状態 | 実装場所 |
|---|---|:---:|---|
| 4-1 | E2E パス結合 (`gridflow run`) | ✅ | `adapter/cli/app.py:run_command` |
| 4-2 | サンプル Scenario Pack (IEEE13 + minimal_feeder) | ✅ | `examples/ieee13/`, `examples/minimal_feeder/` |
| 4-3 | docker-compose 本番版 + 開発用 overlay | ✅ | `docker-compose.yml`, `docker-compose.dev.yml` |
| 4-4 | README Quick Start | ✅ | `README.md` |
| 4-5 | 再現性検証 E2E テスト (3 回実行) | ✅ | `tests/e2e/test_cli_end_to_end.py::test_reproducibility_three_runs` |
| 4-6 | CI 完成版 (lint → typecheck → test → smoke-opendss → docker-build) | ✅ | `.github/workflows/ci.yml` |

---

## 3. 実装成果物サマリ

### 3.1 LOC

| カテゴリ | LOC |
|---|---:|
| `src/gridflow/` (本体) | 約 2,900 |
| `tests/` (全テスト) | 約 1,580 |
| **合計** | **約 4,480** |

計画書見積 (Phase 1 累計) 7,750 LOC に対し約 58% で必要機能を提供。
差分は Phase 1 スコープを MVP に絞った結果 (pandapower / multi-connector /
plugin API / pack バージョニングは Phase 2 以降)。

### 3.2 テスト

| スイート | 件数 | 状態 |
|---|---:|:---:|
| 単体 (`tests/unit/`) | 121 | ✅ |
| E2E (`tests/e2e/test_cli_end_to_end.py`) | 3 | ✅ |
| OpenDSS smoke (`tests/spike/`, `tests/e2e/test_opendss_e2e.py`) | 4 | spike マーカー (CI 別 job) |
| **合計** | **128** | **124 passing / 4 spike-gated** |

### 3.3 静的解析

- `ruff check`: All checks passed
- `ruff format --check`: clean
- `mypy --strict`: Success (44 source files)

---

## 4. 設計決定ハイライト

### 4.1 Orchestrator 責務分割 (論点 6.6 継続)

UseCase 層の `Orchestrator` はビジネスロジック (pack 取得 → status 遷移 →
ExperimentResult 組み立て) のみを持ち、実行バックエンドは
`OrchestratorRunner` Protocol で抽象化した。Infra 層に以下 2 実装:

- `InProcessOrchestratorRunner` — MVP のデフォルト経路
- `ContainerOrchestratorRunner` — Phase 2 以降の Docker 実行用スタブ
  (現状 `ContainerError` を送出する fail-fast 実装)

これにより UseCase から Docker / subprocess 依存を完全に排除した。

### 4.2 frozen + tuple-of-tuples の全面適用

`CLAUDE.md §0` の「妥協なき設計原則」に従い、**すべての** frozen
dataclass の付帯属性 (`parameters` / `metadata` / `properties`) を
`tuple[tuple[str, object], ...]` に統一した。対象:

- `Asset.parameters`, `Event.parameters`, `ExperimentMetadata.parameters`,
  `PackMetadata.parameters`
- `Topology.metadata`, `TimeSeries.metadata`, `Metric.metadata`
- `Edge.properties`
- `ExperimentResult.metrics` (`dict[str, float]` → `tuple[tuple[str, float], ...]`)

運用ヘルパーは `gridflow.domain.util.params` に集約:
- `as_params(mapping)` — dict/iterable → sorted tuple
- `get_param(params, key, default)` — 線形検索
- `params_to_dict(params)` — 逆変換 (JSON シリアライズ境界用)

### 4.3 ScenarioPack の frozen + `with_status()` API

状態遷移は `pack.status = ...` 直接代入ではなく `pack.with_status(new_status)`
に統一。`FileScenarioRegistry.update_status()` が新インスタンスを生成・
永続化して呼び出し側に返却する契約で実装した。

### 4.4 ログの stdout 分離

CLI コマンドが JSON を出力する際に構造化ログが stdout を汚染すると
JSON パース不能になるため、`configure_logging` はログを **stderr** に
送る設定とした。テスト側は typer `CliRunner` の `.stdout` プロパティで
コマンドペイロードのみを取り出す。

### 4.5 CLI は DI で差し替え可能

`adapter/cli/app.py` の `_default_connector_factory` はモジュール属性で
定義し、テストから `monkeypatch.setattr` で差し替え可能。これにより
CLI E2E テストは OpenDSS 無しで実行できる (`DeterministicFakeConnector`)。

---

## 5. 既知の制約・Phase 2 持ち越し

MVP スコープ外として明示的に見送った項目:

- **REQ-F-006 Plugin API**: L2/L3 のプラグイン機構。L1 (YAML 設定変更) は
  `ConfigManager` + 設定注入で対応可能
- **マルチ connector バッチ実行**: 単一 connector 逐次のみ対応 (`total_steps` ループ)
- **pack バージョニング**: `pack_id = name@version` の単純一意 ID のみ
- **ContainerOrchestratorRunner の実装**: スタブのみ (fail-fast)
- **pandapower / 他 connector**: OpenDSS のみ
- **ExperimentResult の BranchResult / GeneratorResult / RenewableResult 実データ化**:
  Orchestrator は NodeResult のみ集約 (OpenDSSTranslator は Topology 抽出のみ)
- **HybridSync / FederationDriven の時間同期戦略**: lockstep のみ

---

## 6. トレーサビリティ

| 設計書 | Phase 1 対応箇所 |
|---|---|
| `docs/development_plan.md` Sprint 1-4 | 本レポート §2.2〜§2.5 |
| `docs/detailed_design/02_module_structure.md` | `src/gridflow/` 4層構成 |
| `docs/detailed_design/03a_domain_classes.md` | Domain 層全エンティティ |
| `docs/detailed_design/03b_usecase_classes.md` | `Orchestrator`, `ConnectorInterface` |
| `docs/detailed_design/03d_infra_classes.md` | `FileScenarioRegistry`, `InProcessOrchestratorRunner` |
| `docs/detailed_design/03e_usecase_results.md` | `StepResult`, `StepStatus`, `ExperimentResult` |
| `docs/detailed_design/08_error_design.md` | `GridflowError` 階層 |
| `docs/phase0_result.md` §6.1-6.6 (review_record) | 本レポート §4 |

---

## 7. Phase 1 事後監査と設計ドリフト是正 (v0.2)

### 7.1 経緯

`README.md` で「MVP が動いているか確認してほしい」というリクエストを
起点に Phase 1 の実装を実際に動かしながら設計書と突き合わせた結果、
以下 **4 件** の設計 ⇔ 実装乖離が明らかになった。いずれも Phase 1 の
初期コミット (3e09c12) の時点で既に発生していたもので、CI が緑なのは
**乖離しているクラスやモジュール自体を駆動するテストが存在しなかった**
ことによる偽陽性だった (TDD 不徹底)。

| # | 種別 | 乖離内容 | 原因 |
|---|---|---|---|
| A | 運用方針 | README が「Docker は optional」と記述、ローカル uv 実行を第一選択に格上げ | ADR-002 (Docker 標準) 無視 |
| B | Domain 不変性 | `GridflowError.context` が mutable `dict` | CLAUDE.md §0.3「付帯属性全 tuple 化」違反 |
| C | Docker ランタイム | `gridflow-core` Dockerfile の HEALTHCHECK が HTTP ではなく `import gridflow`、ENTRYPOINT が `python -m gridflow`、`main.py` 不在 | 詳細設計 §11.1.1 不遵守 |
| D | REST 連携 | opendss-connector コンテナが CLI shim を起動して即終了。`gridflow.connectors.opendss` モジュール不在。`ContainerOrchestratorRunner` はスタブ。`OrchestratorRunner` Protocol が spec (`connector_id / step / context`) と異なる形 | 詳細設計 §11.1.2 / §3.5.6 / §3.8.2 不遵守 |

### 7.2 事後監査で気付いた TDD の不徹底

TDD が厳密に回っていれば **契約テストが失敗して赤になる** はずの箇所が
以下のとおり無検出のまま残っていた:

- `ContainerOrchestratorRunner.run_connector()` を呼ぶテストが 0 件
  → スタブ実装が error を送出する構造だけで型チェックを通過
- `gridflow.connectors.opendss` モジュールを import するテストが 0 件
  → モジュール不在に気付かない
- Dockerfile の HEALTHCHECK コマンドを実行するテストが 0 件
  → HTTP 検査が実際に通るか無検証
- `OrchestratorRunner` Protocol のシグネチャが spec どおりか固定する
  テストが 0 件 → 型構造の退化を検出できない

**教訓**: 設計書の各契約は「契約テスト」としてコード化するべきで、
実装スタブを置いたら必ず「その契約が成立しているか」を駆動するテストも
同時にコミットする。Phase 2 以降ではこの原則を徹底する。

### 7.3 CLAUDE.md §0.5 追加: 「割り切り禁止」と「聞く前に考える」原則

本修正中、Unit 2 実装計画で筆者 (Claude) が「シングルセッション前提で
割り切ります」と発言し、ユーザーから「それはインターフェース設計の
欠陥を実装で隠そうとしているサイン」「技術判断をプロダクトオーナーに
仰ぐのは実装者の責務放棄」と指摘を受けた。これを受けて CLAUDE.md に
新しい原則を追加した (コミット `b2c266a`):

- **§0.5.1 割り切りはインターフェース設計の欠陥**: 「MVP だから単一
  セッション前提で OK」のような妥協の多くは、RESTful リソース化 /
  引数粒度 / ライフサイクル明示で消せる。実装で覆い隠すのではなく
  インターフェースを直す
- **§0.5.2 プロダクト判断 vs 技術判断の峻別**: スコープ・優先度・UX は
  ユーザーに仰ぐ (プロダクト判断)。インターフェース・層境界・不変条件・
  通信方式は実装者が原則と既存ドキュメントで決める (技術判断)
- **§0.5.3 「聞きたくなった」ときの自問テンプレート**: 設計書の深度
  不足が原因なら設計書を深めてから実装する

この原則を適用した結果、Unit 2 では「1 container = 1 active session」
というセッションモデルを spec 側で明示し、Orchestrator 側が並列実験を
複数コンテナで実現する設計に深化させた。割り切りは自然消滅した。

### 7.4 詳細設計 03b §3.5.6 の深化

Unit 2 実装の前提として、詳細設計 `03b_usecase_classes.md` §3.5.6
「REST API エンドポイント」の契約を大幅に深化させた (コミット `b2c266a`):

| 観点 | 旧仕様 | 新仕様 |
|---|---|---|
| セッションモデル | 未定義 | 1 container = 1 session (並列はコンテナ複製) |
| 状態遷移 | 未定義 | `UNINITIALIZED ↔ READY` + 自動 teardown 規則 |
| `/initialize` の引数 | `{"config": dict}` | `{"pack_id": str}` + shared volume 経由 pack 解決 |
| `/execute` の context | `dict` | `tuple[tuple[str, object], ...]` (CLAUDE.md §0.1 準拠) |
| エラー契約 | 未定義 | `GridflowError.to_dict()` 互換 JSON + HTTP ステータス対応表 |
| セッション衝突 | 未定義 | `409 Conflict` で明示的に拒否 |

新規エラークラス 2 件 (`ConnectorStateError` E-30006 / `ConnectorRequestError` E-30007) を追加。

### 7.5 Unit ごとの実装サマリ (TDD RED → GREEN → REFACTOR)

| Unit | 対象 | 主な変更 | コミット |
|---|---|---|---|
| Preamble | 運用方針 (A) | README を Docker-first に戻し「ローカル uv は開発者限定」と明記 | `7fd3b8d` |
| Preamble | Domain 不変性 (B) | `GridflowError.context: Params` に変更。外部 API は `Mapping \| Iterable[pair] \| None` を受け付け、内部は sorted tuple | `3c2d77a` |
| Preamble | Docker HEALTHCHECK (C) | `gridflow.main` 追加 + `gridflow.infra.health_server` 実装 + Dockerfile/ENTRYPOINT 修正。§11.1.1 純粋解で実装を設計に寄せる | `1d7c211`, `81c1227` |
| **Unit 1** | opendss-connector daemon 最小 | `gridflow.connectors.opendss` モジュール新規。`/health` のみ。Dockerfile / docker-compose を詳細設計 §11.1.2 に合わせて修正 | `f85f0d6` |
| **Unit 2** | opendss-connector 業務エンドポイント | `/initialize` / `/execute` / `/teardown` / 405 method dispatch + 状態機械実装。`_DaemonState` クラスで `threading.Lock` 同期、自動 teardown 規則、`GridflowError.to_dict()` 互換エラー JSON | `bd74b46` |
| **Unit 3a** | UseCase 層の新規型 | `ExecutionPlan`, `StepConfig`, `HealthStatus` dataclass + エラークラス 6 種 (`RunnerStartError` ほか) を追加 (非破壊的) | `c84c862` |
| **Unit 3b+3c** | `OrchestratorRunner` Protocol 破壊的リファクタ | Protocol を spec §3.3.3 シグネチャ (`prepare(plan)` / `run_connector(connector_id, step, context)` / `health_check(id)` / `teardown()`) に統一。`InProcessOrchestratorRunner` を `connector_factories` 注入式に、`Orchestrator.run()` を ExecutionPlan ベースに、CLI `run_command` を追従して書き換え | `378dcd3` |
| **Unit 4** | Container ランナー本実装 | `ContainerManager` Protocol + `DockerComposeContainerManager` (subprocess 注入可能) を `infra/container_manager.py` に新規。`ContainerOrchestratorRunner` は `httpx` で REST を呼ぶ本実装に差し替え (Unit 3 のスタブを廃棄) | `ed7fde4` |
| **Unit 5** | CLI ランナー切替 | `build_runner_from_env()` を CLI に追加。`GRIDFLOW_RUNNER=inprocess\|container` で切り替え、コンテナ運用時は `NoOpContainerManager` を使用 (docker-compose の `depends_on: service_healthy` が既にサービスを起動しているため start/stop は不要)。`docker-compose.yml` に `GRIDFLOW_RUNNER` / `GRIDFLOW_CONNECTOR_ENDPOINTS` を追加 | `0ca249b` |

### 7.6 成果物: 型・エラー・モジュール追加一覧

**新規モジュール:**
- `src/gridflow/main.py` — `python -m gridflow.main` コンテナデーモンエントリ
- `src/gridflow/infra/health_server.py` — gridflow-core の `/health` 用最小 HTTP サーバー
- `src/gridflow/connectors/__init__.py`, `src/gridflow/connectors/opendss.py` — opendss-connector REST デーモン
- `src/gridflow/usecase/execution_plan.py` — `ExecutionPlan`, `StepConfig` dataclass
- `src/gridflow/infra/container_manager.py` — `ContainerManager` Protocol + `DockerComposeContainerManager` + `NoOpContainerManager`

**新規エラークラス (`gridflow/domain/error.py`):**

| クラス | error_code | 親 | 用途 |
|---|---|---|---|
| `ConnectorStateError` | E-30006 | `ConnectorError` | REST 状態不整合 (`/execute` before `/initialize` 等 → 409) |
| `ConnectorRequestError` | E-30007 | `ConnectorError` | REST リクエストボディ不正 (→ 400) |
| `RunnerStartError` | E-40005 | `InfraError` | `OrchestratorRunner.prepare()` 失敗 |
| `ConnectorCommunicationError` | E-40006 | `InfraError` | runner ↔ connector REST 通信失敗 |
| `ConnectorNotFoundError` | E-40007 | `InfraError` | runner に未登録の connector_id |
| `ContainerStartError` | E-40008 | `InfraError` | `ContainerManager.start()` 失敗 |
| `ContainerStopError` | E-40009 | `InfraError` | `ContainerManager.stop()` 失敗 |
| `ServiceNotFoundError` | E-40010 | `InfraError` | `ContainerManager` が Docker サービスを発見できない |

**新規 Protocol / 型 (`gridflow/usecase/interfaces.py`, `gridflow/usecase/execution_plan.py`):**
- `OrchestratorRunner` Protocol を §3.3.3 準拠シグネチャにリファクタ
  (`prepare(plan) / run_connector(id, step, context) / health_check(id) / teardown()`)
- `HealthStatus` frozen dataclass (§3.5.5)
- `ExecutionPlan` frozen dataclass (§3.3.4)
- `StepConfig` frozen dataclass (§3.3.5)

### 7.7 テスト増分

v0.1 時点 128 件 → v0.2 時点 206 件 (**+78 件**)

| テストファイル | 新規件数 | 駆動する契約 |
|---|---:|---|
| `tests/unit/infra/test_health_server.py` | +3 | gridflow-core `/health` + Dockerfile HEALTHCHECK 形式互換 |
| `tests/unit/domain/test_error.py` | +10 | `GridflowError.context` tuple 化 + 新規エラークラス 8 種 |
| `tests/unit/connectors/test_opendss_daemon.py` | +23 | Unit 1+2 の REST 契約全件 (`/health`, `/initialize`, `/execute`, `/teardown`, 405) |
| `tests/unit/usecase/test_execution_plan.py` | +9 | ExecutionPlan / StepConfig / HealthStatus の frozen・hashable・params tuple 不変条件 |
| `tests/unit/usecase/test_orchestrator.py` | 14 (書き換え) | 新 Protocol 下での InProcessRunner + Orchestrator の全契約 |
| `tests/unit/infra/test_container_runner.py` | +10 | `ContainerOrchestratorRunner` のライフサイクル全件 (実 daemon + FakeContainerManager) |
| `tests/unit/infra/test_container_manager.py` | +11 | `DockerComposeContainerManager` subprocess 呼び出し + `NoOpContainerManager` |
| `tests/unit/adapter/test_cli.py` | +5 | `GRIDFLOW_RUNNER` 環境変数による runner 切替 |

### 7.8 Smoke 検証結果

v0.2 時点で以下の実動作を検証済み:

- **InProcess CLI** (従来パス): `gridflow run minimal_feeder@1.0.0 --steps 2` → 正常終了、実 OpenDSS 経路
- **Container CLI** (新パス): `GRIDFLOW_RUNNER=container GRIDFLOW_CONNECTOR_ENDPOINTS=...` の下で同コマンド実行 →
  1. `build_runner_from_env()` が `ContainerOrchestratorRunner` を選択
  2. `ContainerOrchestratorRunner.prepare()` が `POST /initialize` を送信
  3. 各 step で `POST /execute` を送信
  4. `ContainerOrchestratorRunner.teardown()` が `POST /teardown` を送信
  5. exit 0 + `experiment_id` が返る
- 206 tests pass / ruff check clean / ruff format clean

### 7.9 Phase 2 持ち越し項目 (追加)

§5 の既知の制約に加え、v0.2 作業中に以下を将来対応として特定した:

- **`DockerComposeContainerManager` の実利用**: ホスト側スクリプトで
  docker-compose ライフサイクル全体を制御するユースケース。実装済みだが
  CLI 経路では `NoOpContainerManager` を使う (CLI は常にコンテナ内実行
  という前提のため)
- **`gridflow scenario create` コマンド**: `development_plan.md` US-1 の
  受け入れ条件に含まれるが Sprint 3 タスク (4 コマンド) に含まれず、
  MVP スコープの内部不整合として残存。Phase 2 で scaffolding ツールとして
  実装するか、US-1 文言を更新するかの判断が必要
- **`review_record.md` への経緯追記**: 本 §7 の内容を `review_record.md`
  の論点番号付きで正式化する作業

### 7.10 トレーサビリティ (v0.2 追加分)

| 設計書 / ルール | v0.2 対応箇所 |
|---|---|
| `CLAUDE.md §0.5` (v0.2 新設) | §7.3 |
| `docs/detailed_design/03b §3.5.6` (v0.9 深化) | §7.4, `src/gridflow/connectors/opendss.py` |
| `docs/detailed_design/03b §3.3.3` OrchestratorRunner Protocol | §7.5 Unit 3, `src/gridflow/usecase/interfaces.py` |
| `docs/detailed_design/03b §3.3.4` ExecutionPlan | `src/gridflow/usecase/execution_plan.py` |
| `docs/detailed_design/03b §3.5.5` HealthStatus | `src/gridflow/usecase/interfaces.py` |
| `docs/detailed_design/03d §3.8.2` ContainerOrchestratorRunner | §7.5 Unit 4, `src/gridflow/infra/orchestrator.py` |
| `docs/detailed_design/03d §3.8.3` ContainerManager | §7.5 Unit 4, `src/gridflow/infra/container_manager.py` |
| `docs/detailed_design/11_build_deploy.md §11.1.1` | §7.1(C), `docker/gridflow-core/Dockerfile`, `src/gridflow/main.py` |
| `docs/detailed_design/11_build_deploy.md §11.1.2` | §7.5 Unit 1, `docker/opendss-connector/Dockerfile` |
| `docs/detailed_design/11_build_deploy.md §11.2` | `docker-compose.yml` (v0.2 で `GRIDFLOW_RUNNER` 環境変数追加) |

### 7.11 MVP 研究シナリオによる end-to-end 実証 (v0.3)

Phase 1 事後監査 (§7.1〜§7.10) で設計・実装の整合を回復した後、
**gridflow が研究ツールとして先行研究の未解決課題を実際に解決できているか**
を end-to-end で定量検証する段階に移った。

#### 7.11.1 先行研究調査

まず既存 OSS / 査読文献の調査を実施し、2 つの新規文書を作成:

- [`docs/research_landscape.md`](./research_landscape.md): solver / co-sim
  framework / RL env / experiment tracker / HCA tool / open data の
  6 カテゴリで関連ツールを棚卸。2024-2025 の arxiv / ScienceDirect /
  MDPI Energies 等から未解決課題を抽出し **C-1 〜 C-10** として通し番号化
- [`docs/mvp_scenario.md`](./mvp_scenario.md): 上記 landscape から
  gridflow が「✅ 直接対応」できると判定した 4 課題 (C-1 再現性 /
  C-3 プロビナンス / C-7 電力系 tracker 不在 / C-10 指標定義ばらつき)
  を end-to-end で実証する具体シナリオを定義

#### 7.11.2 選定したシナリオ: IEEE 13 × DER 浸透率 sweep

`gridtwin_lab_plan.md` §4 Track 2 (DER hosting capacity) に沿い、
IEEE 13 ノード標準フィーダー上で PV 浸透率を **0% / 25% / 50% / 75% / 100%**
の 5 段階に振り、各パターンを **seed=42 で 3 回実行** (計 15 experiment)
して再現性・プロビナンス・指標定義を一度に検証できるシナリオを選んだ。

- PV 総容量は系統総負荷 3,466 kW に対する比 (均等配置、3 バス 671/675/634)
- PV モデルは `Generator` (定電流、力率 1.0、Model=1) で簡素化
- 指標: `voltage_deviation` (RMSE) + `voltage_violation_ratio`
  (ANSI C84.1 Range A `0.95 ≤ V ≤ 1.05 pu` 基準)

#### 7.11.3 隔離スクラッチ領域の採用

ユーザー指示により **`test/mvp_try1/`** というスクラッチ領域を新設し、
core (`src/gridflow/`) / `examples/` / `tools/` / `tests/` には一切
触らず全成果物を隔離した。`test/` (単数) は pytest の
`testpaths = ["tests"]` 設定外なので自動収集されない。

```
test/mvp_try1/
├── README.md              本スクラッチの目的と再現手順
├── packs/                 5 DSS + 5 pack.yaml + 共通 base DSS
├── tools/                 run_der_sweep.sh, verify_reproducibility.py, plot_hosting_capacity.py
├── results/               15 experiment JSON + benchmark JSON + matplotlib 図
└── report.md              実走結果の正式レポート
```

#### 7.11.4 実走結果

コミット `8ef204f` で一式を投入し、`test/mvp_try1/tools/run_der_sweep.sh`
を実走。全工程 (5 pack 登録 → 15 実験実行 → 再現性検証 → benchmark →
可視化) の wall time は **20.87 秒**。

| DoD 項目 (mvp_scenario.md §6) | 目標 | 実測 | 結果 |
|---|---|---|---|
| 15 実験が exit code 0 で完了 | 15/15 | 15/15 | ✅ |
| 各 pack 内 3 runs が `numpy.array_equal` で一致 | 5/5 | 5/5 | ✅ |
| voltage_deviation が DER 100% < DER 0% | 単調減少 | 0.0545 → 0.0324 (**-40.5%**) | ✅ |
| Sweep wall time | < 600 秒 (10 分) | **20.87 秒** | ✅ (約 30 倍高速) |
| hosting_capacity.png 生成 | 4 パネル図 | ✅ `test/mvp_try1/results/hosting_capacity.png` | ✅ |
| report.md 記録 | 実走結果付き | ✅ `test/mvp_try1/report.md` | ✅ |

詳細: [`test/mvp_try1/report.md`](../test/mvp_try1/report.md) §4〜§7。

#### 7.11.5 物理的な妥当性 (研究結果としての意味)

5 段階の voltage metrics (全 41 バス、full run は `results/der_*_run1.json`):

| DER pct | voltage_deviation | violation_ratio | max_over | min_under |
|---:|---:|---:|---:|---:|
|   0 | 0.054470 | 48.78% | 0.0000 | 0.0446 |
|  25 | 0.048351 | 39.02% | 0.0000 | 0.0365 |
|  50 | 0.042708 | 31.71% | 0.0000 | 0.0290 |
|  75 | 0.037473 | 19.51% | 0.0000 | 0.0218 |
| 100 | 0.032390 | 14.63% | 0.0000 | 0.0150 |

- `max_over = 0` が全レベルで成立 → **均等配置では過電圧が発生しない**
  (PV 出力が下流に分散されるため)
- `min_under > 0` が 100% でも残存 → **標準 IEEE 13 の元々の低電圧問題は
  均等配置 PV 単独では完全解消しない**
- 0% → 100% で violation_ratio が 48.78% → 14.63% に低下。解消率 70%
- この傾向は HCA 文献 [MDPI Energies 2020](https://www.mdpi.com/1996-1073/13/11/2758) の
  定性予測と一致する (uncoordinated PV は電圧問題を緩和するが完全解消には
  配置最適化 / 電圧調整 / 無効電力補助が必要)

#### 7.11.6 gridflow が実証できた「新しい効果」

| 課題 (landscape §2) | 実証手段 | 結果 |
|---|---|---|
| **C-1 再現性危機** | 5 DER レベル × 3 runs で `numpy.array_equal` | **全 bit レベル一致** |
| **C-3 プロビナンス欠落** | 全 experiment JSON に `scenario_pack_id` が埋込、pack 側は `FileScenarioRegistry` で一意参照 | 15 実験すべて事後追跡可能 |
| **C-7 電力系 experiment tracker 不在** | Scenario Pack + ExperimentResult + Benchmark で 15 実験を 1 パイプライン管理 | MLflow/Kedro のような ML 特化層ではなく、Topology/NodeResult 等を 1 級データ型として扱える |
| **C-10 指標定義ばらつき** | `voltage_deviation` (RMSE) / `violation_ratio` (ANSI C84.1 Range A) を `test/mvp_try1/tools/plot_hosting_capacity.py` に Python コードとして commit | 指標の再現可能な定義を git 履歴で追跡可能 |

研究者の Before/After:

| 観点 | 従来 (手作業) | gridflow |
|---|---|---|
| 所要時間 | 半日〜2 日 (5 DSS 書換 + 5 回実行 + Excel 集計 + 図化) | **20.87 秒** |
| 再現性検証 | 通常やらない (意識すらない) | `verify_reproducibility.py` で自動 |
| プロビナンス | ファイル命名規則頼み | `pack_id` で自動管理 |
| 指標定義の再現性 | Excel 式に埋もれる | Python コード commit |

### 7.12 論文化可能性の評価 (v0.3 初版 / v0.4 全面 revise)

> ⚠️ **v0.4 注**: v0.3 で書いた本節は **tool-developer 視点 (gridflow について
> Software tool paper を書けるか) での評価** だった。これは MVP 検証として
> 誤った視点であり、正しい問いは「gridflow を使う **ユーザー (研究者)** が、
> gridflow があるからこそ書ける研究論文を 1 本仕上げられるか」である。
> v0.4 では両方の視点を残しつつ、**ユーザー視点での評価を主軸**とする。

#### 7.12.0 v0.4 で加わった「MVP 検証の正しい問い」

Software tool paper はツール作者 (gridflow 開発者) が書く論文であって、
gridflow を使う研究者が書くものではない。tool paper が通ったとしても、
それは「gridflow というツールが存在する」という announcement であって、
「ツールが研究価値を生む」ことの証拠にはならない。

MVP 検証の正しい問いは:

> **gridflow を使う研究者が、gridflow があるからこそ書ける研究論文を
> 1 本仕上げられるか？**

この問いに対して v0.4 で出した答えは **No** (MVP 未達)。詳細は §7.12.2
参照。

#### 7.12.1 (v0.3 オリジナル — tool-developer 視点、以下 §7.12.1-5 は historical 保持)

本節は v0.3 時点の評価。**後述 §7.12.2 で user 視点評価が主軸に置き換わる**
が、historical 理由で本節は保持する。tool-developer 視点での評価が
それ自体として間違いというわけではなく、それが MVP 検証の軸ではない
という意味である。

##### 7.12.1.1 現時点で「新規性がある」と言える/言えないもの

| 成果 | 研究的新規性 | 判定根拠 |
|---|---|---|
| IEEE 13 × DER sweep で voltage_deviation が減少する | ❌ **なし** | HCA 文献で既知。OpenDSS の物理計算結果そのもの |
| 同一 seed で 3 runs bit 一致 | ❌ **なし** | OpenDSS は決定的なので既知の期待挙動。ソフトウェア工学的には健全な確認だが研究貢献ではない |
| 20.87 秒 で sweep 完了 | ❌ **なし** | ツールの使い勝手の話で「性能」ではない (単一 IEEE 13 で 15 実験の CLI オーバーヘッド計測にすぎない) |
| **Scenario Pack を 1 級データ型として設計、Benchmark Harness で差分管理** | ⚠️ **方法論として新規性あり** | MLflow / Kedro が電力系に未踏。ただし **方法論論文 (methodology paper)** としての新規性で、**発明** ではない |
| **設計書と実装の契約テストによる整合化 (Unit 1-5)** | ❌ **なし** | ソフトウェア工学で既知。ベストプラクティスの適用例 |
| **research_landscape.md の課題分類 C-1〜C-10** | ⚠️ **survey としての価値あり** | 2024-2025 の電力系 ワークフロー領域の未解決課題を一箇所にまとめた資料は少ない。ただし既存 review papers の再整理であり独自調査ではない |

##### 7.12.1.2 現状で**出せる可能性がある**論文タイプと条件

| 論文タイプ | 推定 venue | バー | 現状からの不足分 | 現実性 |
|---|---|---|---|---|
| **(A) Software tool paper** | [SoftwareX](https://www.sciencedirect.com/journal/softwarex), [Journal of Open Research Software](https://openresearchsoftware.metajnl.com/) | 低 (有用な OSS 紹介) | (1) 2-3 個の case study (IEEE 13 + もう 1-2 個)、(2) ドキュメント整備、(3) OSS 公開 + DOI 取得、(4) ベンチマーク結果のアーカイブ | **最短 1-2 ヶ月**、現状の延長で可 |
| **(B) Methodology paper**: "FAIR-compliant Scenario Pack for power systems experiment reproducibility" | [Energy Informatics](https://energyinformatics.springeropen.com/), IEEE Access, [MDPI Energies](https://www.mdpi.com/journal/energies) | 中 (方法論提案 + 実証) | (1) Scenario Pack のフォーマル定義 (スキーマ + hash モデル)、(2) 既存 workflow との定量比較 (所要時間、LOC、再現成功率の計測)、(3) 小規模ユーザースタディ (3-5 人で再現実験)、(4) FAIR 原則との対応表 | **3-6 ヶ月**、本 MVP を土台に拡張 |
| **(C) Application paper**: "Reducing operational overhead of DER hosting capacity studies" | [Electric Power Systems Research](https://www.sciencedirect.com/journal/electric-power-systems-research), [Applied Energy](https://www.sciencedirect.com/journal/applied-energy) | 高 (電力系の実問題解決) | (1) より大規模な fixture (CIGRE MV / 実ユーティリティ)、(2) 実際の運用者との協業 / 導入実績、(3) ケーススタディ 3 件以上、(4) 対照群との RCT | **6-12 ヶ月**、共同研究ないと難しい |
| **(D) Empirical study**: "Reproducibility of open-source power systems simulation results" | 上記同類 + [Reproducibility focus journals](https://journal-buildingscities.org/) | 中 | (1) 複数マシン / 複数 OS / 複数 Python 版での実験、(2) OpenDSS 以外の solver (pandapower, PyPSA) での同実験、(3) bit レベル一致 / 許容誤差 一致の 2 段階評価 | **3-6 ヶ月** |

##### 7.12.1.3 実装者としての推奨 (v0.3 時点)

**短期 (1-2 ヶ月) で投稿できる筋**: **(A) Software tool paper**。

理由:
1. 現状の gridflow が既に動いている (本 Phase 1)
2. `research_landscape.md` がそのまま Related Work 節の下書きになる
3. `test/mvp_try1/` がそのまま Case Study 節の下書きになる
4. 査読で求められる典型要求 (OSS 公開 / ライセンス / ドキュメント /
   テスト / 再現手順) は既に満たしている
5. SoftwareX / JORS は novelty の閾値が「**既存ツールが埋めていない gap**」
   で、本 research_landscape §1.4 がまさにその gap (電力系 native な
   experiment tracker 不在) を指摘している

不足分を埋めるための作業は:

- **追加ケーススタディ 1-2 件**: `test/mvp_try2/` (Track 1 マイクログリッド運用)
  と `test/mvp_try3/` (Track 3 逐次運用 or pandapower vs OpenDSS 比較) を追加
- **スキーマのフォーマル化**: `docs/scenario_pack_schema.md` で pack.yaml の
  JSON Schema を正式定義
- **再現性検証の拡張**: 同一 Docker image で異なるホスト OS (Linux / macOS /
  Windows WSL2) での bit 一致を確認、異なる Python パッチバージョン間の
  許容誤差一致も確認
- **OSS 公開の formalization**: GitHub の public release + DOI (Zenodo)

**中長期 (3-6 ヶ月) に投稿できる筋**: **(B) Methodology paper**。Software tool
paper で出した後、利用実績が溜まったら方法論として再整理する。

##### 7.12.1.4 「出せない」と評価する筋

以下は現状の成果では論文として弱いため、推奨しない:

- 「gridflow が IEEE 13 で DER hosting capacity を計算した」→ 物理は既知、
  solver は OpenDSS そのもの
- 「gridflow で再現性 100% を達成した」→ OpenDSS の決定性が保証しているだけ
- 「gridflow で 20 秒で sweep した」→ ワークフローの話で性能貢献ではない

これらを単体で主張する論文は査読で「既存手法の再実装」と判定される可能性が高い。

##### 7.12.1.5 v0.3 時点の結論 (tool-developer 視点)

**現状で「論文に直結する研究成果」は出ていない**。出ているのは
**論文の素材 (research landscape + working prototype + case study 1 本)** で、
これを **software tool paper (SoftwareX / JORS)** に整形すれば 1-2 ヶ月で
投稿可能、というのが v0.3 時点の評価。新規性の主張軸は「電力系ネイティブな
1 級データ型を扱う experiment tracker の gap を埋める最初の OSS 実装」。

#### 7.12.2 v0.4: user 視点で評価し直し

> **正しい問い**: gridflow を使う研究者が、gridflow があるからこそ書ける
> 研究論文を 1 本仕上げられるか？

**結論: No (MVP 未達)**

##### 7.12.2.1 なぜ user 視点で未達と判定するか

`test/mvp_try1/` で実証した「IEEE 13 × 5 段階 DER sweep」を、研究者の
視点で「論文に書けるか」で吟味すると:

| 主張候補 | 既存研究 | 判定 |
|---|---|---|
| IEEE 13 で DER 浸透率を上げると voltage_deviation が減る | HCA 文献で 1000+ 回示されている | ❌ 新規性ゼロ |
| 同一 seed で 3 runs bit 一致 | OpenDSS の決定性が保証する既知の性質 | ❌ 研究結果ではない |
| gridflow で 20 秒で sweep できた | ツール使用感想であり論文の主張ではない | ❌ |
| 均等配置 PV 100% でも under-voltage が 14.6% 残存 | 既知 (IEEE 13 元々の低電圧問題) | ❌ |

**ユーザーが論文に書くべき新規性が、現状の sweep には何もない**。
IEEE 13 × 5 点均等配置は授業の宿題レベルで、査読に通る論文の題材ではない。

##### 7.12.2.2 ユーザーが本当に書きたい論文と必要機能

電力系研究者が HCA 領域で書ける 2024-2025 年の論文類型と、
gridflow に必要な機能のギャップ:

| 論文類型 | 必要機能 | 現状 gridflow |
|---|---|---|
| Stochastic HCA (IEEE 37 で 500-1000 ランダム配置) | **自動 sweep + 統計 aggregator** | ❌ 手動で 1000 pack を作るしかない |
| Cross-solver validation (OpenDSS vs pandapower) | **pandapower connector** + cross-solver benchmark | ❌ OpenDSS 専用 |
| 新指標提案 (violation_ratio に時間重み付け等) | **プラグイン可能 custom metric** | ❌ core の 2 指標のみ |
| Real feeder case study (CIGRE MV 等) | 大規模 network + 実データ import | ⚠️ 理論上可能、実証なし |
| MC / sensitivity (負荷と PV 出力の不確定性伝搬) | 確率分布からのサンプリング + aggregator | ❌ |

**現状の MVP は上記 5 類型のどれも直接サポートしていない**。
ユーザーは gridflow を使っても現状では「授業の宿題の自動化」しかできず、
研究論文の題材には届かない。

##### 7.12.2.3 MVP 検証としての失敗の意味

`test/mvp_try1/report.md §6.2` で書いた「従来 Before 半日 → After 20 秒」は、
研究者が論文を書くために必要な作業の **ごく一部 (pack を 5 回叩くところ)** を
自動化したに過ぎない。研究者の本業である「**意味のある実験を設計し、結果を
解釈し、新規性を主張する**」作業には到達していない。

v0.3 までの MVP (Phase 1 本体 + `test/mvp_try1/`) は:

- ✅ エンジニアリング reproducibility の実証 → 成立
- ✅ 先行研究課題 C-1 / C-3 / C-7 / C-10 への **対応可能性** の実証 → 成立
- ❌ **ユーザーが論文を書ける機能セット** の実装 → **未達**

したがって **user 視点での MVP 検証は失敗しており、機能追加による是正が必要**。

### 7.13 MVP 是正案 (v0.4): 機能 A + B + C の理想設計一括実装

§7.12.2.3 の未達を埋めるため、以下 3 機能を **理想設計で一括実装** する
(CLAUDE.md §0.1 「妥協せず理想の設計を一度で出す」原則)。**最小実装ではなく、
Phase 1 として正しい終形を一度で作る**。

| # | 機能 | ユーザー論文との対応 |
|---|---|---|
| **A** | `gridflow sweep` — パラメータグリッドからの自動実験展開 + aggregator | Stochastic HCA、sensitivity、MC 系論文 |
| **B** | pandapower connector — cross-solver 対応 | Cross-solver validation 論文 |
| **C** | Custom metric plugin — pack.yaml で Python 実装をロード可能 | 新指標提案論文 |

#### 7.13.1 設計方針 (理想設計、妥協なし)

**A. Sweep (UseCase 層の第一級概念)**

- `gridflow.usecase.sweep_plan.SweepPlan` — frozen dataclass (hashable)
  - `sweep_id`, `base_pack_id`, `axes: tuple[ParamAxis, ...]`, `aggregator_name`, `seed`
- `ParamAxis` (Protocol) + 具体クラス:
  - `RangeAxis(name, start, stop, step)` — 決定論的な等差
  - `ChoiceAxis(name, values)` — 離散選択
  - `RandomSampleAxis(name, low, high, n_samples, seed)` — 確率分布
- `SweepOrchestrator(registry, orchestrator, aggregator_registry)` — UseCase 層
  - `run(plan) -> SweepResult` で子 pack を展開 → 個別 Orchestrator 実行 → 集計
- `SweepResult` — frozen dataclass (hashable)
  - 子 experiment ID 群、集計済み metric、SweepPlan ハッシュを保持
- YAML で SweepPlan を記述 → `gridflow sweep --plan sweep_plan.yaml`
- `Aggregator` Protocol + 具体実装:
  - `StatisticsAggregator` (mean/median/std/quartiles)
  - `ExtremaAggregator` (min/max)
  - Aggregator レジストリで名前引き

**B. pandapower connector (ConnectorInterface の 2 つめの実装)**

- `gridflow.adapter.connector.pandapower.PandaPowerConnector`
- `gridflow.connectors.pandapower` REST デーモン (`gridflow.connectors.opendss` と
  構造的に対称)
- `docker/pandapower-connector/Dockerfile`
- `[project.optional-dependencies] pandapower = [...]`
- **.dss を入力**とし、pandapower の built-in converter (または最小自作ブリッジ)
  で pandapower network に変換。cross-solver 比較は「同じ .dss を両方の solver に
  渡す」形で実現される (現時点では CDL canonical network は Phase 2 範囲、
  これは妥協ではなく「同じ入力ファイルを両 solver に渡すのが cross-solver
  validation の最も忠実な実装」という設計上の選択)
- `docker-compose.yml` に `pandapower-connector` サービス追加

**C. Custom metric plugin (MetricCalculator の動的ロード)**

- `gridflow.adapter.benchmark.metric_registry.MetricRegistry`
- pack.yaml 拡張 (非破壊):
  ```yaml
  metrics:
    - name: voltage_deviation      # 既存
    - name: hosting_capacity_mw    # 新規 (ユーザー定義)
      plugin: "mypkg.mymod:HostingCapacityMetric"
  ```
- `importlib` で動的ロード、`MetricCalculator` Protocol 適合を runtime 検証
- Benchmark Harness + Sweep Aggregator の両方が registry 経由で metric を引く

#### 7.13.2 理想設計の統一ポイント

3 機能を一括で入れる際、**共通の原則**:

1. **frozen domain types**: SweepPlan / SweepResult / ParamAxis / MetricSpec
   すべて frozen dataclass、params tuple 規約 (CLAUDE.md §0.1)
2. **Protocol-based extensibility**: Aggregator / MetricCalculator / ParamAxis は
   すべて Protocol 境界、具体実装は DI 注入
3. **spec-first 層境界**: Domain (types) → UseCase (Sweep/Aggregator Protocol)
   → Adapter (metric plugin / CLI) → Infra (pandapower REST daemon, runner)
4. **既存 Protocol の再利用**: SweepOrchestrator は既存 Orchestrator を内部で
   呼ぶ。OrchestratorRunner Protocol はそのまま (prepare/run_connector/
   health_check/teardown)
5. **TDD 厳密遵守**: 各機能は RED → GREEN → REFACTOR で実装、契約テスト先行

#### 7.13.3 検証シナリオ: `test/mvp_try2/`

`docs/mvp_scenario_v2.md` で正式定義する。概要:

- **scenario v2 名**: "IEEE 13 stochastic HCA with cross-solver validation and
  hosting-capacity metric"
- A (sweep): 500 の random PV 配置で sweep (RandomSampleAxis)
- B (pandapower): 同じ sweep を OpenDSS と pandapower の両方で実行
- C (custom metric): `hosting_capacity_mw` = 95% 配置が Range A を満たす最大 PV MW、
  を pack plugin として実装
- **論文として言える結果**: "IEEE 13 feeder の stochastic hosting capacity は
  pandapower と OpenDSS でどの程度一致するか、および本研究で提案する
  hosting_capacity_mw 指標による定量比較"

これは小さいが legitimate な査読論文の題材であり、gridflow があるからこそ
研究者が 1 日で仕上げられる (手作業では 1-2 週間)。

#### 7.13.4 実装順序

1. `docs/mvp_scenario_v2.md` 新設
2. A-i: Domain types (SweepPlan / ParamAxis / SweepResult / MetricSpec)
3. A-ii: UseCase SweepOrchestrator + Aggregator Protocol + 実装
4. A-iii: CLI `gridflow sweep` + YAML パース
5. C-i: MetricRegistry + importlib 動的ロード
6. C-ii: pack.yaml 拡張、Benchmark Harness から registry 経由で metric 引き
7. B-i: PandaPowerConnector (adapter)
8. B-ii: `gridflow.connectors.pandapower` REST daemon
9. B-iii: Dockerfile + docker-compose 追加 + optional dep
10. test/mvp_try2/ 一式 (sweep_plan.yaml + custom metric Python + ラッパー + report)
11. test/mvp_try2 実走 → evidence 収集 → §7.13.5 に追記

各単位で commit + push。Phase 1 事後監査 (§7.5) と同じ TDD サイクルで進める。
