#!/usr/bin/env bash
# MVP try 5 — HCA-R (Threshold-Robust HCA) methodology demonstration.
#
# Steps:
#   1. Register base pack (IEEE 13)
#   2. Run base Monte Carlo sweep (n=1000)
#   3. Rerun for reproducibility verification
#   4. Compute HCA-R via post-processing (analyze_hcar.py)
#   5. Generate publication figure (plot_hcar.py)
#
# HCA-R is computed by post-processing child experiments — no new
# simulation is needed beyond the base Monte Carlo HCA sweep.

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKS_DIR="${HERE}/packs"
SWEEPS_DIR="${HERE}/sweep_plans"
TOOLS_DIR="${HERE}/tools"
RESULTS_DIR="${HERE}/results"

mkdir -p "${RESULTS_DIR}"
export PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

echo "=== Step 1: register base pack ==="
gridflow scenario register "${PACKS_DIR}/ieee13_sweep_base.yaml"
echo ""

echo "=== Step 2: Base sweep (IEEE 13, n=1000) ==="
START=$(date +%s.%N)
gridflow sweep \
  --plan "${SWEEPS_DIR}/n1000_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hosting_capacity:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_base.json" \
  --format json
END=$(date +%s.%N)
WALL=$(awk "BEGIN {printf \"%.2f\", ${END} - ${START}}")
echo "Base sweep wall time: ${WALL} s"
echo ""

echo "=== Step 3: Reproducibility rerun ==="
gridflow sweep \
  --plan "${SWEEPS_DIR}/n1000_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hosting_capacity:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_base_rerun.json" \
  --format json
python "${TOOLS_DIR}/verify_reproducibility.py" \
  "${RESULTS_DIR}/sweep_base.json" \
  "${RESULTS_DIR}/sweep_base_rerun.json"
echo ""

echo "=== Step 4: Compute HCA-R (post-processing) ==="
python "${TOOLS_DIR}/analyze_hcar.py"
echo ""

echo "=== Step 5: Generate publication figure ==="
python "${TOOLS_DIR}/plot_hcar.py"
echo ""

echo "=== Done ==="
