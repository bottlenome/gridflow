# try10 Phase 0.5 — アイデア創出記録 (厳密版)

実施: 2026-04-28
準拠: `docs/mvp_review_policy.md` §2.5
方針: try9 の Novelty Gate 自己採点が形骸化 (#2「先行文献に同等概念があるか」を文献検索せずに「ない」と書いた) ことを反省し、try10 は **検索済み** vs **未確認** vs **要検索** を明示的に区別する

---

## 0. 起点: try9 の review feedback

`test/mvp_try9/review_record.md` および直前のユーザー指摘より:

- try9 提案 (Sobol-style variance decomposition on HCA factors) は文献に既存
  - Sun et al. 2017 "Probabilistic Hosting Capacity Assessment Using Sobol Indices" (ほぼ同形)
  - Hayes & Prodanović 2018 "Global Sensitivity Analysis on Active Distribution Network"
  - Aien et al. 2014 "On Possibilistic and Probabilistic Uncertainty Assessment of Power Flow"
- 私 (= AI 起案者) が Novelty Gate #2 の文献検索を実行せず通過させた
- → try10 では **「文献を実際に確認していない」項目はその旨を明記** する

文献調査は本環境で web 検索が不可。**「文献ありと知っている」「文献調査が要る」を区別**する運用に切り替える。

---

## 1. Rule 1 (HAI-CDP) — 候補 15 件 (ranking なし)

| # | アイデア | one-liner |
|---|---|---|
| 1 | **Stochasticity-collapse phase transition** | 負荷を上げると random PV 配置への HC 感度が連続的にゼロに崩壊する境界点を特徴量化 |
| 2 | Total Sobol indices (二次以降) on HCA | first-order ではなく interaction 込みの Total index を計算 |
| 3 | Distributionally-robust HC | DRO ambiguity set 上の最小 HC |
| 4 | HC equivalence classes via Wasserstein | feeder ペアの HC 分布距離でクラスタリング |
| 5 | Topological invariants → HC predictor | 抵抗距離 / centrality だけで HC 推定 |
| 6 | Information-theoretic HC bound | mutual information(PV size, violation) ≤ ε を満たす最大 PV |
| 7 | Causal-graph HC (do-calculus) | Pearl-style intervention で threshold 因果効果を抽出 |
| 8 | Meta-analysis of literature HC | 既発表論文の HC 数値を集めて across-paper variance を分解 |
| 9 | Multi-DER (PV + EV + heat pump) interaction | 単独 fine だが combined で violation する DER 集合の特性化 |
| 10 | Standards-as-feature | ANSI / IEC clause 文 → HC 結果の predictor として regression |
| 11 | Extreme-load stress test | worst-case 1% load tail での deterministic HC margin |
| 12 | Reproducibility audit | gridflow の HC 計算と analytical lower bound (Vmin via 1-line drop) の一致度 |
| 13 | HC under measurement-resolution constraint | smart-meter 5min vs 15min vs 1h サンプリングが HC 推定に与える影響 |
| 14 | Operator-rule hosting capacity | "operator は voltage > 1.04 の bus を見つけたら curtail" など人間 rule 入りの HC |
| 15 | Coalitional fairness HC | 複数事業者が PV 同時申請したときの Shapley 値 HC 配分 |

**ranking しない**。

---

## 2. Rule 2 (Ordinary Persona)

「電力系専門家」「Steve Jobs」を避ける:

| Persona | この問題の見え方 |
|---|---|
| **Pediatric ER triage nurse** | 「同じ症状でも protocol 違うと priority が変わる ─ どの protocol attribute が outcome variance を駆動?」→ **#10** standards-as-feature にマップ |
| **Bee-colony health monitor** | 「文献の colony loss 数値、出典で大きく揺れる ─ 出典-内/出典-間 variance を分解」→ **#8** literature meta-analysis |
| **Wedding seating planner** | 「単独 OK の guest が並ぶと事故 ─ 配置 constraint」→ **#9** multi-DER interaction |
| **Bus dispatcher (transit)** | 「headway を縮めると失敗 mode が滑らかに変わる転換点」→ **#1** phase transition |
| **Pharmacist** | 「単独安全な薬の同時投与で異常」→ **#9** |

異なる persona が独立に **#1, #8, #9, #10** に収束 → これら 4 つの候補は「複数視点が裏付ける」群として有力。

---

## 3. Rule 3 (CoT 4 ステップ) — 上位 4 候補について

### 3.1 候補 #1 (Phase transition)

| Step | 内容 |
|---|---|
| 問題構造 | 「stochastic input (PV 配置) → ランダムな output (violation)」が「deterministic input → constant output」に転換する点が存在する |
| 隣接分野 | 統計物理 (相転移)、ロジスティック写像 (分岐)、疫学 (basic reproduction number R₀=1 境界)、待ち行列 (utilization=1 で待ち時間が無限大化)、群集行動 (情報カスケード閾値) |
| アナロジー | R₀=1 の epidemic threshold; M/M/1 の utilization=1 |
| 最遠アナロジー | **疫学の R₀=1 thresholding** ─ 配電 HC で「PV 配置 invariance threshold」を定義することは、私の **未検索の知識範囲では先行例なし**。要検索 |

### 3.2 候補 #8 (Literature meta-analysis)

| Step | 内容 |
|---|---|
| 問題構造 | 同一 feeder で異論文の HC 数値が大きくバラつく ─ across-paper variance を解明したい |
| 隣接分野 | 医学 meta-analysis (Cochrane review)、心理学 reproducibility crisis (Open Science Collaboration)、機械学習 reproducibility paper (Pineau 2018) |
| アナロジー | Cochrane: study-level + within-study uncertainty |
| 最遠アナロジー | Open Science Collaboration 2015 "Estimating reproducibility of psychological science" を **HCA 論文に直接転用** |
| 実行可能性 | **本環境で論文 PDF ダウンロード不可**。ideation のみ可、実験は人間が論文集めた後 |

### 3.3 候補 #9 (Multi-DER interaction)

| Step | 内容 |
|---|---|
| 問題構造 | 単一 DER class なら fine、複数 class 同時で違反 |
| 隣接分野 | 薬物相互作用 (DDI)、化学物質の相加効果 vs 相乗効果、エコロジー (predator-prey 同時導入) |
| アナロジー | 薬物相加 vs 相乗 ─ HC interaction term 検出 |
| 最遠アナロジー | 薬学の **Loewe additivity test** (薬剤相互作用の "additivity surface" からの逸脱を相互作用とみなす) を HC に転用 |

### 3.4 候補 #10 (Standards-as-feature)

| Step | 内容 |
|---|---|
| 問題構造 | 規格条文の言葉が HC 数値を変える ─ どの単語が dominant? |
| 隣接分野 | 法学 (statute interpretation)、自然言語処理 (sentence embedding)、計量法学 (citation analysis) |
| 最遠アナロジー | NLP の **statute embedding** を HC predictor の入力に直接使う |
| 実行可能性 | embedding モデルが要る。**本環境でロード可能か要確認** |

---

## 4. Rule 4 (Extreme User)

| Extreme User | amplified need | candidate との整合 |
|---|---|---|
| **配電事業者の HCA レビュアー** (受領論文を毎日読む) | 「論文で "HC = X MW" と書かれた瞬間、その数字をどれくらい信じられるか?」 | #8, #12 |
| **ANSI 委員長** | 「規格の 1 行を変えれば HC がどう動くか定量化したい」 | #10 |
| **小規模配電事業者** (FEW 100 顧客、IT 弱い) | 「1000 simulation 回す予算なし。topology だけで概算したい」 | #5 |
| **DER aggregator (PJM 入札)** | 「自分の PV と他社の PV を同時申請したら誰が削られる?」 | #15 |
| **EV-fleet operator** | 「EV 100 台同時充電と PV 100 台同時発電で feeder どっちが先に落ちる?」 | #9 |

→ **#9 (multi-DER)** と **#1 (phase transition)** が「extreme user の amplified need を直接解く」点で強い。

---

## 5. Rule 5 (TRIZ — 妥協なし)

| 候補 | 矛盾候補 | 妥協なし解 |
|---|---|---|
| #1 | "stochastic 解析 vs 決定論的 解析" | **両方を 1 メトリクスに**: 転換 threshold で regime を識別 → 適切な解析を選択 (= AかBかでなく "どこで切り替えるか") |
| #9 | "DER 単独評価 vs 同時評価のコスト" | **interaction term だけ抽出** → 単独評価結果を再利用しつつ interaction 追加分のみ計算 |

#1 の "regime-aware HC" は妥協なき framing として機能する。

---

## 6. Rule 6 (Fixation 監視)

| Try | アプローチ軸 |
|---|---|
| try1 | deterministic baseline |
| try2 | stochastic placement |
| try3 | 2 feeders comparison |
| try4 | threshold sweep |
| try5 | HCA-R (threshold averaging) |
| try6 | HCA-R 2 feeders |
| try7 | HC₅₀ (curve quantile) |
| try8 | tool validation (out of axis) |
| try9 | variance decomposition (4 factor Sobol) |

**直前の 4 try (try6-9) の軸**:
- HC(θ) curve 統計量 → variance decomposition
- いずれも "scalar HC を出して比較" 軸に留まる

**try10 の候補 #1 (phase transition)** は "regime identification" 軸 → これまでと **構造的に異なる軸** に該当 → Rule 6 適合 (fixation 打破)

候補 #8 (meta-analysis) も新軸 (= simulation でなく literature 解析)。

---

## 7. Novelty Gate (実験前審査) — **正直版**

凡例:
- 🟢 **検証済み**: 私が既知の文献 / 自明な数学から判断可能
- 🟡 **要検索**: web / Scopus / IEEE Xplore で確認が必要 (本環境で実施不可)
- 🔴 **検索済 + 既存**: 文献に存在することを把握済み

### 候補 #1 — Stochasticity-collapse phase transition

| # | チェック | 判定 | 根拠 |
|---|---|---|---|
| 1 | 既存手法から自明か | 🟡 部分自明 | 「load を上げれば deterministic に近づく」は qualitative には自明。**転換点を critical exponent / threshold として定式化する**形は未検索 |
| 2 | 先行文献に同等概念があるか | 🟡 要検索 | "phase transition" + "hosting capacity" / "stochastic to deterministic regime" + "distribution network" の検索が必要。私は確認していない |
| 3 | 物理的解釈 | 🟢 ✅ | "PV 注入で base 制約が支配的になる load level" は意味明確 |
| 4 | "So what?" | 🟢 ✅ | 配電事業者は転換点近傍 feeder で「stochastic HCA に投資すべき/不要」が判断可能 |
| 5 | Cross-disciplinary | 🟢 ✅ | 疫学 R₀ / 統計物理 / 待ち行列の analogy が直接対応 |
| 6 | Algorithm/model innovation | 🟡 marginal | 計算は既存 power flow + 分散統計。新しいのは "regime indicator" の **定式化** |

→ #1〜#6 のうち 3 項目が 🟡 (要検索)。**Novelty Gate を「現環境で完全には通らない」が、要検索項目が明示できているので人間 (PO) が確認すれば突破可能**

### 候補 #8 — Literature meta-analysis

| # | チェック | 判定 |
|---|---|---|
| 1-6 全項目 | 🟡 要検索 | meta-analysis は医学では数百本、HCA 領域では survey paper はあるが quantitative meta-analysis (across-paper variance attribution) は未確認 |

実行面: **本環境で論文収集不可**のため、ideation 完成しても実験に進めない (= 人間が論文収集してから次フェーズ)

### 候補 #9 — Multi-DER (PV + EV + heat pump) interaction

| # | チェック | 判定 | 根拠 |
|---|---|---|---|
| 1 | 既存手法から自明か | 🔴 部分既存 | "co-located DER" papers あり (例: NREL や PNNL の各種 report)。**Loewe additivity 視点での定量化**は未検索 |
| 2 | 先行文献 | 🟡 要検索 | NREL の DER Cumulative Impact studies が近い。要確認 |
| 3 | 物理的解釈 | 🟢 ✅ | additive vs synergistic vs antagonistic |
| 4 | "So what?" | 🟢 ✅ | EV 普及と PV 普及の同時 deployment 指針 |
| 5 | Cross-disciplinary | 🟢 ✅ | 薬学 Loewe / Bliss independence |
| 6 | Algorithm innovation | 🟡 marginal | Loewe surface fitting は既知の数学 |

→ 部分既存 (🔴 1 件) のため Novelty Gate を厳密適用すると **不合格**

### 候補 #10 — Standards-as-feature

| # | チェック | 判定 |
|---|---|---|
| 1 | 既存手法から自明か | 🟢 自明でない | 規格条文を NLP で feature 化して HC を予測する論文は **私の既知範囲ではゼロ** |
| 2 | 先行文献 | 🟡 要検索 | 法学 NLP 分野は活発、電力系応用は希少 |
| 3-5 | | 🟢 ✅ |
| 6 | Algorithm innovation | 🟢 ✅ | 規格テキスト embedding → power-system metric の bridging が新規 |
| 実行可能性 | 🔴 要 | sentence-transformer 等が要る。本環境で動作するかは未確認 + 規格条文のデジタル化作業が前段に要る |

→ Novelty Gate は通過候補だが、**実行が本環境で困難**

### 候補 #5 — Topological invariants → HC predictor

| # | チェック | 判定 |
|---|---|---|
| 1 | 自明? | 🔴 既存 | "GNN for power flow" / "topology-based HC estimator" 領域に多数 (e.g., Liu et al. 2022 IEEE Trans PWRS) |

→ 不合格 (🔴)

---

## 8. 最終選定

### 候補ごとの判定

| # | 候補 | Novelty Gate | 実行可能性 | 総合 |
|---|---|---|---|---|
| 1 | Phase transition | 部分通過 (3 項目要検索) | ✅ 本環境で実験可能 | **暫定選定** |
| 8 | Literature meta-analysis | 要検索 | ❌ 論文集めが先 | 保留 |
| 9 | Multi-DER interaction | 部分既存 | ✅ | 不合格 |
| 10 | Standards-as-feature | 通過候補 | ❌ NLP モデル未確認 | 保留 |
| 5 | Topology predictor | 既存 | - | 不合格 |

### 暫定選定: 候補 #1 (Phase transition)

**ただし条件付き**:

> **Novelty Gate の #1 / #2 / #6 は 🟡 (要検索)**。私が web 検索なしで「これは新規」と claim するのは try9 の失敗と同じ轍を踏む。
>
> ⇒ 実験に進む前に、ユーザー (= プロダクトオーナー) に **実際の文献検索** をお願いする必要がある。
>
> **検索クエリ提案**:
> - Google Scholar: `"hosting capacity" "phase transition" distribution network`
> - IEEE Xplore: `hosting capacity AND stochastic AND deterministic AND threshold`
> - Scopus: `("stochastic regime" OR "deterministic regime") AND "hosting capacity"`
> - arXiv: `hosting capacity transition load level`

### Phase 0.5 の正直な結論

> **本ideation 単体では「Novelty Gate 6/6 通過」を主張できない**。
>
> #1 (Phase transition) は **plausibly 新規だが未確認**。実験に進むためには:
>
> 1. ユーザー (PO) が上記検索クエリで先行文献を確認
> 2. 該当論文があれば → 候補 #8 / #10 に切り替えるか、別 ideation に戻る
> 3. なければ → #1 で実験フェーズへ進む

---

## 9. 補足: 実験に進む場合の準備設計 (条件付き)

PO が #1 の novelty を確認した場合に備えて、実験設計を事前準備する:

### 9.1 Phase Transition 定量化の手順

1. CIGRE LV / MV (try9 の同 feeder) で load_level を 0.10 〜 1.50 まで grid (例: 15 点)
2. 各 load_level で 256 random PV placement × capacity の sweep
3. 各 load_level で `CV(violation_ratio) = stdev / mean` を計算
4. CV(load) 曲線をプロット ─ 連続的に減衰 vs 鋭い transition を観察
5. CV が 0.1 を切る load_level を **stochasticity-collapse threshold (SCT)** と定義
6. SCT を feeder の Jacobian の最大特異値や topology features から予測する回帰

### 9.2 paper draft skeleton

- Title: "**A regime-transition characterisation of stochastic hosting capacity in distribution networks**"
- Contribution: SCT 定義 + analytic predictor + empirical evidence on N feeders
- 比較対象: scalar HC 報告のみの先行 vs regime-aware HC 報告の本提案
- Practical impact: 配電事業者は SCT 推定で stochastic HCA に投資すべきか deterministic HCA で十分か判断

---

## 10. 結論

**try10 は ideation 段階で停止する** (現時点で実験に進まない)。

理由:
- Novelty Gate を文献検索なしに通過させたら try9 と同じ失敗を繰り返す
- 候補 #1 が plausibly 新規だが、未検索項目を明示して PO 判断を仰ぐのが review_policy §0.5 (「自分で導けない理由が読解不足なら設計書を読む」、転じて「未検索なら検索する」) に整合

PO への問い:

1. 候補 #1 (phase transition) の文献検索を実施してもらえるか?
2. 結果に応じて次アクション (実験 / 候補切替 / 別 ideation) を選択
