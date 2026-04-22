#!/usr/bin/env bash
set -euo pipefail
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
export PYTHONPATH="${HERE}/tools${PYTHONPATH:+:${PYTHONPATH}}"
PLUGIN="hosting_capacity:HostingCapacityMetric"

echo "=== Step 1: register packs ==="
gridflow scenario register "${HERE}/packs/ieee13_sweep_base.yaml"
gridflow scenario register "${HERE}/packs/mv_ring_pp_sweep_base.yaml"

echo "=== Step 2: IEEE 13 sweep (n=1000) ==="
gridflow sweep --plan "${HERE}/sweep_plans/ieee13_sweep.yaml" \
  --connector opendss --metric-plugin "${PLUGIN}" \
  --output "${HERE}/results/sweep_ieee13.json" --format json

echo "=== Step 3: MV ring sweep (n=1000) ==="
gridflow sweep --plan "${HERE}/sweep_plans/mv_ring_sweep.yaml" \
  --connector pandapower --metric-plugin "${PLUGIN}" \
  --output "${HERE}/results/sweep_mv_ring.json" --format json

echo "=== Step 4: reproducibility rerun (IEEE 13) ==="
gridflow sweep --plan "${HERE}/sweep_plans/ieee13_sweep.yaml" \
  --connector opendss --metric-plugin "${PLUGIN}" \
  --output "${HERE}/results/sweep_ieee13_rerun.json" --format json
python "${HERE}/tools/verify_reproducibility.py" \
  "${HERE}/results/sweep_ieee13.json" "${HERE}/results/sweep_ieee13_rerun.json"

echo "=== Step 5: 2-feeder HCA-R analysis ==="
python "${HERE}/tools/analyze_two_feeders.py"

echo "=== Step 6: publication figure ==="
python "${HERE}/tools/plot_two_feeders.py"

echo "=== Done ==="
