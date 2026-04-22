# MVP try 3 — Stochastic HCA Cross-topology Comparison

try2 review で指摘された問題を全件修正した再実行。

## try2 からの主な変更

1. **§3.1 準拠**: gridflow を論文 contribution から除外。ドメイン知見のみを主張
2. **数値修正**: 全数値を JSON から転記。try2 の runtime_mean 転記ミスを解消
3. **shared-seed artifact 識別**: hosting_capacity_mw_max の 0.00% 一致を artifact と明示
4. **再現性検証**: `verify_reproducibility.py` による rerun + diff を実装・実行
5. **ラベル修正**: "IEEE 30" → "MV ring 7-bus (20 kV)" に全箇所で統一
6. **relative_delta 修正**: 分母を baseline (OpenDSS) に変更
7. **min=0 議論**: hosting_capacity_mw_min の非対称性を voltage headroom で説明

## 実行方法

```bash
bash test/mvp_try3/tools/run_cross_solver.sh
```

## ディレクトリ構成

```
test/mvp_try3/
├── README.md
├── report.md               # 実験レポート
├── packs/
│   ├── ieee13_sweep_base.dss
│   ├── ieee13_sweep_base.yaml
│   └── mv_ring_pp_sweep_base.yaml
├── sweep_plans/
│   ├── opendss_sweep.yaml
│   └── pandapower_sweep.yaml
├── tools/
│   ├── run_cross_solver.sh
│   ├── hosting_capacity.py
│   ├── compare_solvers.py
│   ├── plot_stochastic_hca.py
│   └── verify_reproducibility.py
└── results/
    ├── sweep_opendss.json
    ├── sweep_pandapower.json
    ├── sweep_opendss_rerun.json
    ├── comparison.json
    └── stochastic_hca.png
```
