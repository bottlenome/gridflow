# Phase 0 実装結果レポート

## 更新履歴

| 版数 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-07 | 初版作成 | Claude |
| 0.2 | 2026-04-07 | OpenDSS smoke test 実行検証完了。完了条件 #5/#6 を達成に更新 | Claude |
| 0.3 | 2026-04-07 | 設計書修正レビュー完了。論点6.1〜6.5 をディスカッション形式で確定し、対応する設計書 (03a/03b/03d/03e/08/02/development_plan) を更新。section 7.1 のチェックを完了。詳細議論は `docs/detailed_design/review_record.md` 参照 | Claude |
| 0.4 | 2026-04-07 | 論点6.6 Orchestrator 責務分割を追加。Phase 0 実装 vs 設計書 v0.8 の矛盾チェックを実施し、7.2 に 5.7/5.8 項を追加（ScenarioPack frozen化 / tuple エルゴノミクスヘルパー）。5.2 の対象範囲を parameters のみから metadata/properties を含む全付帯属性に拡張（行番号付き）。詳細議論は `review_record.md` §8.6 参照 | Claude |

---

## 1. 概要

開発計画書 (`docs/development_plan.md`) の Phase 0 タスク (0-1〜0-8) を実装した結果と、実装中に検出した設計書の不整合・要対応項目をまとめる。

ブランチ: `claude/implement-phase-0-HpOyD`

---

## 2. Phase 0 完了条件の達成状況

| # | 完了条件 | 状態 | 備考 |
|---|---|:---:|---|
| 1 | `pyproject.toml` で `pip install -e .` が通る | ✅ | `uv sync` も動作確認済み |
| 2 | pytest が動作し空テストスイートが PASS | ✅ | 58件全PASS（拡充後） |
| 3 | CI で lint + test が自動実行される | ✅ | uv.lock コミット・dependency-groups 修正済み |
| 4 | Domain層コアデータモデルが型定義済み | ✅ | ScenarioPack, CDL全エンティティ, Result型群 |
| 5 | OpenDSS が Docker 内で動作確認済み | ✅ | OpenDSSDirect.py を `[project.optional-dependencies] opendss` に追加。Docker imageは `uv pip install OpenDSSDirect.py` で構築済み |
| 6 | IEEE 13ノードでパワーフロー成功するスモークテスト | ✅ | smoke test 3件 全PASS。電圧 0.8〜1.2 pu 範囲内を確認。CI workflow に `smoke-opendss` job 追加 |

---

## 3. 実装成果物

| タスク | 成果物 | LOC |
|---|---|---:|
| 0-1 | `pyproject.toml`, `src/gridflow/` Clean Architecture 4層 | 約60 |
| 0-2 | ruff/mypy 設定 (pyproject.toml内), `.pre-commit-config.yaml` | 約30 |
| 0-3 | `.github/workflows/ci.yml` (lint→typecheck→test) | 約75 |
| 0-4 | `docker/gridflow-core/Dockerfile`, `docker/opendss-connector/Dockerfile` | 約90 |
| 0-5 | `docker-compose.yml` (2サービス + ネットワーク + ボリューム) | 約45 |
| 0-6 | Domain層: scenario, cdl(8クラス), result(7型), error(階層) | 約700 |
| 0-7 | `tests/spike/test_opendss_smoke.py` | 約70 |
| 0-8 | `examples/ieee13/` (pack.yaml + IEEE13Nodeckt.dss) | 約120 |
| - | テスト 58件 (unit/domain) | 約530 |
| **合計** | | **約1,720** |

検証結果：
- ruff check / format: All passed
- mypy --strict: Success (18 source files)
- pytest: 58 passed
- 開発計画書見積 1,300 LOC に対し実績約 1,720 LOC

---

## 4. レビュー対応済み項目

### 4.1 GridflowError 属性・メソッドの追加 (指摘 2A)

**設計書 8.1.2-8.1.3** で必須の以下を追加：

| 項目 | 内容 |
|---|---|
| `cause: Exception \| None` | 例外チェーン用属性。`__cause__` にも自動セット |
| `to_dict() -> dict` | `error_code`/`message`/`context` の辞書化。ログ・API出力用 |
| `__str__() -> str` | `[{error_code}] {message}` 形式。CLI 出力用 |

### 4.2 エラー階層の親子関係修正 (指摘 2B)

**設計書 8.1.1** のクラス階層図に合わせて修正：

| クラス | 修正前 | 修正後 |
|---|---|---|
| `OrchestratorError` | UseCaseError 子 | **InfraError 子** |
| `PackNotFoundError` | RegistryError 子 (Infra) | **ScenarioPackError 子 (Domain)** |
| `ScenarioPackError` | 未定義 | DomainError 子として追加 |
| `MetricCalculationError` | 未定義 | DomainError 子として追加 |
| `SimulationError` | 未定義 | UseCaseError 子として追加 |
| `BenchmarkError` | 未定義 | UseCaseError 子として追加 |
| `OpenDSSError` | 未定義 | ConnectorError 子として追加 |
| `CLIError` | 未定義 | AdapterError 子として追加 |
| `PluginError` | 未定義 | AdapterError 子として追加 |
| `ContainerError` | 未定義 | InfraError 子として追加 |

### 4.3 Dockerfile EXPOSE 追加 (指摘 2G)

`docker/gridflow-core/Dockerfile` に `EXPOSE 8888` を追加（設計書 11.1.1 準拠）。

### 4.4 CI 修正

| 問題 | 対応 |
|---|---|
| `uv.lock` 未コミット | `uv lock` で生成・コミット |
| `[project.optional-dependencies]` を使用 | `[dependency-groups]` に変更（uv の `--dev` フラグが参照する正しいテーブル） |

---

## 5. Phase 1 へ持ち越す項目

Phase 0 スコープでは対処せず、Phase 1 で対応すべき項目。

### 5.1 ScenarioPack の `to_dict()` / `validate()` (指摘 2D)

**理由：** Phase 1 タスク 1-1 (ScenarioRegistry 実装) で必要となる時点で実装するのが妥当。

### 5.2 frozen dataclass 内の `dict` 使用 (指摘 2E)

Asset, Event, ExperimentMetadata の `parameters: dict` は `frozen=True` の不変原則に反する可能性がある。**ただしこれは設計書自体の矛盾（後述 6.1）であり、設計書側の方針決定が先**。

### 5.3 ExperimentResult の `steps` 属性 / `StepResult` クラス (指摘 2F)

設計書 3.4.13 では `steps: list[StepResult]` が必須属性だが、`StepResult` の詳細クラス設計が未定義（後述 6.4）。Phase 1 で StepResult の設計確定後に実装する。

---

## 6. 設計書の不整合・要対応項目

実装中に検出した設計書側の問題。次回の設計書更新時に対応すべき。

### 6.1 `parameters: dict` と frozen dataclass の不変原則の矛盾

**該当箇所：**
- `docs/detailed_design/03a_domain_classes.md` 3.4.1
- 同 3.4.6 (Asset), 3.4.8 (Event), 3.4.10 (ExperimentMetadata)

**問題：**
3.4.1 では「frozen dataclass の内部属性には不変コンテナ `tuple` を使用する」と明記されているが、Asset/Event/ExperimentMetadata の `parameters` は `dict` で定義されている。`dict` は mutable であり、`frozen=True` の意図（インスタンスのハッシュ可能性・不変性保証）に反する。

**対応案：**
- (A) 3.4.1 に「`parameters: dict` のみ例外として許容する」旨を明記する
- (B) `parameters: tuple[tuple[str, object], ...]` に変更する
- (C) `parameters: Mapping[str, object]` (read-only型ヒント) に変更する

設計書側でいずれかを選択し、実装に反映する必要がある。

### 6.2 03b ファイル名と内容のレイヤー混乱

**該当箇所：** `docs/detailed_design/03b_usecase_classes.md`

**問題：**
ファイル名は `usecase_classes.md` だが、内部に **Infra層クラス** である `Orchestrator`, `ContainerManager`, `TimeSync`, `OrchestratorDriven` 等が含まれる。02_module_structure.md では `gridflow.infra.orchestrator` モジュールとして Infra層に配置されている。

**対応案：**
- (A) ファイル名を `03b_usecase_and_infra_orchestrator.md` 等に変更
- (B) Orchestrator 関連を `03d_infra_classes.md` に移動

### 6.3 PackNotFoundError の Domain/Infra 二重定義疑い

**該当箇所：**
- `docs/detailed_design/08_error_design.md` 8.1.5 Domain層: `ScenarioPackError → PackNotFoundError`
- `docs/development_plan.md` Sprint1 タスク 1-1: ScenarioRegistry の `get()` が `PackNotFoundError` を送出

**問題：**
PackNotFoundError は Registry（Infra層）の操作結果として発生するが、設計書 8.1.5 では Domain層の `ScenarioPackError` 配下に配置されている。「どのレイヤーが Pack の存在を保証する責務を持つか」という設計判断が曖昧。

**対応案：**
- (A) Domain 配置のままとする（Pack 概念の不変条件として「存在すること」を Domain ルールと位置付ける） — 現実装はこの方針
- (B) Infra層 `RegistryError` 系列に移動（Registry の責務とする）

設計書側で配置方針を明文化する必要がある。

### 6.4 StepResult のクラス設計欠落

**該当箇所：**
- `docs/detailed_design/08_error_design.md` 8.0.5: `StepResult` を「戻り値型」として概要のみ言及
- `docs/detailed_design/03a_domain_classes.md` 3.4.13: `ExperimentResult.steps: list[StepResult]` を必須属性として参照

**問題：**
StepResult の詳細クラス設計（属性一覧、メソッド、配置モジュール）が **どの章にも存在しない**。8.0.5 では `status: str ("success"|"warning"|"error"), data: dict, elapsed_ms: float` の3フィールドのみ言及されているが、Domain層に配置するか UseCase層に配置するか、`status` を Enum 型にすべきかなどが未定義。

**対応案：**
- 03a または 03b に StepResult の詳細クラス設計セクションを追加する
- 配置レイヤーを明示する（推奨：UseCase層、または Domain層 result サブパッケージ）

### 6.5 開発計画書と詳細設計書のディレクトリ構成不一致

**該当箇所：**
- `docs/development_plan.md` 1.4: フラット構成 (`domain/scenario.py`, `domain/cdl.py`)
- `docs/detailed_design/02_module_structure.md` 2.1: サブパッケージ構成 (`domain/scenario/scenario_pack.py`, `domain/cdl/topology.py` 等)

**問題：**
開発計画書では `domain/scenario.py` 単一ファイルだが、詳細設計書ではサブパッケージ + 複数ファイル構成。実装は詳細設計に従っており妥当だが、開発計画書側の更新が必要。

**対応案：**
- 開発計画書 1.4 のパッケージ構成図を詳細設計 2.1 と一致させる

---

## 7. 残課題チェックリスト

### 7.1 設計書修正（次回設計書更新時）

- [x] 6.1: `parameters: dict` と frozen 不変原則の矛盾解消 → **対応案 B 採択** (`tuple[tuple[str, object], ...]`)。03a 3.4.1/3.4.6/3.4.8/3.4.10 更新済み
- [x] 6.2: 03b ファイル名／内容のレイヤー整理 → **対応案 B 採択**。Orchestrator 系を 03d §3.8 へ移設、03b は純粋 UseCase に整理
- [x] 6.3: PackNotFoundError のレイヤー配置の明文化 → **対応案 D 採択**。Domain 配置維持＋ScenarioRegistry を Domain Protocol 化、エラー契約を 8.1 冒頭で明文化
- [x] 6.4: StepResult の詳細クラス設計追加 → **新ファイル 03e_usecase_results.md 作成**。UseCase 層配置、StepStatus enum、frozen、属性拡張 (step_id/timestamp/error)、ExperimentResult も同所に移設
- [x] 6.5: 開発計画書 1.4 のディレクトリ構成を詳細設計に合わせて更新 → **対応案 D 採択**。歴史的経緯保持のため注記追加で対応

### 7.2 Phase 1 での実装対応

- [ ] 5.1: ScenarioPack の `to_dict()` / `validate()` 実装
- [ ] 5.2: frozen dataclass の付帯属性を **すべて** `tuple[tuple[str, object], ...]` に修正（論点6.1 拡張）。対象属性・ファイル・行番号は以下：
  - `parameters` 系:
    - `src/gridflow/domain/cdl/asset.py:28` Asset.parameters
    - `src/gridflow/domain/cdl/event.py:31` Event.parameters
    - `src/gridflow/domain/cdl/experiment_metadata.py:29` ExperimentMetadata.parameters
    - `src/gridflow/domain/scenario/scenario_pack.py:43` PackMetadata.parameters
  - `metadata` / `properties` 系（CLAUDE.md §0 妥協なき原則に従い v0.x で追加）:
    - Topology.metadata / TimeSeries.metadata / Metric.metadata / Edge.properties 該当箇所すべて
  - `ExperimentResult.metrics: dict[str, float]` → `tuple[tuple[str, MetricValue], ...]` （5.5 と同時対応）
  - テストの assertion も書き換え: `asset.parameters["key"]` → `dict(asset.parameters)["key"]` または `get_param()` ヘルパー経由
- [ ] 5.3: StepResult クラスと ExperimentResult.steps 属性の実装（論点6.4: 03e_usecase_results.md 準拠。`gridflow.usecase.result` モジュール新設、StepStatus enum、step_id/timestamp/error 属性含む）
- [ ] 5.4: ScenarioRegistry を Domain Protocol として `gridflow.domain.scenario.registry` に新設し、Infra 実装 (`FileScenarioRegistry`) を `gridflow.infra.scenario.file_registry` に配置する（論点6.3）
- [ ] 5.5: ExperimentResult を `gridflow.domain.result` から `gridflow.usecase.result` に移設する（論点6.4）。既存 `src/gridflow/domain/result/results.py:140` の ExperimentResult クラスを削除し、`usecase/result.py` に frozen=True で再定義。import パスの全置換が必要（テスト含む）
- [ ] 5.6: Orchestrator を責務分割（論点6.6）。`gridflow.usecase.orchestrator.Orchestrator` (ビジネスロジック) と `gridflow.infra.orchestrator.ContainerOrchestratorRunner` (Docker 実装) に分け、`OrchestratorRunner` Protocol を境界とする。OrchestratorDriven/HybridSync は UseCase 層に、FederationDriven は Infra 層に配置。**Phase 0 で Orchestrator は未実装のため新設作業のみ（既存コードを壊す作業はない）**
- [ ] 5.7: **ScenarioPack / PackMetadata の frozen 化**（論点6.2）
  - 対象: `src/gridflow/domain/scenario/scenario_pack.py:21` PackMetadata, `:46` ScenarioPack
  - `@dataclass` → `@dataclass(frozen=True)` に変更
  - **状態遷移との整合が最大の論点**: ScenarioPack は `status: PackStatus` を持ち Draft → Validated → Registered → Running → Completed の状態遷移（05_state_transition.md）がある。frozen 後は `pack.status = ...` 直接代入が不可になるため、状態更新はすべて `dataclasses.replace(pack, status=...)` で **新インスタンス生成**する方式に統一する
  - 呼び出し側（Registry / UseCase）が古い参照を持ち続けないよう、更新後のインスタンスを呼び出し側に返却する API 規約を決める（推奨: `ScenarioRegistry.update_status(pack_id, new_status) -> ScenarioPack` を追加）
  - テスト側の `pack.status = ...` 直接代入があれば `replace()` ベースに書き換え
- [ ] 5.8: **tuple-of-tuples エルゴノミクス対策**（論点6.1 運用ヘルパー）
  - `tuple[tuple[str, object], ...]` は直接アクセスが不便（`asset.parameters["kW"]` が書けない）ため、運用ヘルパーを早期に整備する
  - 配置候補: `src/gridflow/domain/util/params.py`（新設）
  - 提供関数:
    - `as_params(mapping: Mapping[str, object]) -> tuple[tuple[str, object], ...]`：dict 入力を tuple-of-tuples に変換
    - `get_param(params: tuple[tuple[str, object], ...], key: str, default: object = None) -> object`：キー取得
    - `params_to_dict(params: tuple[tuple[str, object], ...]) -> dict[str, object]`：dict 復元
  - テスト・呼び出しコードは極力このヘルパー経由にし、`dict(self.parameters)` の散在を防ぐ
  - **方針決定の論点**: computed property (`@property def params_dict(self)`) 方式にするか関数ヘルパー方式にするか。`@property` はハッシュ等価性には影響しないが、frozen dataclass では `__post_init__` で書き込めないためキャッシュ困難。関数ヘルパーで統一を推奨

---

## 8. トレーサビリティ

| 設計書 | Phase 0 対応箇所 |
|---|---|
| `docs/development_plan.md` 1.3 (タスク一覧) | 全タスク 0-1〜0-8 |
| `docs/detailed_design/02_module_structure.md` 2.1 | `src/gridflow/` ディレクトリ構成 |
| `docs/detailed_design/03a_domain_classes.md` 3.2-3.4 | Domain層クラス全実装 |
| `docs/detailed_design/08_error_design.md` 8.1 | GridflowError 階層（4.1, 4.2 で修正） |
| `docs/detailed_design/11_build_deploy.md` 11.1 | Dockerfile（4.3 で修正） |
| `docs/detailed_design/11_build_deploy.md` 11.2 | docker-compose.yml |
| `docs/detailed_design/11_build_deploy.md` 11.3 | CI workflow |
| `docs/detailed_design/11_build_deploy.md` 11.4 | pyproject.toml |
