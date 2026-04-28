# try9 仮想査読レビュー記録

レビュー実施日: 2026-04-28
レビュー方針: `docs/mvp_review_policy.md` v0.4 ゼロベース
レビュアー: 仮想査読者 (gridflow プロジェクト査読プロセス、try8 と同一基準)
対象: `test/mvp_try9/report.md` + `results/decomposition.json` + `results/raw_results.json`

---

## 1. 論文主張のリフレーズ (§4.5)

| 項目 | 査読者再構成 |
|---|---|
| **課題** | 配電 HCA の出力 (violation rate) は load profile / threshold / placement / capacity / feeder の複数 uncertainty source に依存するが、**それぞれの相対寄与が定量化されていない**。先行論文 ([ScienceDirect 2025](https://www.sciencedirect.com/science/article/pii/S0306261925020537), [MDPI Energies 2023](https://www.mdpi.com/1996-1073/16/5/2371)) は各 source を別々に扱い、規格委員会向けの優先順位指針を欠く |
| **先行研究** | HCA challenges 2025 は load profile inaccuracy と metric definition variation を separate な Future Work に列挙。[arxiv 2501.15339](https://arxiv.org/html/2501.15339v1) は HCA 標準化を呼びかけるが prioritisation は無い。気候モデリング側 (Hawkins-Sutton 2009) には variance partition framework あるが配電応用は見当たらない |
| **方法 (提案手法の価値)** | 2 標準フィーダー (CIGRE LV/MV) × 2 load × 16×16 random PV realisation で 1024 base power-flow + 3 thresholds 後段評価 → 3072 metric values の factorial。各 fixed factor について Sobol-style first-order index `S_f = Var(E[Y\|f]) / Var(Y)` を計算。**新規性は 4 factor の同一実験 + 気候モデリング framework の電力系移植 + Pareto-style 規格優先度導出** |
| **実験結果** | load_level = 86.6 % (支配的)、residual+interactions = 12.7 %、threshold = 0.5 %、feeder = 0.15 %。CIGRE MV at high load では全 256 realisation で violation_ratio = 0.600 (固定) — 副次知見として PV 配置が MV 高 load で無関係になる degeneracy regime を発見 |
| **考察** | 規格委員会は **threshold 定義 (Range A vs B 周辺) より load profile assumption を先に標準化すべき**。Range A vs Range B 議論は 0.5 % 問題、load profile は 87 % 問題。MV degeneracy は PV 規模選択の policy lever としての意義を疑問視 |

リフレーズが破綻なく 5 項目埋まる → §3.1 (gridflow を contribution として扱わない) を満たしている。`§3.6 Tooling` でフレームワークをツールとして言及するに留めている。

---

## 2. 総合判定

### **条件付き合格** (§4.3 — A 合格 + MAJOR 1 件以下 + 修正計画つき)

判定根拠:
- A (方針適合性): ✅ 合格 — gridflow は §3.6 で「tooling」として 1 段落のみ言及、課題は C-3 + C-10 を査読論文 Future Work として根拠つきで明示
- B (数値の信頼性): ✅ — レポートの全数値が `decomposition.json` に対応、計算式 §3.5 で明示
- C (科学的妥当性): ✅ — 因子設計が主張を支持、§4.3 の MV degeneracy が「stdev = 0.000」を artefact として明示識別、Limitations 6 件で既知制約開示
- D (論文材料): ✅ — Title/Abstract/Methodology/Results/Discussion/Limitations/Reproducibility 全揃い
- E (投稿先水準): MAJOR 1 件 (E-2 IEEE PES 標準フィーダー不使用、CIGRE で代用) + MODERATE 数件

修正計画は §5 で明示。

## 3. 指摘事項

### CRITICAL

> **なし**

### MAJOR

| # | 指摘 | 根拠 (review_policy 章節) |
|---|---|---|
| **M-1** | IEEE PES 標準テストフィーダーではなく CIGRE LV/MV を代用。§4.2 E-2 は「IEEE 13/34/37/123」を要求 | レポート §3.1 注記 + §7-1 Limitations で開示済み。修正計画あり (§5-1) |

### MODERATE

| # | 指摘 |
|---|---|
| **m-1** | Threshold range が ±0.01 pu のみ。Range A vs Range B (0.95 vs 0.917) の本来の対立軸を含めれば threshold 寄与率が増える可能性。レポート §7-2 で開示済み |
| **m-2** | Single-PV per realisation。実用 stochastic HCA は multi-PV の cumulative penetration を扱う。residual 12.7 % が placement-interaction を underestimate している可能性 (§7-3) |
| **m-3** | Variance fractions に bootstrap CI なし。点推定のみ。§4.2 E-3「信頼区間」未充足。レポート §7-4 で開示し「one-day extension」として修正計画 |
| **m-4** | CIGRE MV degeneracy (stdev=0.000) は **PV size 50-500 kW が MV scale に過小** という設計選択の artefact。§4.3 で finding として扱っているが、scale-appropriate envelope での再実験が必要 (§7-6 で計画開示) |
| **m-5** | 収束分析 (n=100, 200, 500, 1000) のプロットがない。§4.2 E-3 要求項目 |

### MINOR

| # | 指摘 |
|---|---|
| **n-1** | Figure 1 がレポートに添付されていない (matplotlib 未インストール環境のため `_plot_decomposition` が gracefully skip)。代わりに表で示すのは妥当だが、最終投稿前に図化が必要 |
| **n-2** | Variance fraction を fraction (0-1) で示しているが、論文では % 表記の方が読みやすい (Abstract は %、表は fraction で混在) |
| **n-3** | §3.4 metric の数式が markdown LaTeX で書かれているが、レンダリング環境依存。投稿先の指定形式を要確認 |

---

## 4. 「動くか」と「研究になるか」のギャップ — try8 との比較

| 観点 | try8 | try9 |
|---|---|---|
| 検証対象 | gridflow 機能セット | 配電 HCA の uncertainty 構造 |
| n | 4 + 11 grid points | 1024 base + 3072 metric values |
| 課題出典 | `phase1_result.md §5.1` (内部持ち越し) | `research_landscape.md` C-3 + C-10 (査読論文 Future Work) |
| Phase 0.5 | 未実施 | 実施 (12 ideas + 3 personas + Novelty Gate 6/6 通過) |
| Cross-disciplinary | なし | Hawkins-Sutton 気候モデリング framework |
| 先行研究比較 | 0 件 | 3 件 (定量比較表) |
| Actionable output | テスト合格 | 規格優先度ランキング |
| §3.1 違反 | 違反 (gridflow 機能を contribution に) | 遵守 (gridflow は §3.6 で tooling 言及のみ) |
| 査読合格性 | 不合格 (CRITICAL ×3) | 条件付き合格 (MAJOR 1 件) |

## 5. 修正提案 (try10 の方針 / 投稿前の追加作業)

### Priority 1 (条件付き合格を「合格」に押し上げる)

1. **IEEE PES feeder への移植**: opendssdirect 入りの環境で IEEE 13 + IEEE 34 を CIGRE LV + MV と置換。methodology は不変なので script に feeder factory を 1 行足すだけ
2. **Bootstrap CI on variance fractions**: 1024 base run を block-bootstrap (n=200) して各 fraction に 95 % CI を付ける

### Priority 2 (科学的厚み)

3. **Threshold range を Range A vs Range B に拡大**: 0.917 / 0.95 / 0.96 / 0.97 など、policy debate の実態に近い grid に
4. **Multi-PV realisation**: 1 realisation あたり 2-5 PV 同時注入。placement-interaction を residual から分離
5. **Convergence plot**: n = 64, 256, 1024, 4096 で fraction が収束する図 (§4.2 E-3)

### Priority 3 (発信)

6. **Figure を生成**: matplotlib 入り環境で `_plot_decomposition` を回し、論文用 PNG を `results/` に追加
7. **Hawkins-Sutton 1991/2009 の正確な引用**: report の §5.2 で DOI を脚注化

---

## 6. プロセス上の所見

### 6.1 try8 → try9 の差分が示すもの

try8 でレポート時点で気付いていなかった「ツール検証 vs 研究検証」の区別を、try9 では Phase 0 → 0.5 → 1 の **読解 → 構想 → 実験 → 報告** の順で踏むことで対応できた。これは `mvp_review_policy.md` §0 の問いを **実験前** に立てた効果。

### 6.2 Phase 0.5 の効果検証

ideation_record §7 (Fixation 監視) で「try1〜7 が HC(θ) 曲線統計量に 6 連続固着していた」ことを **明示的にチェックリスト化** したことで、try9 は variance decomposition (構造的に異なる軸) に転換できた。これは Rule 6 が「3 連続で同方向」を強制転換する設計どおりの動作。

### 6.3 残る懸念

- Phase 0.5 ideation が AI (= 私) のみで実施されており、人間の選択眼 (HAI-CDP) は未経由。Rule 1 の本意は「AI = 候補生成、人間 = 選択」であり、この点で部分実装。Phase 3 (PO 最終レビュー) 時点で Idea 4 (variance decomposition) の選択が PO 判断で正しかったかを問い直すのが筋
- 12 ideas のうち 8 件は実験未実施。"Standards-equivalence theorem" (Idea 10) などは独立に MVP として面白い候補

---

## 7. 結論

**try9 は条件付き合格 (MAJOR ×1 / MODERATE ×5 / MINOR ×3)。**

§5 の Priority 1 (IEEE PES feeder + bootstrap CI) を満たせば「合格」、Priority 2 まで満たせば「合格 (Top venue)」相当の論文材料になる。

Phase 3 (プロダクトオーナー最終レビュー) では:
- 本 review_record を読んだ上で、Priority 1 を try10 として実施するか、try9 を「Tier-2 venue (MDPI Energies / IEEE Access) 投稿向けの完成度」として確定するかを判断
- ideation_record の Idea 4 (variance decomposition) 選択が PO 視点で妥当だったか確認
