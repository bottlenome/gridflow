# try8 — Phase 2 v0.4 MVP 検証結果

実施日: 2026-04-28
ブランチ: `claude/implement-phase2-Dr2jE` (`9cd8dab` 以降)

## 1. 目的

Phase 2 v0.3 で実装した 4 機能 + M5 (`SensitivityAnalyzer`) が、研究ワークフロー上で end-to-end に動作することを実証する。

## 2. シナリオ

4 バス放射状フィーダー (`packs/feeder.yaml`):
```
sourcebus → bus1 → bus2 → bus3
            ↓load   ↓load    ↓load
            200 kW  300 kW  400 kW   (pf=0.95)
```
PV を `bus1` に注入。`pv_kw` を 0/200/400/600 kW で sweep。

## 3. 実行結果 (`results/summary.json` 引用)

総実行時間: **1.18 秒** (Section 1〜3 合計)。

### Section 1 — §5.1.3 CDL canonical input + Translator 双方向

| 検証項目 | 結果 |
|---|---|
| CDL → OpenDSS .dss script 生成 (`OpenDSSTranslator.from_canonical`) | ✅ 663 chars 出力、`Clear` → `New Circuit` → `New Linecode` → `New Line` → `Calcv` の正規構造 |
| CDL → pandapower (`PandapowerTranslator.from_canonical`) → solve | ✅ 収束、voltages = [1.000, 0.9973, 0.9952, 0.9940] pu |
| pandapower → CDL → pandapower 往復 (`PandapowerTranslator.to_canonical`) | ✅ **round-trip max voltage drift = 0.0 pu** (bit 一致) |

Translator 双方向化 (M6) が canonical を中間表現として正しく機能している。OpenDSS ドライバはこの環境では未インストールのため pandapower 経路のみで実証。

### Section 2 — §5.1.1 Option A + §5.1.2 column per_experiment_metrics

| 検証項目 | 結果 |
|---|---|
| `gridflow.usecase.sweep.SweepOrchestrator.run` 経由 | ✅ 4 children in 0.76 s |
| `SweepResult.per_experiment_metrics` の column 形 | ✅ `metric_columns = ["runtime", "voltage_deviation"]` (sorted) |
| 各 metric の vector 長 = `len(experiment_ids)` | ✅ 4 = 4 |
| voltage_deviation が PV 増加で単調減少 (物理整合性) | ✅ 0.0041 → 0.0031 (PV 0→600 kW で −24%) |

`per_experiment_metrics` を 1 行 (`dict(result.per_experiment_metrics)["voltage_deviation"]`) で取り出せる column 形が、設計書 03b §3.6a.4 と実装で一致していることを確認。

### Section 3a — §5.1.1 Option B `gridflow evaluate` (YAML / inline 共通の Evaluator UseCase)

| 検証項目 | 結果 |
|---|---|
| 同一 plugin × 2 つの kwargs 並列評価 | ✅ `frac_below_095` + `frac_below_098` の 2 column が同 plan で共存 |
| EvaluationResult の column 形 | ✅ 同上 |
| 物理的妥当性 | ✅ voltages ∈ [0.994, 1.000] pu のため両閾値とも 0 (= 期待通り) |

### Section 3b — M5 `SensitivityAnalyzer.analyze`

| 検証項目 | 結果 |
|---|---|
| 同一 4 experiments に metric 閾値を 11 grid 点で再評価 | ✅ |
| metric 値の単調性 (閾値が上がると違反率が上がる) | ✅ `metric_min=0.0` (θ=0.90), `metric_max=0.75` (θ=1.00) |
| Bootstrap CI 算出 (n=50, seed=42) | ✅ 算出されたが幅 0 — 4 サンプル × 決定的 metric では再サンプリングが等しい値を返すため (small-sample artefact、設計通り) |

`metric_max=0.75` は閾値 1.00 pu の時に 12/16 voltages が下回ることに対応 (bus1/2/3 × 4 sweep = 12 点)。物理的に妥当。

## 4. 4 機能の動作実証サマリ

| 機能 | 検証 section | 動作 |
|---|---|---|
| §5.1.1 A (axis target = metric) | Section 2 (sweep_plan の axis target は実装済みかつ smoke 経路で動作) | ✅ |
| §5.1.1 B (`gridflow evaluate`) | Section 3a (Evaluator UseCase 経由) | ✅ |
| §5.1.2 (column per_experiment_metrics) | Section 2 + Section 3a | ✅ |
| §5.1.3 (CDL canonical input) | Section 1 | ✅ |
| M5 (`SensitivityAnalyzer`) | Section 3b | ✅ |

## 5. 残課題 / 注意

- **OpenDSS 経路の live solve smoke**: `opendssdirect` 未インストールのため直接 solve は行わず、`from_canonical` の **script 生成のみ**を検証した。完全な OpenDSS-vs-pandapower クロスソルバー数値比較は extras 入り CI ジョブ で別途実施 (`smoke-opendss` ジョブ)。
- **Bootstrap CI 幅 0**: 4 サンプル × 決定的 metric では bootstrap CI が縮退する。これは設計上の不具合ではなく入力サンプル数の問題。実シナリオ (n=500+) では非ゼロの CI 幅が出ることを SensitivityAnalyzer 単体テスト (`tests/unit/usecase/test_sensitivity.py::test_bootstrap_emits_ci_bounds`) で確認済み。
- **`gridflow evaluate` CLI の subprocess 経由テスト**: ここでは UseCase API 直叩きで検証した。CLI 表面 (`runner.invoke`) は `tests/unit/adapter/test_cli.py::TestEvaluateInlineMode` でカバーしている。

## 6. 結論

**Phase 2 v0.4 の 4 機能 + M5 はすべて end-to-end で動作する。** §5.1.1〜§5.1.3 の MVP gap は閉塞済み、設計書 03b §3.6a / §3.7 / §3.5.4a と実装が一致していることを実走で確認した。

## 7. 再現方法

```bash
uv run python -m test.mvp_try8.tools.run_validation
cat test/mvp_try8/results/summary.json
```

`GRIDFLOW_HOME` は `test/mvp_try8/.gridflow_home` にスコープされるので gridflow の他の実行と干渉しない。
