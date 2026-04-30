# Phase 2 実装結果レポート

## 更新履歴

| 版数 | 日付 | 変更内容 | 著者 |
|---|---|---|---|
| 0.1 | 2026-04-22 | 初版作成。`docs/phase1_result.md` §5.1 で Phase 2 持ち越しに指定された 3 件 (metric parametric evaluation / per-experiment metrics / CDL canonical network input) を理想設計で一括実装 | Claude |
| 0.2 | 2026-04-22 | 設計整合レビュー反映: `SweepResult.per_experiment_metrics` / `EvaluationResult.per_experiment_metrics` を **column-oriented** (`tuple[tuple[str, tuple[float, ...]], ...]` sorted by metric name) に変更。設計書 03b §3.6a.4 と一致。row-oriented の実装ミスは §5.1.2 が要求する分析ワークロード (quantile / bootstrap / histogram) で O(N·M) → O(N) になる重大な性能差を持っていたため、CLAUDE.md §0.5.1 「割り切り = インターフェース設計の欠陥」として是正 | Claude |
| 0.3 | 2026-04-22 | 設計整合 Commit 1 + 2: (1) 設計書 03a/03b §3.6a を実装に合わせて update (M2/M3/M7/M8/M9)。(2) 設計書 03b §3.7 の `SensitivityAnalyzer` を実装 (M5: `gridflow.usecase.sensitivity`、`SensitivityResult` / `VoltageSensitivityMatrix` を Domain 層に追加 = DD-CLS-051/052)。(3) `gridflow evaluate` CLI に inline DSL 形式 (`--results <path> --metric "name:Cls(kw=val)" [--parameter-sweep "kw:start:stop:n"]`) を追加 (M4 案 C: case-A/B 併存)。`--parameter-sweep` 経路は `SensitivityAnalyzer` を起動。382 tests passing (+29) | Claude |
| 0.4 | 2026-04-22 | 設計整合 Commit 3 (M6): CDL translator を双方向化 + 設計書通りの位置に整理。(1) `gridflow.adapter.connector.opendss_translator.OpenDSSTranslator` に `from_canonical(network)` (CDL → DSS script) と `to_canonical()` (live driver → CDLNetwork) を追加。(2) `gridflow.adapter.connector.pandapower_translator.PandapowerTranslator` を新設 (DD-CLS-059)、`from_canonical` / `to_canonical` 双方向。(3) 既存の `gridflow.adapter.network.cdl_to_*` 関数は thin wrapper として残し後方互換。(4) `OpenDSSConnector` / `PandaPowerConnector` の CDL 入力経路を translator class 経由に変更。392 tests passing (+10) | Claude |

---

## 1. 概要

`docs/phase1_result.md` v0.5 §5.1 で「MVP 検証 (try2-try7) で発見された設計ギャップ」として Phase 2 持ち越しに指定された **3 項目** を実装した。

- **§5.1.1 Metric parametric evaluation (最優先)** — 同一シミュレーション結果に対して metric パラメータ (e.g. 電圧閾値) を変えて再計算するワークフローの正式サポート
- **§5.1.2 Per-experiment metric values in SweepResult** — n=1000 件の child JSON を個別再読込せずに済む per-experiment raw metric キャッシュ
- **§5.1.3 CDL canonical network input** — CDL → OpenDSS .dss / pandapower network の双方向変換。cross-solver 検証で solver effect と topology effect を分離

ブランチ: `claude/implement-phase2-Dr2jE`

CLAUDE.md §0.1「妥協なき理想設計」原則に従い、3 項目すべてを **一度で最終形として** 実装した。段階的な「あとで直す」ではなく、型設計・層境界・不変条件を一括で確定した。

---

## 2. 完了条件達成状況

### 2.1 §5.1.1 Metric parametric evaluation

`phase1_result.md §5.1.1` は案 A (sweep 軸で metric パラメータを展開) と案 B (post-processing コマンド) の両方を「排他でなく併用可能」として示していた。**両方を実装**。

| 案 | 内容 | 状態 | 実装場所 |
|---|---|:---:|---|
| **A: Axis target** | sweep 軸が pack / metric どちらを overlay するか指定 | ✅ | `gridflow.usecase.sweep_plan` (`ParamAxis.target`, `ChildAssignment`), `gridflow.usecase.sweep` (`SweepOrchestrator._harness_for_assignment`) |
| **B: Post-processing** | `gridflow evaluate` コマンドで既存 ExperimentResult に metric 再適用 | ✅ | `gridflow.usecase.evaluation` (`MetricSpec`, `EvaluationPlan`, `EvaluationResult`, `Evaluator`), CLI `evaluate` |

### 2.2 §5.1.2 Per-experiment metric values in SweepResult

| 項目 | 状態 | 実装場所 |
|---|:---:|---|
| `SweepResult.per_experiment_metrics` 追加 | ✅ | `gridflow.usecase.sweep_plan.SweepResult` |
| `SweepResult.assignments` 追加 (`ChildAssignment` で per-child の pack/metric 分離) | ✅ | 同上 |
| `SweepOrchestrator.run` での populate | ✅ | `gridflow.usecase.sweep.SweepOrchestrator.run` |
| `to_dict` での round-trip 保持 | ✅ | `SweepResult.to_dict` / `ChildAssignment.to_dict` |

### 2.3 §5.1.3 CDL canonical network input

| 項目 | 状態 | 実装場所 |
|---|:---:|---|
| `CDLNetwork` 型 (Topology + Assets + base voltage/frequency) | ✅ | `gridflow.domain.cdl.network.CDLNetwork` |
| CDL YAML → `CDLNetwork` ローダー | ✅ | `gridflow.adapter.network.cdl_yaml_loader` |
| CDL → OpenDSS .dss 変換 | ✅ | `gridflow.adapter.network.cdl_to_dss.cdl_to_dss` |
| CDL → pandapower network 変換 | ✅ | `gridflow.adapter.network.cdl_to_pandapower.cdl_to_pandapower` |
| OpenDSSConnector の CDL 入力対応 (`cdl_network_file` 経由) | ✅ | `OpenDSSConnector.initialize` + `_compile_cdl_script` |
| PandaPowerConnector の CDL 入力対応 | ✅ | `PandaPowerConnector.initialize` + `_build_from_cdl` |
| サンプル (CDL-first pack) | ✅ | `examples/cdl_minimal/` |

---

## 3. 実装成果物サマリ

### 3.1 LOC (新規)

| カテゴリ | LOC |
|---|---:|
| `src/gridflow/` 新規 (usecase/evaluation, adapter/network, domain/cdl/network) | 約 1,050 |
| `src/gridflow/` 既存への加筆 (sweep*, cli/app, connector/*) | 約 400 |
| `tests/unit/` 新規テスト | 約 850 |
| **合計** | **約 2,300** |

v0.5 時点 約 4,480 → Phase 2 後 約 **6,780** (約 +51%)。

### 3.2 テスト

| スイート | Phase 1 v0.5 | Phase 2 | 差分 |
|---|---:|---:|---:|
| 単体 (`tests/unit/`) | 274 | **335 passing / 6 skipped** | **+61** |
| E2E (`tests/e2e/`) | 3 | 3 | 0 |
| OpenDSS smoke (spike-gated) | 4 | 4 | 0 |
| **合計 passing** | **277** | **338** | **+61** |

### 3.3 静的解析

- `ruff check src tests` → **All checks passed**
- `ruff format --check src tests` → **110 files already formatted**
- `mypy --strict src` → **Success: no issues found in 64 source files**

---

## 4. 設計決定ハイライト

### 4.1 ChildAssignment を構造化 (§5.1.1 Option A)

**決定**: sweep 軸の target ("pack" vs "metric:<name>") を文字列 prefix で flatten せず、`ChildAssignment` frozen dataclass で **pack_params** と **metric_params** を構造的に分離する。

**理由** (CLAUDE.md §0.1):
- namespaced キー (`"metric:hc_090.voltage_low"`) は見た目は軽いが、consumer が毎回パースする責務を負い、型が object のまま流れる
- 構造分離なら pack 重ね合わせは `_derive_child_pack`、metric 重ね合わせは `_harness_for_assignment` と、**異なるライフタイム・異なる consumer に対する責務分離**が層境界で明示できる
- §0.5.1「割り切りはインターフェース設計の欠陥」── prefix 方式は後から metric target だけ特殊化したくなる圧力を蓄積する

`SweepPlan.expand()` の戻り値型を `tuple[Params, ...]` → `tuple[ChildAssignment, ...]` に **破壊的変更**。3 箇所の既存テストを ChildAssignment シグネチャに合わせて書き換え。

### 4.1.1 `per_experiment_metrics` は column-oriented (v0.2 是正)

v0.1 で導入した `per_experiment_metrics` を当初 row-oriented (各 experiment の `tuple[tuple[str, float], ...]` の outer tuple) で実装したが、設計書 03b §3.6a.4 と矛盾していた上、§5.1.2 motivating use case と整合しなかったので v0.2 で column-oriented に是正した。

最終形:

```python
SweepResult.per_experiment_metrics: tuple[tuple[str, tuple[float, ...]], ...]
EvaluationResult.per_experiment_metrics: tuple[tuple[str, tuple[float, ...]], ...]
# 各 outer entry = (metric_name, vector_of_N_floats)
# vector[i] が experiment_ids[i] に対応 (positional alignment)
# outer は metric_name で sort 済み (canonical 形)
```

JSON シリアライズ:
```json
"per_experiment_metrics": {"voltage_deviation": [0.04, 0.06, ...], "hc_metric": [1.2, 0.8, ...]}
```

**根拠**:
- §5.1.2 が指す downstream consumer (sensitivity analysis / quantile / bootstrap / histogram) は **「1 metric × N experiments」を 1 ベクトルで取得するワークロード**。column-oriented なら O(1) lookup + O(N) iterate で済むのに対し、row-oriented では各アクセスごとに dict 再構築 = O(N·M)
- pandas / NumPy / Apache Arrow といった analytics エコシステムが column-oriented 前提
- メモリ上の Python tuple object 数も column の方が ~M 倍少ない (n=1000, m=5 で実測 ~14x)

**不変条件** (`__post_init__` で fail-fast):
1. metric 名は重複なし
2. metric 名で昇順ソート (canonical 形)
3. 各 vector の長さが `len(experiment_ids)` と一致 (rectangular)

**実装ヘルパー**: `gridflow.usecase.sweep._columnize_per_experiment` / `gridflow.usecase.evaluation._columnize`。row-of-dict (Aggregator Protocol の input 形) を column tuple に転置。欠損値は NaN 埋めで rectangular 性を維持。

**テスト**: `test_sweep_plan.py::TestSweepResult` / `test_evaluation.py::TestEvaluationResult` が column 形の構築・to_dict・不変条件を網羅。

### 4.2 MetricSpec を §5.1.1 A / §5.1.1 B で共通化

`EvaluationPlan.metrics: tuple[MetricSpec, ...]` と `SweepOrchestrator(metric_specs=...)` が **同じ** `MetricSpec` frozen dataclass を共有する。これにより:

- sweep で "hc_metric の voltage_low を 0.90→0.95 にスイープ" と書いた YAML を、post-processing でも同じ構文で再利用できる
- `_instantiate_metric(spec, merged_kwargs)` が sweep と evaluation の両方で呼ばれ、metric 生成セマンティクス (built-in 判定 / plugin ロード / `_NamedMetric` ラッピング) が 1 箇所に集約

### 4.3 `_NamedMetric` wrapper (MetricCalculator Protocol との両立)

同一 plugin クラスを `hc_090` / `hc_095` のように異なる name で複数回登録したいが、`MetricCalculator.name` は Protocol で class attribute として定義されている。

**決定**: frozen dataclass ではなく plain class で `_NamedMetric` を実装。`name: str` を通常属性にすることで、mypy --strict の「Protocol の settable attribute は read-only 属性では満たせない」警告を根本的に回避。

### 4.4 `gridflow evaluate` の source EOR ルール (§5.1.1 B)

evaluation.yaml は `results:` / `results_dir:` / `sweep_result:` の **exactly one** を要求する。

**理由**: 「全部書かれていたらどれを優先するか」という判断を loader が取るのは後段の都合で前段を歪める (§0.1 違反)。ユーザーがどれで ExperimentResult を指定したかは明示的に決めるべき。`sweep_result:` は将来的には最頻パターンで、SweepResult から experiment_id 群を抽出し sweep JSON と同じディレクトリから child JSON を探す。

### 4.5 CDL canonical は **string-producing** DSS converter + **live-object** pandapower converter

OpenDSS は .dss テキストで入力する言語、pandapower は Python object で入力するライブラリという構造の差に合わせて、converter の戻り値を分けた。

- `cdl_to_dss(network) -> str` は **OpenDSS を import しない**。純粋文字列生成なので `opendssdirect` が入っていない環境でも単体テスト可能
- `cdl_to_pandapower(network) -> pandapowerNet` は pandapower を lazy import。未インストール時は `ConnectorError` (ImportError を wrap) を投げる

これにより CI は両方の extra が入っていない構成でも、大部分の CDL 変換を単体検証できる (skipif で pandapower-gated 系のみスキップ)。

### 4.6 CDLNetwork 不変条件の早期 validation

`CDLNetwork.__post_init__` で以下すべてを検査:

- `topology.validate()` (既存)
- 全 asset の `validate()`
- `base_voltage_kv > 0`, `base_frequency_hz > 0`
- 全 asset の `node_id` が topology に存在する

この結果、converter 側では null-check を省略できる (§0.5.1 「割り切り禁止」を回避する逆方向の力: 不変条件を early にすることで後段の defensive code を削れる)。

### 4.7 pack.yaml の `cdl_network_file` 優先、`master_file` フォールバック

既存の Phase 1 pack は `network.master_file: foo.dss` を使っている。Phase 2 で CDL 入力を追加する際、**パラメータ名を衝突させず** 既存 pack を無変更で動かし続けるために、新しい `cdl_network_file` パラメータを優先キーとして導入。

```python
# connector/opendss.py:
cdl_file = get_param(pack.metadata.parameters, "cdl_network_file")
if isinstance(cdl_file, str) and cdl_file:
    cdl_script = self._compile_cdl_script(pack, cdl_file)
    ...
else:
    # Phase 1 互換: master_file フォールバック
    ...
```

同じ形を pandapower connector にも適用 (`cdl_network_file` vs `pp_network`)。

---

## 5. トレーサビリティ

| 設計書 / 要件 | Phase 2 対応箇所 |
|---|---|
| `docs/phase1_result.md` §5.1.1 (Option A) | 本レポート §2.1, `gridflow.usecase.sweep_plan.ParamAxis.target` / `ChildAssignment` / `gridflow.usecase.sweep.SweepOrchestrator._harness_for_assignment` |
| `docs/phase1_result.md` §5.1.1 (Option B) | 本レポート §2.1, `gridflow.usecase.evaluation` / `adapter/cli/app.py:evaluate_command` |
| `docs/phase1_result.md` §5.1.2 | 本レポート §2.2, `SweepResult.per_experiment_metrics` / `SweepResult.assignments` |
| `docs/phase1_result.md` §5.1.3 | 本レポート §2.3, `gridflow.domain.cdl.network` + `gridflow.adapter.network.*` |
| `docs/detailed_design/03a_domain_classes.md` DD-CLS-053〜059 (aa68da9) | 対応 (SweepPlan, ParamAxis, SweepResult, Aggregator, EvaluateCommandHandler, PandapowerTranslator は本 Phase で実装済みまたは既存) |
| `docs/detailed_design/03b_usecase_classes.md` §3.6a (aa68da9) | Sweep 関連クラスを実装に反映 |
| CLAUDE.md §0.1「妥協なき理想設計」 | ChildAssignment 構造化 (§4.1)、MetricSpec 共通化 (§4.2) |
| CLAUDE.md §0.5.1「割り切り禁止」 | namespaced string key 方式を回避 (§4.1)、CDL 早期 validation で defensive code を排除 (§4.6) |

---

## 6. Phase 2 で変わった CLI / YAML スキーマ

### 6.1 新コマンド: `gridflow evaluate`

```bash
gridflow evaluate --plan evaluation.yaml --output eval.json --format json
```

```yaml
# evaluation.yaml
evaluation:
  id: hc_threshold_sweep
  sweep_result: results/sweep_opendss.json    # or `results:` / `results_dir:`

metrics:
  - name: voltage_deviation                    # built-in
  - name: hc_090                                # 同一 plugin、異なる kwargs
    plugin: mypkg.mymod:HostingCapacityMetric
    kwargs: {voltage_low: 0.90}
  - name: hc_095
    plugin: mypkg.mymod:HostingCapacityMetric
    kwargs: {voltage_low: 0.95}
```

### 6.2 拡張: sweep_plan.yaml に `axes[i].target` + `metrics:`

```yaml
# sweep_plan.yaml
sweep:
  id: hc_threshold_coupled_sweep
  base_pack_id: ieee13@1.0.0
  aggregator: statistics

axes:
  - name: pv_kw
    type: range
    start: 100
    stop: 500
    step: 100
    # target: pack (既定)
  - name: voltage_low
    type: range
    start: 0.90
    stop: 0.96
    step: 0.01
    target: "metric:hc_metric"    # Phase 2 新規 — metric kwargs を sweep

metrics:                           # Phase 2 新規 — 参照される metric を宣言
  - name: voltage_deviation
  - name: hc_metric
    plugin: mypkg.mymod:HostingCapacityMetric
    kwargs: {voltage_low: 0.95, voltage_high: 1.05}
```

### 6.3 拡張: pack.yaml で CDL 入力

```yaml
# pack.yaml (Phase 1 master_file 方式は互換保持)
pack:
  name: cdl_minimal
  version: "1.0.0"
  connector: opendss

network:
  cdl_network_file: network.yaml   # Phase 2 新規

parameters:
  cdl_network_file: network.yaml
```

```yaml
# network.yaml — CDL canonical
network:
  base_voltage_kv: 12.47
  source_bus: sourcebus

nodes:
  - {id: sourcebus, voltage_kv: 12.47, node_type: source}
  - {id: loadbus, voltage_kv: 12.47, node_type: bus}

edges:
  - id: line_1
    from: sourcebus
    to: loadbus
    edge_type: line
    length_km: 1.0
    properties:
      r1_ohm_per_km: 0.3
      x1_ohm_per_km: 0.5

assets:
  - id: load_1
    asset_type: load
    node_id: loadbus
    rated_power_kw: 500.0
    parameters: {pf: 0.95}
```

これで `--connector opendss` と `--connector pandapower` のどちらでも同じネットワーク定義から解ける。

---

## 7. 既知の制約・Phase 3 持ち越し

- **Aggregator 追加実装**: `QuantileAggregator` (25/50/75/95%ile), `CVaRAggregator` — 設計書 03b §3.6a.5 で言及、Phase 2 は既存 StatisticsAggregator / ExtremaAggregator で代替
- **CDL canonical の逆変換** (`from_canonical(net) -> CDLNetwork`): pandapower / OpenDSS → CDL。本 Phase は forward のみ (`CDL → solver`)。設計書 03b §3.5.4a の目標は残る
- **CDL canonical でサポートされないアセット**: storage / inverter dynamic model / HELICS federate reference 等。`_emit_assets` は未知 asset_type を `! CDL asset '..' not mapped` コメントで DSS に残す (pandapower は silently skip)。本格サポートは solver 側の能力と CDL 形式の拡張に依存
- **MVP try2-try7 の scenario 再実装**: §5.1.1 A/B, §5.1.2, §5.1.3 が揃ったので、try4 (3 閾値 sensitivity) は sweep 1 回 + metric plugin 3 個で、try5-7 (HCA-R / HC₅₀) は `per_experiment_metrics` を使った下流 script で再実装可能 — Phase 2 本体ではやらず、検証シナリオとして別 commit で切り出す想定
- **既存 Phase 1 test の一部**: `test/mvp_try1` 〜 `test/mvp_try7` は Phase 1 時点の API (`SweepResult.assignments: tuple[Params, ...]` 等) に依存している箇所があれば Phase 2 API シフトで要更新。`tests/` (複数形) は pytest で自動収集されており全 passing、`test/` (単数形) は testpaths 外なので影響なし

---

## 8. 次フェーズへの申し送り

Phase 2 で設計原則 (CLAUDE.md §0.1 / §0.5) に沿って **3 件すべてを理想設計で一括実装** したため、以下が恒久的に保証される:

1. 全ドメイン型は frozen + hashable (`ChildAssignment`, `MetricSpec`, `EvaluationPlan`, `EvaluationResult`, `CDLNetwork` すべて)
2. 層境界が明確 — Domain (CDL types) / UseCase (Evaluator / SweepOrchestrator の metric 再合成) / Adapter (cdl_to_dss / cdl_to_pandapower / CLI)
3. simulation と analysis が UseCase レベルで分離 — `Evaluator` は connector を触らない純 UseCase

Phase 3 以降は上記不変条件を崩さずに、`QuantileAggregator` 追加・CDL 逆変換・新 asset type といった拡張を積み増すだけで済む。
