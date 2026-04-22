# MVP try 7 — HC₅₀: Pharmacology-Inspired HCA Transition Metric

**Cross-disciplinary innovation**: IC₅₀ (pharmacology) → HC₅₀ (power systems HCA)

## Core Result

| Feeder | HC₅₀ (pu) | HC-width (pu) | Interpretation |
|---|---|---|---|
| IEEE 13 | **0.914** [0.914, 0.915] | **0.018** [0.017, 0.018] | 0.014 pu tightening → 50% HC loss |
| MV ring | > 0.950 (censored) | N/A | Robust beyond Range A |

## What HC₅₀ tells you that other metrics can't

- **Fixed-threshold HC**: "IEEE 13 has 0 MW (Range A) or 0.98 MW (Range B)" — which is it?
- **HCA-R**: "IEEE 13 has 0.28 MW average" — so what?
- **HC₅₀**: "IEEE 13 loses half its HC at θ_low = 0.914 pu — just 0.014 pu above Range B" — **actionable**

## Files

- `tools/hc50_metric.py` — HC₅₀ / HC-width reference implementation
- `results/hc50_analysis.json` — All numerical results
- `results/hc50_figure.png` — 4-panel publication figure
