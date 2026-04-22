# MVP try 6 — HCA-R: 2-Feeder Demonstration

Resolves try5 MAJOR C-1: single-feeder degenerate case.

## Core Result

| Metric | IEEE 13 | MV ring | Interpretation |
|---|---|---|---|
| HCA-R | 0.280 MW | **1.038 MW** | MV ring 3.7x more robust |
| HCA-S | 0.979 MW | 0.000 MW | IEEE 13: threshold-fragile |
| HCA-RR | 0.000 | **1.000** | MV ring: perfectly robust |

Fixed-threshold HC gives contradictory rankings; HCA-R resolves this.

## Execution

```bash
bash test/mvp_try6/tools/run_hcar_study.sh
```
