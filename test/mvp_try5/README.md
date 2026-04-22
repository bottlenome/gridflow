# MVP try 5 — HCA-R: Threshold-Robust Hosting Capacity Metric

**Methodological contribution**: A new HCA metric (HCA-R) that eliminates
voltage-standard ambiguity in Monte Carlo hosting capacity assessment.

## Core Result (IEEE 13, n=1000)

| Metric | Value | 95% CI | Interpretation |
|---|---|---|---|
| **HCA-R** | **0.287 MW** | [0.272, 0.304] | Regulation-invariant HC |
| HCA-S | 0.979 MW | [0.947, 1.014] | Regulatory sensitivity |
| HCA-RR | 0.000 | [0.000, 0.000] | Regulatory robustness ratio |

Fixed-threshold HC reports:
- HC(Range A) = 0.000 MW
- HC(Range B) = 0.979 MW

→ HCA-R collapses this 0-0.98 MW ambiguity into a single characteristic value.

## Execution

```bash
bash test/mvp_try5/tools/run_hcar_study.sh
```

## Files

- `tools/hcar_metric.py` — Reference implementation of HCA-R / HCA-S / HCA-RR
- `tools/analyze_hcar.py` — Bootstrap CI + convergence + fixed-threshold comparison
- `tools/plot_hcar.py` — Publication figure generator
- `report.md` — Experiment report with paper draft material
- `results/hcar_analysis.json` — All numerical results (JSON, machine-readable)
- `results/hcar_figure.png` — 4-panel publication figure
