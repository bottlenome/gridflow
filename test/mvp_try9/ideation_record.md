# try9 Phase 0.5 — アイデア創出記録

実施: 2026-04-28
準拠: `docs/mvp_review_policy.md` §2.5 (Rule 1〜6 + Novelty Gate)

---

## 1. 起点: Phase 0 で選定した課題

`docs/research_landscape.md` から **2 件複合**で選定:

| 課題 ID | 内容 | 査読出典 (Future Work) |
|---|---|---|
| **C-3** | データ品質・プロビナンスの欠落 — 「outdated/incomplete network models と inaccurate load profiles が HCA 信頼性を根本的に崩す」 | [ScienceDirect 2025 HCA challenges](https://www.sciencedirect.com/science/article/pii/S0306261925020537) |
| **C-10** | 電圧/熱違反の定義のばらつき — 「voltage violation ratio の計算式が論文ごとに異なる」 | [MDPI Energies 2023](https://www.mdpi.com/1996-1073/16/5/2371) |

**複合化の理由**: C-3 (load profile の不確実性) と C-10 (threshold 選択) は HCA の出力に同時に影響する。先行論文は片方ずつ扱っており、**交互作用が定量化されていない** ことが両論文の Future Work から導ける gap。

---

## 2. Rule 1 (HAI-CDP) — AI に 12 候補を出させる (ranking なし)

「HCA における load uncertainty と threshold uncertainty の交互作用を扱うアプローチ」を 10+ 列挙:

1. Quantile regression on HC vs PV penetration with threshold as categorical
2. ANSI committee-friendly: per-regulatory-zone calibrated threshold (ANSI A vs B)
3. Bootstrap confidence band on the HC distribution
4. **Sobol-like variance decomposition of HC across (placement, capacity, threshold, load) factors**
5. Sensitivity envelope of HC over (Range A vs Range B vs custom)
6. Time-of-day-conditional HC (load profile time slicing)
7. Threshold-as-CDF (inverse problem: "threshold for HC=5 MW")
8. Insurance-actuarial framing: HC as premium-rated event count distribution
9. Renewable capacity-factor uncertainty Monte Carlo
10. **Standards-equivalence theorem: when do Range A and Range B give statistically indistinguishable HC?**
11. Cross-feeder universality: does the HC distribution shape transfer?
12. Rank correlation between metric variants (Spearman across realizations)

> ranking しない。人間 (= プロジェクトオーナー視点での一次選別役) が読んで non-obvious なものを選ぶ。

---

## 3. Rule 2 (Ordinary Persona)

「電力系専門家」「Steve Jobs」を避け、無関係職業で考え直す:

- **保険のアクチュアリー**: HC の分布をリスク事象の累積分布として扱い、premium rating の感度分析手法 (Sobol indices) を直接転用
- **農業の品種改良者**: 多変量の遺伝子型 × 環境 (G × E) 交互作用 ANOVA 分解の枠組みを HC × 閾値 × load profile に転用
- **ANSI 規格改訂委員会の委員長**: 「どの uncertainty を**先に**標準化すれば最大の HC 信頼性向上が得られるか?」を直接問題化

3 persona すべてが「**variance decomposition by factor**」に収束するのは偶然ではなく、これは confidence in the answer に近い (= cross-disciplinary insight, Rule 3 step 4)。

---

## 4. Rule 3 (CoT 4 ステップ)

### Step 1: 問題構造の分析

矛盾:
- **A**: HCA を信頼できる定量指標として標準化したい
- **B**: しかし複数の uncertainty source (load, threshold, placement, capacity) が同時にあり、結果が揺れる

これは「結論の信頼性 vs 入力の不完全性」の矛盾。

### Step 2: 隣接分野の列挙 (5+)

この矛盾構造が出現する分野:
- **(i) 気候モデリング**: GCM ensemble の不確実性を "model variance vs scenario variance vs internal variance" に分解 (Hawkins & Sutton 2009)
- **(ii) 遺伝学 GWAS**: phenotype 分散を遺伝・環境・GxE 相互作用に分解 (heritability)
- **(iii) 工学品質管理**: Taguchi parameter design — control vs noise factors の variance contribution
- **(iv) 経済予測**: ANOVA decomposition of forecast error by source
- **(v) 数値天気予報**: ensemble spread decomposition by perturbation type
- **(vi) ロボット制御**: parameter sensitivity for robust control via Sobol indices

### Step 3: アナロジー生成

各分野の解法:
- (i) Hawkins-Sutton variance fraction plot (scenario uncertainty が先に支配的、後に internal variance) → **時間軸ではなく feeder type 軸で同等プロット**
- (ii) Heritability h² = Var(G) / Var(P) → **HC heritability h²_threshold = Var(threshold) / Var(HC)**
- (iii) Taguchi: signal-to-noise ratio per factor → "robust HC under threshold drift"
- (iv) ANOVA F-test の p-value で factor 重要度 → 「threshold は HC に統計的有意か?」
- (vi) Sobol first-order index = factor X による出力分散の説明割合

### Step 4: 最遠アナロジー選択

**気候モデリング (Hawkins-Sutton 2009)** が最も意外。電力系 HCA 文献で「climate variance decomposition framework を移植」した先行は (調査範囲では) 見当たらない。これは Sobol indices より "fraction-of-uncertainty" 的に直感的で、規格委員会が読みやすい (= Persona 3 「ANSI 委員長」と整合)。

---

## 5. Rule 4 (Extreme User)

| 極端ユーザー | amplified need |
|---|---|
| **ANSI 規格改訂委員会委員長** (1) | "どの uncertainty を**最初に**標準化すれば 80% の HC 信頼性回復になるか" — Pareto principle 適用、actionable |
| **配電事業者の HCA レビュアー** | "受領した HCA レポートの数値が threshold 選択と load profile 選択でどれくらい揺れたか、報告書からは読めない" — 透明性要求 |
| **保険会社の DER アグリゲータ向け商品開発者** | "HC を underwriting limit として使うとき、どの uncertainty が premium 計算を支配するか" — 経済価値化 |
| **PhD 学生** (10年 1 feeder) | "feeder 固有の HC 不確実性 fingerprint が分かれば、新規測定の優先順位が決まる" |

ANSI 委員長 persona が **最も actionable な output 形** (= "標準化優先度ランキング") を要求している。これを論文の "Practical Relevance" 部に直結させる。

---

## 6. Rule 5 (TRIZ — 妥協なし)

Trade-off候補:
- ❌ "計算コスト vs 不確実性の網羅性" — Sobol/Hawkins-Sutton は full grid 不要 (subsample から推定可)
- ❌ "feeder 一般性 vs 個別精度" — feeder type 軸で stratified analysis すれば両立
- ✅ **AもBも**: 単一 metric (HC) に対して、4 factor (placement, capacity, threshold, load) の variance contribution を **同一実験から** 同時に算出 (factorial ANOVA decomposition)

「精度を犠牲にせず網羅性を上げる」: 各 factor を独立にサンプリングするのではなく、**factorial design** にすることで全 factor 効果を 1 sweep で得る。

---

## 7. Rule 6 (Fixation 監視)

過去 try1〜try7 の系列:
- try1: deterministic baseline (PV penetration sweep)
- try2: stochastic placement
- try3: 2 feeders comparison
- try4: 3 thresholds × 3 plugins (= **threshold sweep**)
- try5: HCA-R (= threshold robust averaging) ← 同方向
- try6: HCA-R 2 feeders (= 同上 × multi feeder) ← 同方向
- try7: HC₅₀ (= threshold curve quantile) ← 同方向 (3 連続 → §2.5 強制転換ライン)

try9 は **「HC(θ) 曲線の統計量」軸を完全に放棄** し、**「variance decomposition by factor」** に転換する。これは fixation 打破に該当 (= Rule 6 適合)。

---

## 8. Novelty Gate (実験前審査)

| # | チェック | 判定 | 根拠 |
|---|---|---|---|
| 1 | 既存 metric / 手法から自明に導けるか | ✅ 自明でない | HCA 文献では (placement, capacity) の sweep は標準だが、(threshold, load profile) も同 grid に入れて variance decompose する設計は調査範囲では見当たらない |
| 2 | 先行文献に同等概念があるか | ✅ ない | "HCA + Sobol" は ScienceDirect / MDPI / arxiv 2024-2025 の検索範囲内で hit せず (try9 報告で具体引用) |
| 3 | 物理的に解釈可能か | ✅ Yes | Sobol first-order index = "factor X を固定したら HC 分散の何 % が消えるか" (intuitively interpretable) |
| 4 | "So what?" テストに耐えるか | ✅ Yes | 「threshold 選択が HC 分散の N % を占めるなら、ANSI 委員会は threshold standardization を最優先すべき」と 1 文で言える |
| 5 | Cross-disciplinary insight | ✅ Yes | Hawkins-Sutton (気候モデリング) フレームワークを HCA に移植 |
| 6 | 計算手法自体に innovation | ✅ Marginal | Sobol 自体は既知だが、**factor 設計自体** (placement / capacity / threshold / load の cartesian factorial) と「standards prioritization output」が新規 |

**6/6 通過** → 実験フェーズに進む。

---

## 9. 確定した研究問題

> **2 つの標準配電フィーダー (CIGRE LV, CIGRE MV) における stochastic Hosting Capacity 分散を、PV 配置・PV 容量・電圧違反閾値・負荷プロファイルの 4 factor に variance decomposition し、規格委員会向けの「先に標準化すべき factor」優先度ランキングを与える。**

### 副題候補

- "Variance attribution of distribution Hosting Capacity uncertainty: which standard should we write first?"
- "Sobol-style decomposition of HC uncertainty across CIGRE LV and MV feeders"
