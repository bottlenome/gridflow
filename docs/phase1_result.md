# Phase 1 実装結果レポート

## 更新履歴

| 版数 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-07 | 初版作成。Phase 1 全スプリント (1〜4) と Phase 0 持ち越し項目 (5.1〜5.8) を実装 | Claude |
| 0.2 | 2026-04-11 | §7 追記: Phase 1 事後監査で発見された設計 ⇔ 実装の乖離 (運用環境方針 / domain 不変性 / Docker HEALTHCHECK / REST connector architecture) を TDD で是正。CLAUDE.md §0.5 追加・詳細設計 03b §3.5.6 深化・ContainerOrchestratorRunner 本実装までを記録 | Claude |

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
