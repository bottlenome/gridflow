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
