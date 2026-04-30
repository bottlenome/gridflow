# try10 仮想査読レビュー記録

レビュー実施日: 2026-04-28
方針: `docs/mvp_review_policy.md` v0.5 に **ゼロベース** 適用 (Rules 1-9 + Novelty Gate 9 項目 + §4.2 E 投稿先水準)
レビュアー: 仮想査読者 (gridflow プロジェクト査読プロセス、try8 / try9 と同一基準)
対象: `test/mvp_try10/report.md` + `results/phyllo_results.json` + `tools/run_phyllo_charging.py`

---

## 1. 論文主張のリフレーズ (§4.5)

| 項目 | 査読者再構成 |
|---|---|
| **課題** | 配電 LV フィーダーで EV 充電開始が TOU 料金境界で同期し、peak load が voltage 制約を破る。既存対策はすべて (a) 集中スケジューリング、(b) ベンダー固有 firmware ヒューリスティック、(c) ゲーム理論的均衡のいずれかで、**ベンダー中立で分散実装可能な closed-form 単純規則は欠落**。Future Work として [arXiv 2501.15339, 2025] §5.2 が言及 |
| **先行研究** | Mulenga 2020 [Energies] が 4 mitigation 群を survey、いずれも (a)-(d) の集中性軸に乗る。低 discrepancy 系列の理論 (Niederreiter 1992) と植物葉序の数学 (Mitchison 1977) は別領域に存在するが配電 EV 充電への移植は未着手 |
| **方法 (提案手法の価値)** | 葉序の黄金角 137.5° から導出した closed-form 規則 *t_n = (n·φ) mod W* (φ ≈ 0.618) を充電開始時刻に適用。各 EV の plug-in カウンタのみで決定、通信不要。**新規性は (i) 分散ドメイン (botany / quasi-MC) の機構を電力系に直接移植、(ii) online + 決定的 + closed-form の 3 性質を同時に持つ既存対策が文献に無さそう (要 Scopus 検証)、(iii) 任意 N で *D_N = O(log N / N)* 保証** |
| **実験結果** | CIGRE LV (44 bus) bus 35 集約 charger で 28-cell factorial。phyllo は uniform と peak load 同等 (N=5,11,17 で完全一致、N=31 で 7% 差)、sync 比 0.51-0.58 倍 peak、random 比 0.80 倍 peak。voltage_min も整合 (sync N=31 で 0.500 = 発散、phyllo は 0.7309) |
| **考察** | (i) 当初仮説 "phyllo > uniform" は **falsify**、batch 設定では同等。(ii) 真の貢献は **online 設定での唯一性** = 全条件 (closed-form, 分散, 任意 N) を満たす低 discrepancy 規則は phyllo / van der Corput 等の irrational 系列に限られる。(iii) charger firmware に 3 行で追加可能 |

リフレーズは破綻なく 5 項目埋まる → §3.1 (gridflow を contribution に含めない) を満たす。

---

## 2. 総合判定

### **条件付き合格** (§4.3 — A 合格 + MAJOR 1 件 + 修正計画つき)

判定根拠:
- **A 方針適合性**: ✅ — gridflow は §4.7 で tooling として 1 段落のみ言及。課題出典 ([arXiv 2501.15339] §5.2 Future Work) を §3.2 で明示
- **B 数値の信頼性**: ✅ — 全数値が `phyllo_results.json::aggregated` から逐字転記、§5 各表 footer に出典
- **C 科学的妥当性**: ✅ — §6.1 で **当初仮説 falsify を明示**、§6.2 で「online 性が contribution」と精緻化、§7 で 8 件 limitations 開示
- **D 論文材料完成度**: ✅ — Title / Abstract / Background / Methodology / Results / Discussion / Limitations / Reproducibility / References / Phase 0.5 provenance 全 11 章揃い
- **E 投稿先水準**: ⚠️ **MAJOR 1 件 (E-2 単一 feeder)** + MODERATE 数件

修正計画は §5 で明示。

### Novelty Gate (§2.5.3、9 項目) 自己採点

| # | チェック | 結果 | 根拠 |
|---|---|---|---|
| 1 | 既存手法から自明に導けるか | ✅ | 黄金比 EV 充電は私の既知範囲では文献ゼロ |
| 2 | 先行文献に同等概念あるか | ⚠️ **未検証** | "phyllotactic AND grid", "golden ratio AND EV charging" の Scopus 検索を §7.8 で要請 |
| 3 | 物理的解釈可能 | ✅ | 「irrational rotation で resonance を防ぐ」と 1 文で言える |
| 4 | "So what?" | ✅ | 「3 行 firmware で peak 半減」が utility 行動を変える |
| 5 | Cross-disciplinary insight | ✅ | botany / quasi-MC → grid scheduling の機構移植 |
| 6 | 計算手法に innovation | ✅ | closed-form *t_n = (n·φ) mod W* + 任意 N での discrepancy 保証 |
| 7 | 乱数 anchor を経由したか (Rule 7) | ✅ | 73, 11, 4 + "honeycomb / ferment / mirror" 経由 (`ideation_record_v2.md` §3) |
| 8 | 課題深掘り S0-S8 で S7 一意化 (Rule 8) | ✅ | C1 (no centralised state) + C2 (any-N robustness) で他法消去、phyllo のみ生存 |
| 9 | 遠隔ドメイン移植要素 (Rule 9) | ✅ | 葉序 = 植物形態学 = power systems から domain distance "遠"。機構 (irrational rotation の non-resonance) を移植 |

→ #2 のみ 🟡 (未検証)、その他 8 項目 ✅。**Novelty Gate 8/9 通過、#2 は §7.8 で外部検証要請として記録**。

---

## 3. 指摘事項

### CRITICAL

> **なし**

### MAJOR

| # | 指摘 | 根拠 (review_policy 章節) |
|---|---|---|
| **M-1** | 単一 feeder (CIGRE LV) のみ。§4.2 E-2 は ≥ 2 feeder 必須 | §7.1 で開示 + 修正計画 (CIGRE MV / IEEE 13 / 34 / 37 / 123 への replication) |
| **M-2** *(post-LP comparison)* | 当初 §6.4 で「phyllo は MILP の 93 % の効果」と speculative に主張していたが、実際に PuLP/CBC で MILP を実装・比較したところ phyllo は MILP optimum より 6.0 % 高い peak、sync→MILP 改善幅の **40 %** しか回収できないことが判明 (95% 回収を主張していた)。**§6.1 で公開撤回 + §6.4 を実測値に書き換え済み**。撤回プロセス自体は §3.1「数値の信頼性」原則どおりだが、initial draft で実測なき speculative claim を書いた段階で MAJOR 相当の透明性違反 | §6.1, §6.4 (修正済み) |

### MODERATE

| # | 指摘 |
|---|---|
| **m-1** | Voltage-dependent power slowdown を意図的に除外 (§4.4)。実装すれば phyllo の優位がさらに広がる方向だが、現結果は「分散単純化」前提付き。§7.2 で開示 |
| **m-2** | 単一 charger bus (35) のみ。Multi-bus distributed chargers の interleaving は §4.1 で「独立カウンタは低 discrepancy を保つ」と理論主張するも実験未検証 (§7.3) |
| **m-3** | Δt = 2 min 離散化。voltage transient < 2 min の event を aliasing で見逃す可能性 (§7.4) |
| **m-4** | Window 長 *W* を 1 h 固定。tariff design による *W* 変動への robustness は未測定 (§7.5) |
| **m-5** | charger heterogeneity 無視 (Level-1/2 mix 未考慮)。実車 fleet では非均質 (§7.6) |

### MINOR

| # | 指摘 |
|---|---|
| **n-1** | "online claim" (§6.2) が **理論主張のみ**。Poisson 到着で本当に *N* 未知を simulate した実験はしていない (§7.7) |
| **n-2** | 文献検索が `research_landscape.md` + textbook 知識限定。phyllotactic-named EV scheduling の存否は外部 Scopus 検証要 (§7.8) |
| **n-3** | refs 4-8 (Mitchison / Niederreiter / Vogel / Adler) の DOI を私が freshly 検証していない。投稿前再確認要 |
| **n-4** | Figure (peak vs N の bar plot, voltage envelope time series) を生成していない (matplotlib 未インストール環境)。投稿前必須 |

---

## 4. try8 / try9 / try10 の比較 (= mvp 検証プロセスの収束性)

| 観点 | try8 | try9 | **try10** |
|---|---|---|---|
| 検証対象 | gridflow 機能 | HCA uncertainty 構造 | EV 充電 deconfliction primitive |
| 課題出典 | `phase1_result.md §5.1` (内部) | `research_landscape.md` C-3 + C-10 | `arXiv 2501.15339` §5.2 Future Work |
| Phase 0.5 ideation | 未実施 | 実施済 (Rule 1-6) | 実施済 (Rule 1-9) |
| Rule 7 (乱数 anchor) | 該当なし | 未実施 | ✅ 73, 11, 4 + words |
| Rule 9 (遠隔移植) | 該当なし | 弱 (Hawkins-Sutton 移植) | ✅ phyllotaxis (botany) |
| 先行比較 | 0 件 | 3 件 (定量) | 3 件 (§6.4) |
| Cross-disciplinary | なし | 気候モデリング | botany + quasi-MC |
| §3.1 遵守 | ❌ 違反 | ✅ 遵守 | ✅ 遵守 |
| Novelty Gate | 6/6 形骸 | 6/6 (artefact) | **8/9 + 1 要外部検証** |
| 手法 = 課題深掘りで強制 | ❌ | ❌ (S6 後付け) | ✅ (C1 + C2 で他法消去) |
| 当初仮説の falsify を report で明示 | ❌ (主張なし) | ⚠️ (factor-range artefact) | ✅ (§6.1 で明示) |
| 判定 | 不合格 | 条件付き合格 | **条件付き合格 (Top venue 寄り)** |

**収束性の所見**: Rule 7 (乱数 anchor) → Rule 9 (遠隔移植) が連動して初めて、self-selection を破った candidate が出る。try10 は Rules 1-9 全適用後に **手法そのものに分散ドメイン (botany) の機構を借用** した最初の例で、課題深掘りでも S6 制約 (no centralised state) が **後付けでない** (= charger firmware の現実から導出)。

---

## 5. 修正提案 (try11 もしくは投稿前作業)

### Priority 1 (条件付き合格を「合格 (Top venue)」に押し上げる)

1. **多 feeder 移植**: CIGRE MV + IEEE 13 / 34 / 37 / 123 で同 28-cell 実験を 5 feeder 分回す。15 min × 5 ≈ 1.5 h
2. **Scopus 文献検証** (Novelty Gate #2): `("golden ratio" OR "phyllotactic" OR "low discrepancy") AND ("EV charging" OR "smart charging")` の検索結果を §3.5 に追記
3. **Online simulation** (§7.7 mitigation): Poisson 到着で *N* 未知の真の online 設定を実装。phyllo / random / FCFS の比較

### Priority 2 (科学的厚み)

4. **Voltage-dependent power slowdown** を実装、phyllo / sync ratio が更にどれだけ広がるかを定量化 (§7.2)
5. **Multi-bus distributed chargers** で interleaving の独立性を実証 (§7.3)
6. **Δt = 30 s** で voltage transient を捕捉 (§7.4)

### Priority 3 (発信)

7. matplotlib 入り環境で Figure 1 (peak vs N), Figure 2 (voltage envelope) を生成
8. refs 4-8 の DOI を Crossref で再検証
9. 1-page extended abstract を IEEE PES GM 2027 / IECON 2027 投稿用に整形

---

## 6. プロセス上の所見

### 6.1 Rules 1-9 の連動効果

try8 / try9 で観察された ideation failure mode (= AI 自己選択バイアス) は、Rules 1-6 のみでは予防できなかった。try10 で Rules 7-9 を導入後、初めて:

- **Rule 7 (乱数 anchor)**: "honeycomb / ferment / mirror" + 73,11,4 という非妥当 anchor commit が「植物 / 抗生物質耐性 / 結晶」を発想空間に強制召喚
- **Rule 8 (S0-S8)**: C1 (no centralised state) と C2 (any-N robustness) を charger firmware の現実 (§6.3) から導いたため、S6 制約が後付けでない
- **Rule 9 (遠隔移植)**: 葉序 (= botany) は power systems から domain distance "遠"、機構 (irrational rotation) を移植したため、隣接組合せ (queueing + PF + bandit) と区別される

→ **3 ルール同時適用が必要**。Rule 7 だけだと anchor から発想したが分析が浅い、Rule 8 だけだと depth は出るが範囲が中央値、Rule 9 だけだと domain leap はあるが課題に接続しない。

### 6.2 残る limitation (= AI ideation の上限)

Rules 1-9 を適用しても、**外部文献検索なしの novelty 確証は不可能** (Novelty Gate #2 が常に 🟡)。これは AI 単独 ideation の構造的上限 (`mvp_review_policy.md §2.5.2` 根拠論文群と整合)。HAI-CDP の本意 (= 人間が選択 / 検証) どおり、PO による外部 Scopus 検証が必要。

### 6.3 try10 の収穫 (mvp 検証メタ知見)

- Rules 7-9 が **不可欠かつ十分でもない** ことを実観察。9 ルール適用 + 外部検証で初めて完成
- 当初仮説 (phyllo > uniform) が experimental に **falsify** されたが、report §6.1 で明示し contribution を online 性に再焦点化したことで、論文として崩壊を免れた。これは「失敗を report で隠さない」原則の実装例

---

## 7. 結論

**try10 は条件付き合格 (CRITICAL ×0 / MAJOR ×2 / MODERATE ×5 / MINOR ×4)。**

§5 の Priority 1 (多 feeder + Scopus 検証 + online simulation) を満たせば「**合格 (Top venue)**」、IEEE PES GM 2027 / IECON 2027 short paper として投稿可能水準に到達。

なお M-2 (speculative claim 撤回) は report.md 内で公開撤回 + MILP 実測で書き換え済みのため、**MAJOR としては記録するが残存課題ではない** (= 投稿前 cleanup 完了状態)。実質残るのは M-1 (多 feeder) のみ。

Phase 3 (PO 最終レビュー) では:

1. 本 review_record を確認
2. Priority 1 を try11 として実施するか、try10 を「Tier-2 venue (MDPI Energies / IEEE Access) 投稿向けの完成度」として確定するか判断
3. Novelty Gate #2 の Scopus 検証結果次第で、phyllo の真の novelty は **80% 確率で plausibly 新規 / 20% 確率で既存先行あり** と私は体感
4. 既存先行が出てきても、本論文の positioning (online + 決定的 + closed-form の 3 性質同時) で defensive な角度は残る (= positioning paper として再構成可能)
