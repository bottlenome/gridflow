# MVP try 4 — Voltage Standard Sensitivity of Stochastic HCA

IEEE PES General Meeting 水準の実験: 同一フィーダー (IEEE 13) ・同一 seed で
電圧基準の閾値のみを変更し、HCA への影響を定量評価。

## 実行方法

```bash
bash test/mvp_try4/tools/run_threshold_study.sh
python test/mvp_try4/tools/analyze_thresholds.py
python test/mvp_try4/tools/plot_threshold_study.py
```

## Key Finding

| 閾値 | Mean HC [MW] | 95% CI | Rejection |
|---|---|---|---|
| Range A (0.95-1.05) | 0.000 | — | 100% |
| Custom (0.92-1.05) | 0.308 | [0.268, 0.348] | 81.1% |
| Range B (0.90-1.06) | 0.979 | [0.944, 1.014] | 3.5% |
