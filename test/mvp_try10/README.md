# try10 — Ideation-only stop (暫定)

実施日: 2026-04-28
準拠: `docs/mvp_review_policy.md` §2.5

## 状態: **Phase 0.5 で意図的に停止中**

try9 で Novelty Gate を **文献検索なし**に自己採点して通過させたのが review で破綻したため、try10 は同じ轍を踏まないよう「実際の文献検索ができるまで実験フェーズに進まない」運用を選択。

## 進捗

| フェーズ | 状態 | 成果物 |
|---|---|---|
| Phase 0 (課題出典) | ✅ try9 と同じ C-3 + C-10 を継承 | `docs/research_landscape.md` |
| Phase 0.5 (ideation) | ✅ **完了** | `ideation_record.md` (15 候補 / 5 persona / 4-step CoT / 5 extreme user / TRIZ / fixation 監査 / **正直 Novelty Gate**) |
| Phase 1 (実験) | ⏸ **PO 判断待ち** | 暫定選定: 候補 #1 (Stochasticity-collapse phase transition)、要検索項目 3 件 |
| Phase 2 (review) | ⏸ Phase 1 完了後 | - |

## PO への確認事項 (`ideation_record.md` §10)

1. 候補 #1 の novelty 確認 — 以下クエリでの先行論文有無:
   - Google Scholar: `"hosting capacity" "phase transition" distribution network`
   - IEEE Xplore: `hosting capacity AND stochastic AND deterministic AND threshold`
   - Scopus: `("stochastic regime" OR "deterministic regime") AND "hosting capacity"`
   - arXiv: `hosting capacity transition load level`

2. 文献あり → 候補 #8 (literature meta-analysis) / #10 (standards-as-feature) / 別 ideation のどれに切替?
3. 文献なし → 候補 #1 で実験フェーズへ go (準備設計済み、§9 参照)

## 候補 #1 の本質 (要約)

> 配電 feeder の load level を上げると、ランダム PV 配置への HC 感度 (stdev of violation ratio) が連続的にゼロに崩壊する **転換点** がある。これを "stochasticity-collapse threshold (SCT)" として定義し、feeder topology features からの analytic predictor を構築する。

try9 の MV degeneracy 観察 (CIGRE MV @ load=1.0 で全 256 realisation が同一 violation_ratio=0.6) が経験的根拠。
