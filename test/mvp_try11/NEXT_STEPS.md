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
