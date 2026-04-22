# MVP try6 report.md — Phase 2 査読レビュー記録（第三者レビュー）

## 論文主張のリフレーズ

- **課題**: stochastic HCA の閾値選択依存は「フィーダー ranking が逆転する」レベルの実害がある。IEEE 13 は Range A で HC=0、Range B で HC=0.98 — ranking は閾値次第
- **先行研究**: 閾値感度の存在は知られているが、これを scalar metric として解決する提案は無い。既存 HCA 文献は固定閾値の点推定のみ
- **方法**: HC(α) curve を規制パラメータ α 上で積分した HCA-R を提案。補助指標 HCA-S (感度) + HCA-RR (頑健性比) の triplet で feeder 特性を完全に記述
- **実験結果**: 2 フィーダーで実証。IEEE 13: HCA-R=0.280, HCA-RR=0 (fragile)。MV ring: HCA-R=1.038, HCA-RR=1 (perfectly robust)。fixed-threshold HC の ranking 矛盾を HCA-R が解決
- **考察**: HCA-R triplet は feeder の「規制頑健性」を単一の指標セットで表現する。ただしソルバー/トポロジ交絡あり。HCA-RR ∈ (0,1) の中間ケースは未検証

---

| 項目 | 値 |
|---|---|
| レビュー実施日 | 2026-04-22 |
| 対象ファイル | `test/mvp_try6/report.md` |
| レビュー方式 | 全成果物 (JSON x4, PNG x1, Python x5) との照合 |
| レビュー方針 | `docs/mvp_review_policy.md` (§4.2 A-E) |

---

## A. 方針適合性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| gridflow を contribution に含めていないか | ✅ | Abstract (§5.2) に gridflow の語なし。Contribution (§5.3) は HCA-R の方法論・理論・実証・実用の 4 点。§5.3 末尾で「ツール自体は contribution ではない」と明示 |
| 課題の出典が査読論文の Future Work か | ✅ | C-2, C-3, C-10 を research_landscape.md で引用確認 |

**A 判定: 合格**

---

## B. 数値の信頼性

16 数値 (§4.1 table + CI + convergence) を two_feeder_hcar.json と全件照合: **全一致** ✅

| 検証項目 | 結果 |
|---|---|
| IEEE 13 HCA-R/S/RR point | ✅ 4dp 一致 |
| MV ring HCA-R/S/RR point | ✅ 4dp 一致 |
| HC(Range A/B) 両フィーダー | ✅ |
| 95% CI 4 値 | ✅ |
| 収束 checkpoint 8 値 | ✅ |
| Bootstrap 統一性 | ✅ 全行 bootstrap=1000 (try5 B-3a 解消) |
| 再現性 | ✅ IEEE 13 rerun で physics metrics bit-identical |

**B 判定: 合格** (CRITICAL/MAJOR/MODERATE なし)

---

## C. 科学的妥当性

### try5 MAJOR C-1 の解消確認

| 要件 | 判定 | 根拠 |
|---|---|---|
| 2 フィーダー以上で HCA-R を実証 | ✅ | IEEE 13 + MV ring の 2 フィーダー |
| HCA-RR の非 degenerate case を含む | ✅ | MV ring で HCA-RR = 1.000 (perfectly robust) |
| cross-feeder 比較可能性を実証 | ✅ | §4.2 で ranking 矛盾の解決を数値実証 |

**C-1: 解消** ✅

### try5 MODERATE C-2/C-3/C-4 の解消確認

| 指摘 | 判定 | 根拠 |
|---|---|---|
| C-2: "regulatory-invariant" over-claim | ✅ 解消 | §2.2 point 4 で "threshold-choice-invariant within ANSI range" に修正 |
| C-3: 性質の議論不足 | ✅ 解消 | §2.2 で有界性証明、単調性は「一般に非保証、binding constraint 条件下で成立」、連続性は有限 N の離散性を明記 |
| C-4: α 補間の根拠不足 | ✅ 解消 | §2.3 で ANSI 2-range 体系との対応を議論 |

### 新規指摘

#### MODERATE C-5: HCA-RR が 0 と 1 の両極端のみ — 中間値の挙動が未知

2 フィーダーの結果は HCA-RR = 0 (IEEE 13) と HCA-RR = 1 (MV ring)。
HCA-RR ∈ (0, 1) の中間ケース (e.g., 0.3 や 0.7) が存在するフィーダーでの
挙動が未検証。3 指標の連続的な discriminative power は未実証。
Limitations §5.4 item 2 で認知済み。

**影響度**: PES GM 5 ページ conference paper としては 2-feeder 実証で十分。
中間ケースは extended version (journal) で求められる水準。

#### MODERATE C-6: ソルバー / トポロジ交絡

IEEE 13 (OpenDSS) vs MV ring (pandapower) はソルバーが異なる。
HCA-R の差がトポロジ由来かソルバー由来か分離不能。
Limitations §5.4 item 1 で認知済み。
本論文の主張は「HCA-R が比較を可能にする」であり、物理的原因の特定は scope 外
なので、MODERATE に留まる。

### その他

| チェック項目 | 判定 |
|---|---|
| DoD 判定 | ✅ 適切 |
| Limitations | ✅ 5 項目 (交絡、2 feeder 限界、α 線形、時間粒度、熱制約) |
| 収束分析 | ✅ 両フィーダーで 4 checkpoint |
| Bootstrap | ✅ 全行 1000 resamples |

**C 判定: 合格** (MODERATE 2 件: C-5 中間 HCA-RR、C-6 交絡)

---

## D. 論文材料としての完成度

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 図ラベル | ✅ | 2-feeder 4-panel figure、IEEE 13 / MV ring 正確表記 |
| 用語 | ✅ | ANSI C84.1, threshold-choice-invariant (over-claim 修正済み) |
| 再現手順 | ✅ | run_hcar_study.sh で全 6 steps |
| 数式 | ✅ | §2.1 で HC(α), HCA-R/S/RR 定義 |
| §2.2 性質 | ✅ | 有界性 + 条件付き単調性 + 離散/連続の区別 |
| §2.3 補間根拠 | ✅ | ANSI 2-range 対応 |

**D 判定: 合格**

---

## E. 投稿先水準 (IEEE PES GM)

### E-1. 手法的新規性

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| 先行研究との差分 | ✅ | HCA の閾値パラメータ空間積分 → scalar 化は前例なし |
| 差分が自明でないか | ✅ | ranking 矛盾の数値実証 (§4.2) が自明でない結果を示す |
| 先行研究比較 | ⚠️ MODERATE | EPRI DRIVE / arXiv 等の他提案指標との定量比較なし |

### E-2. 実験規模

| チェック項目 | 判定 | 根拠 |
|---|---|---|
| n >= 1000 | ✅ | 両フィーダー n=1000 |
| IEEE 標準フィーダー | ✅ | IEEE 13 |
| **フィーダー数** | **✅** | **2 フィーダー (try5 MAJOR 解消)** |
| 時間粒度 | ⚠️ MODERATE | ピーク 1 時刻 |
| 制約の網羅性 | ⚠️ MODERATE | 電圧のみ |

### E-3. 科学的健全性

| チェック項目 | 判定 |
|---|---|
| 信頼区間 | ✅ bootstrap 1000 |
| 収束分析 | ✅ 4 checkpoints × 2 feeders |
| 感度分析 | ✅ α 全域で HC(α) 評価 (= 本論文の主題) |

### E-4. 実用的メッセージ

| チェック項目 | 判定 |
|---|---|
| Actionable | ✅ 既存文献 post-processing 変換 + ranking 矛盾解決 |
| Policy | ✅ threshold-choice-invariant 比較の必要性 |

**E 判定: 投稿可 (Top venue)** — CRITICAL/MAJOR なし、MODERATE 3 件は PES GM 5p の制約内

---

## 総合判定

| 観点 | 判定 |
|---|---|
| A 方針適合性 | ✅ 合格 |
| B 数値信頼性 | ✅ 合格 |
| C 科学的妥当性 | ✅ 合格 (MODERATE 2 件) |
| D 完成度 | ✅ 合格 |
| E 投稿先水準 (PES GM) | ✅ **投稿可 (Top venue)** (MODERATE 3 件) |

### 総合判定: **合格 (Top venue)**

try5 MAJOR C-1 (単一フィーダー degenerate) が 2-feeder 実証で解消。
try5 MODERATE C-2/C-3/C-4/B-3a の全 4 件も適切に修正済み。

**新規 MODERATE 3 件** (C-5: HCA-RR 中間値、C-6: 交絡、E-1: 先行指標比較)
はいずれも Limitations で認知されており、PES GM 5 ページ conference paper の
制約範囲内。Journal extended version で対応が望ましいが、conference 採択を
阻むレベルではない。

---

## try2 → try6 の進化

| try | 判定 | 主な問題 |
|---|---|---|
| try2 | 不合格 | §3.1 violation + 転記ミス |
| try3 | 合格 / E 不適 | novelty 不足 |
| try4 | 合格 / E 条件付き | empirical study 止まり |
| try5 | 条件付き合格 | 単一 degenerate feeder |
| **try6** | **合格 (Top venue)** | **MODERATE 3 件のみ** |

---

## 残存 MODERATE (journal extended version で対応推奨)

| # | 内容 |
|---|---|
| C-5 | HCA-RR ∈ (0,1) の中間ケースフィーダー追加 (IEEE 34/123) |
| C-6 | 同一ネットワーク cross-solver 検証 (CDL Phase 2) |
| E-1 | EPRI DRIVE 等他提案指標との定量比較 |
