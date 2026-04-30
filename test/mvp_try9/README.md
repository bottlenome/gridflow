# try9 — Variance Attribution of Hosting-Capacity Uncertainty across CIGRE LV/MV

## 1. 研究問題

> 2 つの標準配電フィーダー (CIGRE LV / CIGRE MV) で stochastic 違反率の分散を
> PV 配置・PV 容量・電圧閾値・負荷プロファイルの 4 factor に **variance
> decomposition** し、「規格委員会が**最初に**標準化すべき factor」を量で示す。

## 2. 出典課題 (Phase 0 / `mvp_review_policy.md` §2.1 準拠)

| ID | 出典 |
|---|---|
| C-3 | [ScienceDirect 2025: HCA challenges (DOI: 10.1016/j.apenergy.2025.020537)](https://www.sciencedirect.com/science/article/pii/S0306261925020537) Future Work |
| C-10 | [MDPI Energies 2023: HCA Strategies (DOI: 10.3390/en16052371)](https://www.mdpi.com/1996-1073/16/5/2371) Future Work |

詳細: `docs/research_landscape.md`、`test/mvp_try9/ideation_record.md`

## 3. 実験設計 (factorial)

| Factor | Levels | 種別 |
|---|---|---|
| Feeder | CIGRE LV (44 bus), CIGRE MV (15 bus) | 固定 |
| Load level | 0.50, 1.00 (× nominal) | 固定 |
| Threshold (lower) | 0.94, 0.95, 0.96 pu | 固定 (post-hoc) |
| Placement seed | 1..16 (random PV bus per realization) | ランダム |
| Capacity seed | 1..16 (random PV kW ∈ [50, 500] per realization) | ランダム |

**Total simulations**: 2 × 2 × 16 × 16 = **1024 base runs** + 3 thresholds の post-hoc 再評価 = 3072 metric values。

## 4. 出力

- `results/raw_results.json` — 1024 件の (factor 値, voltage vector) 全件
- `results/decomposition.json` — Sobol-style first-order variance fractions
- `results/variance_decomposition.png` — 4 factor の fraction-of-variance 棒グラフ
- `report.md` — paper draft material (Title / Abstract / 図キャプション / Limitations)
- `review_record.md` — Phase 2 ゼロベース査読

## 5. 再現

```bash
uv run python -m test.mvp_try9.tools.run_variance_decomposition
cat test/mvp_try9/results/decomposition.json
```
