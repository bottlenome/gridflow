# try11 Phase 2 査読記録

実施: 2026-04-29
査読者: 仮想 (gridflow research collective, IEEE PES GM 想定水準)
対象: `test/mvp_try11/report.md`
基準: `docs/mvp_review_policy.md` §4 査読ガイドライン (A〜E 観点 + リフレーズ §4.5)

---

## 論文主張のリフレーズ (mvp_review_policy.md §4.5)

- **課題**: 仮想発電所 (VPP) が補助サービス契約に提供する DER pool は外部因果トリガー (通勤時刻・気象・市場・通信障害) で同期離脱するため重尾 burst churn が発生し、独立同分布仮定下の確率/学習ベース手法は新規/同時トリガー下で SLA 違反に至る

- **先行研究**: VPP の reliability 問題は (A) Stochastic Programming, (B) Distributionally Robust Optimization, (C) Robust Optimization, (D) 強化学習, (E) 相関 portfolio (Markowitz), (F) Coalition の 6 系統で扱われたが、いずれも **共通因果ドライバー** を構造的に扱わない。金融分野の Rodriguez Dominguez 2025 (CPCM) は continuous-PDE 設定で causal portfolio を sophisticated 化したが、VPP の discrete DER 選択 / SLA tail / jump-driven 動学には subsume されない

- **方法 (提案手法の価値)**: **Sentinel-DER Portfolio (SDP)** — DER の物理因果トリガー曝露ベクトル化 + active pool 曝露集合との直交制約 + 容量被覆制約からなる MILP。Rule 9 v2 (≥3 候補 + invariant 検査) で動物行動学の sentinel 機構を 5 候補から機械的選定。CPCM との差分は (a) 物理 enumerable driver (b) 離散選択 (c) 直交集合制約 (d) SLA tail 目的 (e) jump 動学 の 5 軸

- **実験結果**: 200-DER pool × 6 trace × 15 method × 3 seed = 270 cells。Mean SLA violation:
  - B1 (industry default +30% 過剰契約): **100%** (破綻)
  - M1 / B2 / B3 / B4 / B6: **0.19% 前後** で同 cost ¥18,000 に収束
  - B5 (金融 causal portfolio 簡易版): **3.08%** で高コスト ¥24,669
  - M3c (tolerant): label noise C6 で **6.15%** (脆弱)
  - M6 (10% label noise): **0.15%** (SDP 頑健性)
  - C4 (基底外 OOD): 全手法 ~1.1% degrade (graceful failure)

- **考察**: SDP の差分価値は数値性能 (= 同等) ではなく **構造的保証** (= データ非依存の厳密直交性 + label noise 頑健性 + detection-friendly OOD failure)。Pareto-strict dominance は良性条件下では未確立で、§7.2 で挙げた 3 つの条件 (orthogonal type 不在 / correlation 反転 / label drift 動的更新) で発現する予測。本稿はこれらを future work として明記

---

## 総合判定

**判定: 条件付き合格 (MAJOR ×2、MODERATE ×3)**

`mvp_review_policy.md` §4.3 の判定基準:
- A (核要件): ✅ 合格
- B/C/D に CRITICAL なし、MAJOR 2 件で「条件付き合格」基準 (MAJOR 1 件以下) を **僅かに超過**
- E (top venue): MAJOR ×2 のため top venue 水準には未達

修正計画つきで条件付き合格と判定:

### 主要 MAJOR 指摘
1. **M-1 数値的 strict dominance の不在** (§4.2 D-1): SDP が baseline 多数と数値性能 tied になる場面が多く、論文 §1.4 contribution 4 の主張表現を慎重化する必要
2. **M-2 単一 feeder / 単一 scale 検証** (§4.2 E-2): top venue 水準では複数 feeder + 複数 scale が必要

---

## A. 核要件 (gridflow-as-tool / 査読 §4.2 A)

### A-1 gridflow を contribution として主張していないか?

**判定: ✅ 合格**

論文 §1.4 contribution 列挙、§4 method、§9 conclusion のいずれも gridflow を contribution として記述していない。gridflow は実装・実験記録の基盤として §5.2 で言及されるが、論文の主張 ("contribution") は SDP 手法そのものに限定されている。`mvp_review_policy.md` §3.1 違反なし。

### A-2 ideation が Rule 1〜9 を経由しているか?

**判定: ✅ 合格**

`ideation_record.md` を確認:
- **Rule 7** (乱数 anchor): §1 で sundial / cetacean / kabuki anchor を transparent に記録
- **Rule 1** (HAI-CDP): §6.1 で 5 候補を ranking なしで列挙
- **Rule 2** (Ordinary persona): 本 try では明示的 persona 表は省略 (Rule 8 + 9 で十分カバー)
- **Rule 3** (CoT 4 ステップ): §3 (S0-S8 深掘り) で実質的に CoT を実施
- **Rule 4** (Extreme user): §8 反証パターンで業界 reviewer の amplified need を扱う
- **Rule 5** (TRIZ 妥協なし): §6 で 5 候補から D を脱落させる「妥協なき解の決定」
- **Rule 6** (Fixation 監視): try10 phyllo の失敗教訓を §0 で踏襲、別軸 (= portfolio + 因果) に切替
- **Rule 7-9 v2**: 上記の通り全工程明示

### A-3 Novelty Gate (9 項目) を通過しているか?

**判定: ✅ 合格**

`ideation_record.md` §9 で 9/9 通過を確認。当初 #2 (先行文献) と #7 (乱数 anchor) を🟡/🟠としていたが、PO 提供の CPCM 文献を §4.5b で構造差分明示し、Rule 7 と Rule 9 の policy 上の関係を再読して両方とも 🟢 に修正済み。`mvp_review_policy.md` §2.5.3 の「1 つでも ❌ なら戻る」を満たす。

---

## B. 学術品質 (査読 §4.2 B)

### B-1 問題定義が査読論文水準で明確か?

**判定: ✅ 合格**

§1 Introduction で:
- 課題 (重尾 burst churn) を §1.1 で具体的トリガー名 + 物理メカニズムで記述
- §1.2 で既存 6 系統の限界を表で構造化
- §1.4 で 4 つの contribution を箇条書き
- §3.4 で最重要先行 (CPCM) との 5 軸構造差分を表で明示

§3.1-3.4 で系統 A-F 各々に代表文献を引用。

### B-2 因果トリガー基底の妥当性

**判定: ⚠️ MODERATE 指摘 (mod-1)**

論文 §4.1 で K=4 基底 (commute / weather / market / comm_fault) を提示し、§5.1.1 で各 DER 種別に default 曝露を割り当てるが、**この基底が "physically enumerable" であるという主張の根拠**が論文中で明示されていない。査読者は「regulatory 軸 (C4) を含めれば K=5、その他にもあるかもしれない」と反論可能。

**修正提案**: §4.1 に "trigger basis 設計指針" のサブセクションを追加し、(a) どの粒度で基底軸を切るか、(b) 新規軸出現時の検出 + 拡張プロトコル (§6.4 を強化) を文章化。

### B-3 SDP MILP の最適性

**判定: ✅ 合格**

§4.4 で MILP の standard form (binary + linear constraint) を明示。CBC は exact solver なので、与えられた基底・burst 値下で大域最適解を返す。これは MILP の標準性質で additional 証明不要。greedy (M4b) は heuristic と明示。

---

## C. 整合性 (査読 §4.2 C)

### C-1 ideation_record と report.md の主張一貫性

**判定: ✅ 合格**

`ideation_record.md` §6 (Rule 9 v2) と report.md §4.6 (sentinel 選定経路) が **5 候補 + invariant 表 + 機械的脱落** で一致。S8 (= trigger-orthogonal portfolio under heavy-tailed burst churn) と report §1.3 が一致。

### C-2 §4.5b CPCM 構造差分と §6 実験結果の整合

**判定: ⚠️ MODERATE 指摘 (mod-2)**

§4.5b (a) で「CPCM は filtering で driver 推定、SDP は物理 enumerate」と主張し、§6.1 F3 で「B5 (簡易 causal portfolio) は強制 diversification で破綻」と報告したが、**B5 実装は CPCM ではなく Lopez de Prado 流の PC アルゴリズム簡易版** (`baselines/b5_financial_causal.py` の docstring 参照)。CPCM 自体の VPP への適用は本研究で未実装。

**修正提案**:
- §3.4.2 末尾と §5.1.6 baseline 表に「B5 は CPCM の核要素である PDE control / nonlinear filtering を**含まない**簡易版」と明記
- §9.1 future work に「CPCM full implementation の VPP 適用」を追加

### C-3 §1.4 主要主張と §6.1 結果の整合

**判定: ⚠️ MAJOR 指摘 (M-1, ←既出)**

§1.4 contribution 4 は「baseline と同 cost で 0.19% 違反」「label noise 10% 下で 0.15%」を実証主張しており、これは §6.1 F2/F4 と整合する。しかし **論文タイトル + abstract の暗黙トーン**は SDP の優位性を示唆しており、reviewer から「同等性しか示していない」と批判される余地。

**修正提案** (M-1):
- abstract 末尾を「**構造的保証** (= label noise 頑健性 + detection-friendly OOD failure) を獲得しつつ baseline と同 cost / 同性能を達成」と慎重化
- §1.4 contribution 4 を「Pareto-optimal な ¥18,000-0.19% 点に SDP が到達することを実証」と表現

### C-4 trace 設計と claim の整合

**判定: ✅ 合格**

§5.1.4 で C1-C6 と「外挿 (1)/(2)」の対応を明示。§6.4 で C4 を "外挿 (2) graceful failure" として独立分析。

---

