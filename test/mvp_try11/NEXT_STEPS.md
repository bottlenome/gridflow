# try11 次セッション詳細手順書

実施: 2026-04-30 (PWRS reviewer C3/C2 への対応途中で次セッションへ引き継ぎ)
本書は **次のコンテナ / 次の作業者** が現状を正確に把握して継続できるように
書かれた手順書です。

---

## A. プロジェクト背景・目的・stakeholder

### A.1 gridflow とは

`/home/user/gridflow/` に置かれた **電力系統研究用ツール群** プロジェクト。
Python ベース、pandapower / pulp / pyaml 等を依存に持つ。配電網シミュレー
ション + 最適化 + ベンチマーク + シナリオパック管理の hexagonal architecture
で実装されている (`src/gridflow/{domain,usecase,adapter,infra}`)。

主要設計原則は **`/home/user/gridflow/CLAUDE.md`** に記載 (要必読):
- §0.1 妥協なき理想設計の原則
- §0.5 割り切り禁止 + 聞く前に考える原則 (§0.5.3 自問テンプレート)

### A.2 MVP 検証フロー

`/home/user/gridflow/docs/mvp_review_policy.md` で定義された 4 phase loop:

```
Phase 0   課題収集 (= research_landscape.md / mvp_problem_candidates.md)
Phase 0.5 アイデア創出 (Rule 1-9) — ← AI 平均化バイアス回避が目的
Phase 1   仮想研究者による実装 + 実験
Phase 2   仮想査読者による review (= review_record.md)
Phase 3   PO による最終 review
```

各 try (try1, try2, ...) が独立した MVP cycle。本 try11 は **try10 phyllotactic
charging** の失敗 (= Rule 9 v1 単一遠隔ドメイン) を受けて Rule 9 v2 (≥3 候補
+ invariant 検査) を最初から適用した cycle。

### A.3 try11 の研究目標

**問題**: 仮想発電所 (Virtual Power Plant; VPP) の補助サービス契約に発生する
重尾 burst churn (= 共通因果トリガーで DER が同期離脱)。

**提案手法**: **Causal-Trigger Orthogonal Portfolio (CTOP)** = DER の物理因果
トリガー曝露ベクトルを基にした discrete structural causal portfolio MILP。
動物行動学の sentinel 機構を遠隔ドメイン移植 (Rule 9 v2 で 5 候補から
invariant 検査により機械的選定)。

**target venue**: IEEE Trans. on Power Systems (PWRS) — top venue。
revision 受理水準を要件とする。

### A.4 stakeholder と作業形態

- **PO (Product Owner)**: 本リポジトリのオーナー。前セッションで PWRS reviewer
  ゼロベースレビューを依頼、reviewer C3 (96% voltage 違反は致命的) /
  C2 (合成データのみは PWRS 不可) を指摘済み。
- **作業形態**: PO が **コンテナを移動** する都度引き継ぎが発生。本書は
  この non-持続的環境を前提とした handover document。
- **コミット運用**: 各 MS (milestone) で smoke test 付き commit + push を
  徹底 (= 進捗を環境跨いで保存)。

### A.5 Phase D の **真の目的** (本引継書の範囲)

PWRS reviewer C3 (= deployable でない 12% voltage violation) と
C2 (= framework のみで実データ未取得) の **真の解消**。

成功定義 (Phase D 完了基準):

| 項目 | 達成基準 |
|---|---|
| Voltage 違反 (dispatch-induced) | **< 0.1%** (PWRS 水準) |
| 実データ実験 | **少なくとも 1 source (CAISO 推奨) で sweep 結果取得** |
| 倫理的 review_record | **「12% 合格」判定を取消、honest re-judge** |
| 論文の引用整合 | abstract / §1.4 / §6 / §9 が新数値と一致 |
| 再現可能性 | 全 sweep が seed 固定で deterministic、commit 履歴で trace 可能 |

達成すれば PWRS revision 投稿水準。失敗すれば 後段 §代替パス を参照。

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

## 4. Phase D-2: Tight bound MILP + infeasibility 報告

**目的**: 現状の M7 で使った relaxed bound (V_max=1.10, line_max=120%) を
**運用基準** (V_max=1.05, line_max=100%) に戻し、その下で feasible/infeasible
を honestly に報告する。

### 4.1 問題

現状 `tools/run_phase1_multifeeder.py` の M7 case:

```python
sol = solve_sdp_grid_aware(
    pool, active_ids, burst, bus_map=bus_map, feeder_name=feeder_name,
    basis=TRIGGER_BASIS_K3,
    v_max_pu=1.10, line_max_pct=120.0,  # ← relaxed
    mode="M7-grid",
)
```

これは ANSI / IEEE 規格を 1% 超えても許容する hack。**実運用なら一発不採用**。

しかも、この緩和が `feasible=True` を作ったので、論文の主張が一見成立しただけで、
真の運用基準で再評価すると infeasible になる可能性が高い。

### 4.2 実装手順

#### Step 1: M7 の bound を tight 化 (V_max=1.05, line_max=100%)

```python
# In run_phase1_multifeeder.py:
if method == "M7":
    sol = solve_sdp_grid_aware(
        pool, active_ids, burst, bus_map=bus_map, feeder_name=feeder_name,
        basis=TRIGGER_BASIS_K3,
        v_max_pu=1.05,        # ← ANSI C84.1 strict
        line_max_pct=100.0,   # ← 線路定格
        mode="M7-strict-grid",
    )
```

#### Step 2: Infeasibility を ExperimentResult に明示

`run_one_cell` で `sol.feasible == False` の場合:

```python
if not sol.feasible:
    return {
        "feeder": feeder, "scale": scale, "trace_id": trace_id,
        "method": method, "seed": seed,
        "elapsed_s": round(elapsed, 3),
        "error": None,
        "design_cost": None,
        "n_standby": 0,
        "infeasible": True,                      # ← 追加 field
        "infeasibility_reason": "MILP infeasible under V_max=1.05 strict",
        "metrics": {},
    }
```

aggregate スクリプトで infeasible cells を別カウント。

#### Step 3: Soft fallback (M7-soft) variant 追加

infeasible の場合に違反量を最小化する soft variant を実装:

```python
def solve_sdp_grid_aware_soft(...):
    """電圧制約を hard でなく penalty 項に。
    overshoot violation の総和を minimize するスラック変数を導入."""
    # 各 bus i に slack s_i ≥ 0 を導入
    # constraint: V_i ≤ V_max + s_i
    # objective: cost + λ * sum(s_i)
```

これで「strict 不可だがどれだけ近づけるか」を測定可能。

#### Step 4: Re-run F-M2 sweep with tight bounds

```bash
PYTHONPATH=src .venv/bin/python -m tools.run_phase1_multifeeder \
    --feeders cigre_lv kerber_dorf kerber_landnetz \
    --scales 200 \
    --traces C1 C2 C3 C4 C5 C6 C7 C8 \
    --methods M1 M7 M7-soft B1 B4 B5 \
    --seeds 0 1 2 \
    --n-workers 4
```

期待される結果:
- M7 (strict): cigre_lv で多くの cell が **infeasible**
- M7-soft: feasible だが slack > 0 (= 違反緩和の量を測定)
- M1 (no grid): 高 voltage 違反のまま (現状)

#### Step 5: 結果を honestly 報告

`results/try11_FM2_strict_results.json` に分けて出力。次の集計で:

- M7 strict が **何 % の cell で feasible** か (= 運用域の境界)
- M7 strict の voltage 違反は **<0.1%** (= 制約により構造的に保証)
- M7-soft の slack 平均 (= 構造保証を緩めた場合のコスト)

### 4.3 完了基準

- M7 strict (V_max=1.05) で feasible cell の voltage 違反 ratio < 0.1%
- infeasible cells の割合を report に明記
- M7-soft の slack 統計を取得し、緩和コストを定量化
- review_record で「12% 合格」判定を取消、「strict X% feasible / soft Y%」に書換

### 4.4 想定される困難と対処

#### 困難 A: cigre_lv のほぼ全 cell が infeasible

baseline_v_min = 0.912 で既に違反、SDP は positive injection のみで V_min は
上げ得るが V_max もタイトに制約されるので、そもそも feasible 領域が極小。

**対処**: D-3 (active pool MILP 化) で active 配置を grid-aware にする。
それでも infeasible なら **cigre_lv はこの SLA scale には不向き** と論文で
明示し、kerber_dorf / kerber_landnetz で主張を作る。

#### 困難 B: kerber_dorf / kerber_landnetz でも infeasible 多発

burst kw に対して standby 容量が物理的に不足している可能性。SLA target を
さらに下げる (= per-feeder 30% trafo MVA) か、active pool size を再設計
(= D-3)。

### 4.5 工数目安

1-2 日 (sweep 実行 1142s × 2 回 + soft variant 実装 + 結果分析)

---

## 5. Phase D-3: Active pool を含む完全 MILP (M8)

**目的**: 現状は active pool を `feeder_active_pool()` で固定していたが、
これを **MILP の決定変数** に昇格させて、grid-aware な active 配置で
baseline 違反を構造的に解消する。

### 5.1 問題

現状 `_make_active_pool` (run_phase1_multifeeder.py 内) で:

```python
def _make_active_pool(pool, sla_kw):
    ev_pool = [d for d in pool if d.der_type == "residential_ev"]
    return frozenset(d.der_id for d in ev_pool[:cfg.n_active_ev])
```

= **decision-time に random EV を 60 機ピックアップ**。これらの EV は cigre_lv
の任意 bus に配置されるので、**たまたま V_min 違反を悪化させる場所** に
集まる可能性。

D-1, D-2 で voltage 違反が baseline 起因と判明した場合、その baseline を
変えない限り改善できない。

### 5.2 提案: M8 — Active + Standby joint optimization

active 集合と standby 集合を **同時に** MILP の binary 変数で表現し:

```
変数:
  y_j ∈ {0,1}    DER j を active に入れるか
  x_j ∈ {0,1}    DER j を standby に入れるか
  ∀j: y_j + x_j ≤ 1   (両方には入れない)

目的:
  min sum_j (c_j^active * y_j + c_j^standby * x_j)

制約:
  - SLA: sum_j cap_j * y_j ≥ SLA_target × α  (active capacity がベース)
  - TriOrth: ∀k ∈ E_active(y): sum_j e_jk * x_j = 0
       (E_active は y で曝露される軸の集合 — このままだと quadratic だが
        big-M 線形化可能 [後述])
  - Capacity coverage (standby): ∀k: sum_j (1-e_jk) * cap_j * x_j ≥ B_k
  - Voltage upper: ∀i ∈ buses:
       V_baseline_existing_load_i
       + sum_j cap_j * V_imp[i, b(j)] * y_j   ← active も寄与
       + sum_j cap_j * V_imp[i, b(j)] * x_j
       ≤ 1.05
  - Voltage lower: ∀i:
       V_baseline_existing_load_i + sum_j cap_j * V_imp[i, b(j)] * y_j
       ≥ 0.95
       (= active が **存在することで baseline 改善** する形を陽に書く)
  - Line loading: 同様
```

### 5.3 quadratic な TriOrth の big-M 線形化

`E_active(y) = {k : ∃j active, e_jk=1}` を扱うために中間変数 z_k:

```
z_k = 1   iff sum_j e_jk * y_j ≥ 1
        ↓ big-M で
z_k ≥ (sum_j e_jk * y_j) / N  (N = pool size)
z_k ≤ sum_j e_jk * y_j

# TriOrth 制約:
∀k: sum_j e_jk * x_j ≤ M * (1 - z_k)
   = if z_k=1 (= active 曝露あり), x 側で曝露ゼロ強制
     if z_k=0 (= active 曝露なし), 制約緩い (M で支配)
```

これで MILP として可解 (binary x, y, z + linear constraint)。

### 5.4 実装手順

#### Step 1: `tools/sdp_full_milp.py` を新規作成

```python
def solve_sdp_full(
    pool,
    bus_map,
    feeder_name,
    burst_kw,
    sla_target_kw,
    *,
    basis=TRIGGER_BASIS_K3,
    v_max_pu=1.05,
    v_min_pu=0.95,
    line_max_pct=100.0,
) -> SDPSolution_extended:
    # MILP 構築 (上記 §5.2)
    # binary y, x, z 変数
    # 5 種類の制約セット
    # PuLP/CBC で解く
    ...
```

新たに `SDPSolution_extended` (active_ids も output に含める) を frozen dataclass
で追加。

#### Step 2: `run_phase1_multifeeder.py` に M8 case 追加

```python
METHODS = (... existing ..., "M8", ...)

def _solve(...):
    if method == "M8":
        sol_ext = solve_sdp_full(
            pool, bus_map=bus_map, feeder_name=feeder_name,
            burst_kw=burst, sla_target_kw=sla_kw,
        )
        # active_ids も sol_ext から取得
        return (sol_ext.standby_ids, sol_ext.active_ids,
                sol_ext.objective_cost, "M8-full", policy)
```

`run_one_cell` で active が dynamic に変わる場合に対応するため、
`feeder_active_pool` をスキップするフラグを追加。

#### Step 3: smoke test `tools/_msD3_smoke_test.py`

cigre_lv で M1 (= active 固定) vs M8 (= active 自由) 比較:

- M8 が選ぶ active 配置を可視化 (どの bus に EV が集まるか)
- baseline_v_min 改善を確認 (例: 0.912 → 0.94 など)
- voltage 違反 (strict V_max/V_min) が <0.1% に下がるか
- cost が大幅に増加しないか確認

#### Step 4: F-M2 sweep に M8 を追加

M8 の MILP は変数数が 2N (= 400 for N=200) で重いが、CBC で 1-5 秒/cell 想定。
全 360 cell で ~30 分。

### 5.5 完了基準

- M8 strict (V_max=1.05/V_min=0.95) が **多くの cell で feasible** (現状の M7
  strict より大幅改善)
- baseline_v_min が active 配置最適化により改善されることを実測
- M8 の cost が M1 の +20% 以内 (= 過大なコスト増を回避)

### 5.6 リスク

- MILP 変数数が倍増 → solve time 5-10x、N=5000 で確実に timeout
- → M4b 同様 greedy heuristic (M8b-greedy) を別途用意する必要性

### 5.7 工数目安

2-3 日 (MILP 設計 + big-M 線形化 + smoke test + sweep 実行)

---

## 6. Phase D-4: Feasibility envelope 分析 (novel contribution)

**目的**: D-2/D-3 で voltage 制約付き MILP が成立する範囲が **feeder × SLA × burst**
の複合的な関数であることが分かった。これを **明示的に可視化** することで
論文の novel contribution に昇格させる。

### 6.1 アイデア

PWRS reviewer の典型的批判は「benchmark が単一 setup」。Feasibility envelope
は **どの operational regime で CTOP が deployable か** を示すマップで、
配電事業者にとって直接的な意思決定支援となる。

### 6.2 実験設計

3 軸 grid sweep:

```
feeder ∈ {cigre_lv, kerber_dorf, kerber_landnetz}
SLA scale α ∈ {0.10, 0.20, 0.30, 0.40, 0.50, 0.60} × trafo_MVA
burst level β ∈ {0.5, 1.0, 1.5, 2.0} × default_burst
```

= 3 × 6 × 4 = 72 (feeder, α, β) cells × 8 traces × 3 seeds × 16 methods
= 27,648 cells

**スケール大** なので分割実行:
- **D-4a**: 1 method (M8 strict) のみで envelope 測定 = 1,728 cells (= 約 1 時間)
- **D-4b**: 1-2 baseline (B4 etc.) を加えて比較 = 5,184 cells (= 約 3 時間)

### 6.3 測定指標

各 (feeder, α, β) cell で:

- **Feasibility rate**: (feasible cells) / (8 traces × 3 seeds) ∈ [0, 1]
- **Mean SLA violation**: feasible cells のみ
- **Mean voltage violation (dispatch-induced)**: D-1 metric
- **Mean cost normalised by SLA**: ¥ / kW_SLA (= cost intensity)

### 6.4 視覚化

3 つの heatmap (per feeder):

```
         β=0.5  β=1.0  β=1.5  β=2.0
α=0.10    ✅100%  ✅100%  ✅100%  ⚠️70%
α=0.20    ✅100%  ✅100%  ⚠️60%  ❌20%
α=0.30    ✅100%  ⚠️70%  ❌30%  ❌5%
α=0.40    ⚠️80%  ❌40%  ❌10%  ❌0%
α=0.50    ❌50%  ❌10%  ❌0%   ❌0%
...
```

各セル = feasibility rate (緑/黄/赤)。これが論文の Figure 6 候補。

### 6.5 論文への組込方針

報告書 §6 に新節 §6.5 "Feasibility Envelope" を追加:

> CTOP の operational deployability は (feeder, SLA scale, burst level) の
> 三軸関数。我々は 72 (feeder × α × β) operating points × 8 traces × 3 seeds
> で envelope を測定し、配電事業者向け **deployability map** を作成。
> CIGRE LV は α ≤ 0.20 で 100% feasible、Kerber Dorf は α ≤ 0.40 で 90%、
> Kerber Landnetz は α ≤ 0.50 で 100%。

### 6.6 実装手順

#### Step 1: `tools/run_envelope.py` を新規作成

`run_phase1_multifeeder.py` を base に、α/β を sweep 軸に追加:

```python
def main():
    parser.add_argument("--alpha-sla", type=float, nargs="+",
                        default=[0.10, 0.20, 0.30, 0.40, 0.50, 0.60])
    parser.add_argument("--beta-burst", type=float, nargs="+",
                        default=[0.5, 1.0, 1.5, 2.0])
    ...

def run_one_envelope_cell(args):
    feeder, alpha, beta, trace_id, method, seed = args
    cfg_default = get_feeder_config(feeder)
    sla_kw = cfg_default.sla_kw * (alpha / 0.50)  # rescale
    burst = {k: v * beta for k, v in cfg_default.burst_dict().items()}
    ...
```

#### Step 2: 集計スクリプト `tools/aggregate_envelope.py`

```python
# (feeder, alpha, beta) の三重ループで feasibility rate を算出
# matplotlib heatmap で 3 図描画
```

#### Step 3: 論文 §6.5 に embed

### 6.7 完了基準

- 3 feeder × 6 α × 4 β = 72 envelope cells の feasibility / cost / violation を測定
- matplotlib heatmap 3 図 (per feeder) を `results/plots/feasibility_envelope_*.png`
- 論文 §6.5 "Feasibility Envelope" を執筆 (~ 1 ページ + 3 図)

### 6.8 工数目安

1-2 日 (sweep 1-3 時間 + 集計 + 図 + 論文執筆)

---

## 7. Phase D-5: 実データ取得 (C2 真の解消)

**目的**: PWRS reviewer C2 (合成のみは不可) の真の解消には **実データを使った
実験結果** が必須。本コミット時点では framework のみで、実データ取得は未達。

### 7.1 取得対象 (優先度順)

| # | dataset | 取得難度 | 期待効果 |
|---|---|---|---|
| 1 | **CAISO 5-min system load** | 易 (公開 API) | trigger trace の統計検証 |
| 2 | **AEMO South Australia VPP report** | 易 (PDF 抽出) | VPP availability 直接検証 |
| 3 | **Pecan Street residential EV** | 中 (academic registration) | DER 個別 churn 直接検証 |
| 4 | NREL ResStock | 中 (large download) | 補助検証 |
| 5 | JEPX 30-min spot price | 易 (CSV download) | market trigger 検証 |

### 7.2 各取得手順

#### 7.2.1 CAISO (最優先、公開 API)

URL pattern (本実装の loader docstring 内既述):
```
https://oasis.caiso.com/oasisapi/SingleZip
   ?queryname=PRC_RTPD_LMP
   &startdatetime=20240101T07:00-0000
   &enddatetime=20240108T07:00-0000
   &resultformat=6
```

**取得方法 (次セッションで実装)**:
```python
# tools/fetch_caiso.py
import requests
import zipfile
import io
import csv

def fetch_caiso_load(start_iso: str, end_iso: str, out_path: Path):
    # PRC_RTPD_LMP は LMP 価格データ; system load は SLD_FCST 等
    # 正確な query name を CAISO ドキュメントで確認:
    # https://www.caiso.com/Documents/OASISAPISpecification.pdf

    url = (
        f"https://oasis.caiso.com/oasisapi/SingleZip"
        f"?queryname=ENE_HASP&startdatetime={start_iso}&enddatetime={end_iso}"
        f"&resultformat=6"
    )
    r = requests.get(url, timeout=60)
    r.raise_for_status()
    with zipfile.ZipFile(io.BytesIO(r.content)) as zf:
        for name in zf.namelist():
            if name.endswith(".csv"):
                # parse and convert to gridflow loader format
                ...
```

**注意点**:
- CAISO は 30 日 max per query → 月毎にループ
- `resultformat=6` で CSV、それ以外で XML
- rate limit: 60 query / hour (cron で分割)

**期待される CSV format** (gridflow loader 用に変換):
```
ts_iso,system_load_mw
2024-01-01T00:00:00Z,28100.5
2024-01-01T00:05:00Z,28050.0
...
```

#### 7.2.2 AEMO South Australia VPP

AEMO は四半期報告書 (PDF) で VPP データを公開。直接 CSV はないが:

**取得方法**:
1. https://aemo.com.au/initiatives/major-programs/nem-distributed-energy-resources-der-program/der-demonstrations/virtual-power-plant-vpp-demonstrations
   から最新 PDF を DL
2. Tabular extraction (camelot-py / tabula-py) で表形式抽出
3. ts_iso, n_units_online, total_capacity_kw, frequency_hz の列を生成

**代替案**: AEMO Data Dashboard (https://aemo.com.au/en/energy-systems/electricity/national-electricity-market-nem/data-nem)
の DER register CSV を使う (= aggregated, より低時間粒度だが直接 CSV)。

#### 7.2.3 Pecan Street residential EV

**重要: Academic registration が必要**。次セッションで:

1. PI / lab account で https://www.pecanstreet.org/dataport/ 登録
2. Data Use Agreement (DUA) 締結
3. Residential EV charging dataset (1-15 households, 5-min, 1 month) を DL
4. CSV を $GRIDFLOW_DATASET_ROOT/pecanstreet/residential_ev/v1/data.csv に配置

**注意**: Pecan Street は **redistribution 禁止** (Proprietary-Research)。論文には
集計値のみ公開 (個別 household ID は隠す)。

#### 7.2.4 JEPX spot price

**最も簡単**: https://www.jepx.org/electricpower/market-data/spot/ から CSV
直接 DL (CC-BY-4.0)。

```bash
curl -O "https://www.jepx.org/.../<year>_spot.csv"
# Excel-style 列を ts_iso, spot_price_jpy_per_kwh に変換
```

#### 7.2.5 NREL ResStock

**大規模** (TB スケール)。サブセット (数 household × 1 月) を BuildStock LDB
からピンポイント取得。

### 7.3 取得後の検証手順

#### Step 1: Loader smoke test (実データで)

```bash
# 各 source の load() が DatasetTimeSeries を返すことを確認
PYTHONPATH=src .venv/bin/python -c "
from gridflow.adapter.dataset import CAISOLoader
from gridflow.domain.dataset import DatasetSpec
ts = CAISOLoader().load(DatasetSpec(dataset_id='caiso/system_load_5min/v1'))
print(f'n_steps={ts.n_steps}, sha256={ts.metadata.sha256[:10]}')
"
```

#### Step 2: try11 sweep を実データで再実行

`run_phase1_multifeeder.py` を改修し、trace を実データから生成:

```python
# CAISO load を normalize して active_fraction にマッピング
real_trace = build_real_trace_from_caiso(...)
# 既存の synth_c1_single_trigger と互換 ChurnTrace で出力
```

#### Step 3: Real-data results を report に追加

新節 §6.6 "Real-Data Validation":

> CAISO 2024 Q1 system load (n=8640 timesteps) と AEMO Tesla VPP report
> (n=8640) の実データで try11 sweep を再実行。M7 の SLA 違反 X% (vs 合成
> Y%)、voltage 違反 X% (合成 Y%)。

### 7.4 完了基準

- 5 dataset のうち少なくとも **3 source** で実 CSV 取得
- 各 source で `data.csv + metadata.json` が `$GRIDFLOW_DATASET_ROOT/` に配置
- sha256 が contributor 署名つきで `docs/dataset_catalog.md` に登録
- try11 sweep を実データで再実行、結果を report §6.6 に組込

### 7.5 取得不可シナリオの対処

PWRS reviewer は **少なくとも 1 つの実データ** を要求するので、最低限:

- CAISO (= 公開 API、rate limit 内で fetch 可) を **必ず** 取得
- 残りは contributor を募る (= GitHub PR で受付)

### 7.6 工数目安

- CAISO 取得 + sweep 再実行: 1 日
- AEMO PDF 抽出 + sweep: 1-2 日
- Pecan Street registration → 取得 → sweep: 1 週間 (registration が律速)
- 全 5 source: 2 週間

---

## 8. Phase D-6: Multi-scale 検証 (mod-A1)

**目的**: Theorem 2 (`theorems.md` §Theorem 2) で示した greedy ln(K)+1 倍境界を
**N=50, 200, 1000, 5000** で実測し、論文に scaling table を追加。

### 8.1 測定軸

```
N ∈ {50, 200, 1000, 5000}
method ∈ {M1 MILP, M4b greedy, M7 grid-aware, M8 full}
trace ∈ C1 (代表)
seed ∈ {0, 1, 2}
feeder = cigre_lv (代表)
```

= 4 × 4 × 1 × 3 × 1 = 48 cells

### 8.2 期待される結果

```
N      M1 cost  M4b cost  ratio   M1 time  M4b time
50     1500     2000      1.33    0.005s   < 0.001s
200    3500     6000      1.71    0.013s   < 0.001s
1000   15000    25000     1.67    0.5s     0.005s
5000   timeout  100000    -       >300s    0.05s
```

主張:
- N≤200 では MILP が実用域、greedy は ~1.7x cost
- N≥1000 では MILP が次第に遅くなる
- N=5000 では MILP が timeout、greedy のみ実用 → Theorem 2 の境界 1.83 (K=3) 内

### 8.3 実装手順

#### Step 1: `tools/run_scaling.py` を新規作成

`run_phase1_multifeeder.py` を base に N を sweep 軸に。Pool 拡張は既存
`make_scaled_pool` (`der_pool.py`) を使う。

#### Step 2: timeout 処理

CBC に timeLimit=300 を設定し、timeout した cell を `infeasible_timeout=True`
として記録。

#### Step 3: 結果 plot

```
tools/plot_scaling.py:
  - x 軸: N (log scale)
  - y 軸 (左): cost (log)
  - y 軸 (右): solve time (log)
  - line: M1 / M4b / M7
```

### 8.4 工数目安

1 日 (sweep + 集計 + plot)

---

## 9. Phase D-7: Report / review_record 再書き (倫理対応)

**目的**: 60% / 12% の voltage 違反で「合格」とした判定を取消、真の合格
基準で書き直す。

### 9.1 修正対象

| ファイル | 修正内容 |
|---|---|
| `report.md` §1 Abstract | "5x voltage reduction" を取消、"in some regime" に慎重化 |
| `report.md` §6 F7 | 12% を **dispatch-induced X% / baseline-only Y%** に分解 |
| `report.md` §8.7 | 「実装済み」→「strict bound で feasibility envelope 測定」に書き直し |
| `report.md` §9 | "合格" を "Phase D 拡張で投稿水準に到達見込み" に書き換え |
| `review_record.md` §総合判定 | 「合格 (top venue 水準)」を取消、「条件付き合格 (Phase D 必須)」に格下げ |

### 9.2 倫理的注意

論文文中で:
- 「relaxed bound (V_max=1.10) を使った」事実を **必ず明記**
- ANSI C84.1 strict (1.05) 準拠は **future work** と明示
- 「12% violation」は dispatch + baseline の合算で、内訳が分離されていない時点
  での measurement であることを **明示**

これらを隠すと scientific misconduct になる。

### 9.3 工数目安

1 日 (report 4 節改訂 + review_record 全節改訂)

---

## 10. 全 Phase 統合スケジュール (推奨)

```
Day 1-2: D-1 (voltage metric 二分解) + D-7 一部 (60% 合格判定取消)
Day 3-4: D-2 (tight bound + infeasibility report)
Day 5-7: D-3 (M8 active+standby joint MILP)
Day 8-9: D-4 (feasibility envelope)
Day 10-12: D-5 (実データ取得 — CAISO 最低限)
Day 13: D-6 (multi-scale)
Day 14-15: D-7 (report 全面再書き) + 最終 review_record
```

合計 **約 2-3 週間**。

### 10.1 短縮版 (= D-1, D-2, D-7 のみで 1 週間)

「PWRS reject 確実な 12% 合格判定だけは取り消す」最低限路線:
- D-1 (metric 分解、半日) + D-2 (tight bound、1 日) + D-7 (report 修正、半日)
- 残課題は paper に limitation として明記

### 10.2 完全版 (= D-1〜D-7 全実装で 3 週間)

PWRS submission 準備完了水準。Phase D 後に Phase E (Phase 3 PO レビュー
+ submission preparation) へ。

---

## 11. 引継ぎ確認チェックリスト (次セッション開始時に実行)

### 11.1 環境確認

```bash
cd /home/user/gridflow
git log --oneline -10            # 最新 commit が見える
ls test/mvp_try11/results/grid_impact_cache/   # 3 feeder の cache が ある
ls test/mvp_try11/data/          # demo fixtures (CAISO/AEMO) が ある
```

### 11.2 既存テストの pass 確認

```bash
PYTHONPATH=src .venv/bin/python -m pytest tests/dataset/ -q
# 41 passed
```

### 11.3 Smoke test の pass 確認 (各 MS)

```bash
cd test/mvp_try11
for ms in _ms1 _ms2 _ms3 _ms5 _msA1 _msA2 _msA3 _msA4 _msC3_1 _msC3_3 _msC2_6; do
    PYTHONPATH=/home/user/gridflow/src \
        /home/user/gridflow/.venv/bin/python -m tools.${ms}_smoke_test
done
# 全部 OK と表示されること
```

### 11.4 既存 sweep 結果の確認

```bash
PYTHONPATH=/home/user/gridflow/src /home/user/gridflow/.venv/bin/python -c "
import json
d = json.loads(open('test/mvp_try11/results/try11_FM2_results.json').read())
print(f'records: {len(d[\"records\"])}, errors: {d[\"n_errors\"]}')
"
# records: 360, errors: 0
```

### 11.5 引継ぎコンテキスト確認

```bash
# このファイルを読み返す
cat test/mvp_try11/NEXT_STEPS.md | less
# 特に §0 (現状の正直評価) と §10 (推奨スケジュール) を確認
```

### 11.6 関連ファイル

| ファイル | 役割 |
|---|---|
| `test/mvp_try11/ideation_record.md` | Phase 0.5 ideation (Rule 1-9 全経由) |
| `test/mvp_try11/implementation_plan.md` | Phase 1 元計画 |
| `test/mvp_try11/theorems.md` | 理論貢献 (Theorem 1-3) |
| `test/mvp_try11/report.md` | 論文ドラフト (要 D-7 で再書き) |
| `test/mvp_try11/review_record.md` | 査読記録 (要 D-7 で再書き) |
| `test/mvp_try11/NEXT_STEPS.md` | 本書 (= 次セッション手順書) |
| `docs/dataset_contribution.md` | データセット contribution rules |
| `docs/dataset_catalog.md` | 登録 dataset カタログ |

---

## 12. 引継ぎメッセージ (次の作業者へ)

本実装サイクルでは、PWRS reviewer (zero-base) の指摘を全て技術的には応答した
ものの、**運用基準で見ると 12% voltage 違反は依然 deployable でない** ことに
気付いた時点で次セッションへ引き継ぎとなった。

最重要点:
1. **Phase D-1, D-2 を最優先**: 真の voltage 違反 (dispatch-induced) を測定
2. **Phase D-7 と並行**: 「60% / 12% 合格」の取消は倫理的に最優先
3. **Phase D-5 (実データ)**: CAISO 取得は技術的に容易、優先実装

PWRS submission に向けては Phase D 全実装 (2-3 週間) が必要だが、最低限
**D-1, D-2, D-7 (= 1 週間)** で「正直な現状報告」には到達できる。

成功の鍵は **CLAUDE.md §0.1 (妥協なし)** と **§0.5.3 (自己判断)** を貫くこと。
12% 合格判定はこの 2 つから外れた結果。同じ過ちを繰り返さない。

---

## 13. 更新履歴

| 日付 | 内容 |
|---|---|
| 2026-04-30 | 初版作成。chunk 1-7 で段階的にコミット。次セッションへの引継ぎ完了 |

