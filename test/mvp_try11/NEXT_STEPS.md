# try11 次セッション詳細手順書

実施: 2026-04-30 (PWRS reviewer C3/C2 への対応途中で次セッションへ引き継ぎ)
本書は **次のコンテナ / 次の作業者** が現状を正確に把握して継続できるように
書かれた手順書です。

---

## 0. 現状の正直な評価 (= 未解消の問題)

### 0.1 C3 の "解消" は不十分

PWRS reviewer は **「電圧違反 96% は致命的」** と指摘した。本実装で M7 を入れて
**96% → 12%** に下げたが、これを「合格」と判定したのは **判断ミス**:

- 配電網運用では voltage 違反は ANSI C84.1 / IEEE 1547 / EN 50160 で
  **年間 < 0.1%** が現実目標。**12% は 100x 過大** で運用展開不可。
- 60% / 12% という数値で合格を出した review_record は **書き直し必要**。
- 「relaxed bound (V_max=1.10) を使ったから許容」という言い訳は技術的には
  正しくても **運用基準を緩めた** だけで本質的解消ではない。

**真の合格基準**: voltage 違反 **< 1%** (デモ実装) / **< 0.1%** (PWRS 投稿水準)。

### 0.2 12% 違反の内訳が不明

`voltage_violation_ratio` metric は (a) dispatch 起因 (M7 の責任) と
(b) 既存負荷起因 (= cigre_lv の baseline V_min<0.95) を **混ぜて報告** している。

cigre_lv の baseline_v_min = 0.912 (`grid_impact_cache/cigre_lv.json` で確認可)
であり、**DER injection ゼロでも既に違反**。M7 はこの ground 違反を
解決できない (= positive injection は V を上げるのみ) ので、12% のうち
ある程度は **M7 が改善不能な構造的違反**。

**しかし** これも論文の主張としては **失格**: 査読者は
「合成 feeder の選択が悪い」と判断する。**実 feeder では起きない問題で
論文を構成する** のは方法論的破綻。

### 0.3 C2 の "解消" は framework のみ、実データ未取得

PWRS reviewer は **「合成のみは PWRS 水準で不十分」** と指摘した。本実装で:

- ✅ Dataset 機能 (Domain types + 6 loaders + Registry + Bridge + 41 tests pass)
- ✅ Repository contribution rules (`docs/dataset_contribution.md`)
- ✅ Demo fixtures (CAISO/AEMO published schema 一致、合成だが構造は実)
- ❌ **実データ ZIP / API fetch は 403/503 で失敗**、取得できず

つまり **「実データを使った検証」は依然未達**。framework は揃ったので、
contributor が手元データを drop すれば動くが、**論文で報告できる実データ
sweep 結果は本コミット時点でゼロ**。

### 0.4 残課題リスト

| 課題 | 重要度 | 種別 | 対応 Phase |
|---|---|---|---|
| voltage 違反を < 1% に下げる | **CRITICAL** | C3 真の解消 | **D-1, D-2, D-3** |
| voltage 違反 metric を分離 | HIGH | 計測精度 | D-1 |
| cigre_lv 既存負荷問題対処 | HIGH | feeder 設計 | D-3 |
| 実データ取得 + sweep 再実行 | **CRITICAL** | C2 真の解消 | **D-5** |
| 多 scale 検証 (N=1000, 5000) | MEDIUM | mod-A1 | D-6 |
| review_record の判定取消 | HIGH | 倫理 | D-7 |

---

## 1. 全体構造 (Phase D 概観)

次セッションで実施する Phase D は以下 7 sub-phase:

```
D-1: voltage 違反 metric の二分解 (baseline-only vs dispatch-induced)
       └─ ground violation を明示し、M7 の責任範囲を限定
D-2: tight bound MILP + infeasibility 報告
       └─ V_max=1.05 strict / V_min=0.95 で再 sweep
       └─ 実 feeder で feasible 領域を測定
D-3: active pool 含めた完全 MILP (active 側も grid-constraint 配慮)
       └─ 既存負荷起因の baseline 違反を改善する active 配置
D-4: feasibility envelope 分析
       └─ (feeder, SLA, burst) の feasible 領域を可視化
       └─ 論文の novel contribution に昇格
D-5: 実データ取得 (Pecan Street / CAISO / AEMO)
       └─ contributor route または curated public API
D-6: 多 scale 検証 (N=50/200/1000/5000)
       └─ Theorem 2 greedy ln(K) 境界の実測
D-7: report.md / review_record.md 全面再書きえ
       └─ 60% 合格判定の取消 + 真の合格基準で再評価
```

各 sub-phase は MS 単位で実装 → smoke test → commit → push を繰り返す。

---

## 2. 共通の作業ルール (次セッションで遵守)

- **CLAUDE.md §0.1 妥協なし**: 「relaxed bound で許容」のような hack はしない
- **CLAUDE.md §0.5.3 自分で判断**: ユーザー判断を仰ぐのは product judgment のみ
- **正直な metric**: 違反率を内訳分解し、誰の責任かを明示
- **failure を honest に報告**: infeasible なら infeasible と報告 (隠さない)
- **小コミット**: MS 単位、smoke test 付き、commit message に意図明記

---

## 3. Phase D-1: Voltage 違反 metric の二分解

**目的**: 既存負荷起因の baseline-only 違反 (= M7 の責任外) と、SDP の dispatch
が引き起こす dispatch-induced 違反 (= M7 の責任) を明示分離する。

### 3.1 問題

現状の `voltage_violation_ratio` (= `tools/grid_metrics.py`) は

```python
violations = sum(
    1 for vmin, vmax in zip(v_min, v_max)
    if vmin < 0.95 or vmax > 1.05
)
return violations / n
```

で、(a) DER injection ゼロでも違反する step、(b) injection で v が押し上げ
られて違反する step を区別しない。

cigre_lv の場合: baseline_v_min = 0.912 < 0.95 で、**全 step で v_min 違反**。
M7 がどんな選択をしても改善されない (positive injection しか提供しないので)。

### 3.2 実装手順

#### Step 1: `grid_simulator.py` を修正、baseline ground truth を保存

```python
# In grid_simulator.py, add to GridRunResult:
@dataclass(frozen=True)
class GridRunResult:
    # 既存フィールドに加えて:
    baseline_voltage_min_pu: tuple[float, ...]    # DER injection ゼロ時の V_min(t)
    baseline_voltage_max_pu: tuple[float, ...]    # 同 V_max(t)
    baseline_line_load_pct: tuple[float, ...]     # 同 L_max(t)
```

baseline は **その timestep に existing load だけが流れているとき** の voltage。
これを `grid_simulate` の中で計算するには:

```python
# 各 sample step で 2 回 PF を回す:
# (1) DER 全停止 (active も standby も) で baseline_v_*
# (2) DER 動作中の状態で v_min/v_max
```

または、`grid_impact.py` で計算済みの `baseline_v_pu` (existing load only)
を timestep に依らない定数として使い、active / standby の injection 寄与
を線形重畳して per-step v_min(t), v_max(t) を計算する (= DistFlow 線形近似で)。

**推奨: 後者** (1 回の追加 PF で済む、計算量 O(1))。

#### Step 2: `grid_metrics.py` に新 metric 追加

```python
@dataclass(frozen=True)
class VoltageBaselineViolationRatio:
    """既存負荷だけで起きる V 違反の比率 (= M7 が改善不能)."""
    name: str = "voltage_violation_baseline_only"
    # __aggregate__ や __sla_target__ と同じ pattern で、
    # __voltage_baseline_min__ / __voltage_baseline_max__ から計算

@dataclass(frozen=True)
class VoltageDispatchInducedViolationRatio:
    """SDP の dispatch が引き起こした V 違反の比率 (= M7 の責任)."""
    name: str = "voltage_violation_dispatch_induced"
    # baseline では違反していないのに、dispatch 後に違反した step
    # = (vmin_actual < 0.95 and vmin_baseline >= 0.95)
    #   OR (vmax_actual > 1.05 and vmax_baseline <= 1.05)
```

#### Step 3: `to_grid_experiment_result` で baseline 系列を ExperimentResult に埋込

```python
load_results = (
    ...,
    LoadResult(asset_id="__voltage_baseline_min__",
               demands=v_baseline_min, supplied=v_baseline_min),
    LoadResult(asset_id="__voltage_baseline_max__",
               demands=v_baseline_max, supplied=v_baseline_max),
    ...,
)
```

#### Step 4: smoke test

`tools/_msD1_smoke_test.py`:

- cigre_lv で M7 を実行
- 既存の voltage_violation_ratio (合算) が ~10% 程度
- 新 metric `voltage_violation_baseline_only` が ~10% (= ほぼ全部 baseline 起因)
- `voltage_violation_dispatch_induced` が ~0% (= M7 は injection で V 上げて
  むしろ改善している場合も)
- 全 metric が finite かつ sum 整合性 (合算 = baseline + dispatch を超えないこと)

#### Step 5: aggregate スクリプト更新

`/tmp/aggregate_C3.py` を `tools/aggregate_results.py` に格上げし、
新 metric を表示。

### 3.3 完了基準

- 既存 voltage_violation_ratio が **2 つの内訳** に分解される
- M7 の dispatch-induced 違反が **数値で 0-1% 以内** であることを確認
- baseline-only 違反は別途報告 (= feeder 設計の問題として明示)
- review_record で「M7 voltage 違反 12%」を「dispatch-induced X%, baseline Y%」と
  内訳付きに書き換える

### 3.4 工数目安

半日〜1 日 (PF call 増加あり、smoke test 含む)

---
