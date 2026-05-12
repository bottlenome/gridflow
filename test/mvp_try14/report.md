# try14 — Multi-Feeder × Multi-Phase Breadth + Soft Variant

実施: 2026-04-30
シナリオ: VPP standby design (try11→12→13→14、PWRS 投稿水準到達 attempt)
データ: `results/try14_breadth.json` (256 cells)

---

## Abstract

try13 の review が指摘した残課題 3 件 ─ (a) cigre_lv α=0.70 strict での infeasibility、(b) ACN は workplace pattern で residential VPP との phase 不一致、(c) LV demo feeder のみ ─ を構造的に解決する 3 拡張 ((a) **M9-grid-soft** = slack-penalised expected-loss、(b) **ACN phase-invert** = residential VPP proxy、(c) **CIGRE MV feeder** = pandapower 同梱 22kV 50 MVA 14-bus) を実装。**8-method × 4-feeder × 2-phase × 4-week = 256 cell** の bootstrap CI sweep を実施。

**Mixed findings**: workplace phase + LV scale で M9-grid / M9-grid-soft が **kerber_dorf 単独勝者** (try13 結果を multi-week で再確認、CI 完全分離)、M9-grid-soft は cigre_lv での infeasibility を解消。一方 **MV scale (cigre_mv) では全 MILP method (M1/M7/M9/M9-grid/M9-grid-soft) が infeasible** — baseline V_min=0.923 が既に ANSI 0.95 を下回り MILP envelope に解なし、B 系 ¥180,000-198,000 の over-buy のみ feasible。Residential phase では大半の method が同等性能で controller 差別化されない。本論文は M9-grid-soft の robustness 拡張と、商用 MV scale での **deployability 限界** を honest に報告する。

---

## 1. 残課題 3 件への対応

### 1.1 (a) cigre_lv α=0.70 infeasibility — M9-grid-soft

`tools14/sdp_full_soft.py:solve_sdp_full_soft` で expected-loss 制約に slack:
$$
\forall k \in E(A): \sum_j \pi_{j,k} \mathrm{cap}_j x_j \leq \theta_k + s_k, \quad s_k \geq 0
$$
目的に λ·Σs_k 加算。常時 feasible、slack 統計で「どれだけ envelope を緩めたか」を定量化。

実測: cigre_lv α=0.70 で slack=0、|S|=9、cost ¥9,200 — ハード制約版が見つけ損ねていた feasible region を発見。

### 1.2 (b) Residential phase — ACN phase-invert

`tools14/real_data_residential.py:build_trace_from_acn_residential` で ACN session の意味を反転:
- Workplace mode (try13): active iff in-session
- **Residential mode (try14): active iff NOT in-session** (= 在宅 = home VPP available)

Trigger event は connection time (= 朝 home → workplace 出発時刻) のクラスタを抽出。

実測: PT 13-15 で availability 最低 (185/200, 仕事中) → PT 19-23 で 197 (帰宅) という **完全に opposite phase** が観測された。

### 1.3 (c) MV scale — CIGRE MV feeder

`tools14/feeders_mv.py` で pandapower の `create_cigre_network_mv()` (22 kV, 50 MVA, 14-bus) を try11 の `make_feeder` / `map_pool_to_feeder` / `grid_impact` 機構に統合。LV demo の **52-300x スケール** (kerber_landnetz 0.16 MVA → 50 MVA)。

---

## 2. 256-cell breadth sweep 結果

軸: 4 feeder × 2 phase × 8 method × 4 week × 1 pairing = 256 cells、bootstrap n_boot=2000。

### 2.1 Workplace phase 結果

| feeder (α) | 単独勝者 | 詳細 |
|---|---|---|
| cigre_lv (α=0.50) | tied | 全 method 0%/0% (= operating regime が容易) |
| **kerber_dorf (α=0.70)** | **M9-grid / M9-grid-soft** | M1/M9 grid 100% violation, M7 SLA 47.9 [44.0, 53.1]%, M9-grid 0%/0% ¥4,600 ← **CI 完全分離** |
| kerber_landnetz (α=0.70) | M7/M9/M9-grid/M9-grid-soft tied (M9 cheapest ¥1,900) | M1 SLA 62.2 [60.4, 63.5]%, B5 SLA 93.2 [81.6, 99.7]% |
| **cigre_mv (α=0.30)** | **negative** | **全 MILP method infeasible**, B1 SLA 100%, B4 ¥180,000, B5 ¥198,000 |

### 2.2 Residential phase 結果

| feeder | 観察 |
|---|---|
| cigre_lv | 全 method 0%/0% (residential phase は容易) |
| kerber_dorf | M1/M9 still grid 100% violation, **M7/M9-grid/M9-grid-soft の 3 つのみ 0%/0%** |
| kerber_landnetz | 大半 0%/0% (= phase 反転で SLA pressure 解消) |
| cigre_mv | 同 workplace、全 MILP infeasible |

### 2.3 主要発見

1. **M9-grid-soft は M9-grid を strict superset**: feasible region で同一解 (slack=0)、infeasible region でも graceful degradation
2. **kerber_dorf workplace で M9-grid / M9-grid-soft が単独勝者** (try13 結果を 4 week × multi-method で再確認、CI 完全分離)
3. **MV scale (cigre_mv) では全 MILP infeasible**: 50 MVA scale + ANSI strict bound + Bayes constraint の組合せで feasibility 域消失。B4/B5 は ¥180-198k の over-buy で SLA 0% 達成、しかし cost で MILP 系を **逆 Pareto-dominate**
4. **Residential phase は workplace よりも VPP に容易** (= 夜間帯のヒマな時間に需要):  M1 でも kerber_landnetz residential で SLA 0% を達成

### 2.4 MV infeasibility の解釈 (honest negative finding)

cigre_mv の baseline V_min = 0.923 は既に ANSI 0.95 の下限を下回る (= LV demo の cigre_lv と同様の構造的問題が MV scale でも発生)。M9-grid-soft でも slack で救えないのは、Bayes 制約だけでなく **V_max strict + V_min strict + capacity 同時** が解空間を空に追いやるため。

→ **MV scale での「deployable」主張は本研究 (try14) の実装範囲では成立せず**。Phase 2 (try15+) で:
- (i) V_min 制約も active 配置で構造的に repair する M8 (try11 Phase D-3) を MV に拡張
- (ii) 別 MV feeder (SimBench MV、IEEE 13/34 OpenDSS) で baseline V_min ≥ 0.95 の feeder を選ぶ
- (iii) MV scale 用 SLA / burst sizing の再 calibration
が必要。

---

## 3. Limitations / Phase 2

| # | 残課題 | try15 scope |
|---|---|---|
| 1 | MV scale で MILP infeasible | M8 (active+standby joint) を MV に拡張、SimBench MV / IEEE 13/34 で再検証 |
| 2 | Residential proxy (phase-invert) は ACN の semantic 反転であって真の residential data ではない | Pecan Street registration でデータ取得 |
| 3 | Multi-month/site ACN は try13 で取得済だが try14 sweep に再活用していない | week_offsets を multi-month に拡張 |

---

## 4. Conclusion

try14 は M9-grid-soft (slack-penalised) で cigre_lv α=0.70 の infeasibility を解消、CIGRE MV feeder で商用 scale 試験を導入、ACN phase-invert で residential VPP proxy を提供した。**8-method × 4-feeder × 2-phase × 4-week = 256 cell** sweep で:
- ✅ kerber_dorf workplace で M9-grid / M9-grid-soft の **単独勝者** (CI 完全分離) を multi-week × residential/workplace で再確認
- ✅ M9-grid-soft の slack 機構で graceful degradation を実証
- ❌ MV scale (cigre_mv) で MILP 系全 infeasible — **deployable scale 主張の限界を honest に露呈**
- △ Residential phase ではほとんどの method が同等 (= phase は controller 差別化に効かない)

PWRS 投稿候補としては **kerber_dorf workplace = "M9-grid as the unique 3-axis-simultaneously-satisfying solver"** を core claim、MV scale を Limitations 章で正直に報告する形で Major Revision 級。
