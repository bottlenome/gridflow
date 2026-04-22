#!/usr/bin/env bash
# MVP try 4 — Parametric voltage threshold sensitivity study.
#
# Runs 3 x 1000 = 3000 stochastic HCA experiments on IEEE 13-node feeder
# with three voltage standards:
#   A: ANSI C84.1 Range A (0.95-1.05 pu)
#   B: ANSI C84.1 Range B (0.90-1.06 pu)
#   C: Custom intermediate (0.92-1.05 pu)
#
# Same seed/axes across all three → only the threshold changes.
# Plus: reproducibility verification (rerun Range B + diff).

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKS_DIR="${HERE}/packs"
SWEEPS_DIR="${HERE}/sweep_plans"
TOOLS_DIR="${HERE}/tools"
RESULTS_DIR="${HERE}/results"

mkdir -p "${RESULTS_DIR}"

echo "=== Step 1: register base pack ==="
gridflow scenario register "${PACKS_DIR}/ieee13_sweep_base.yaml"
echo ""

echo "=== Step 2: Range A sweep (0.95-1.05, n=1000) ==="
PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
START_A=$(date +%s.%N)
PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
gridflow sweep \
  --plan "${SWEEPS_DIR}/range_a_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hc_range_a:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_range_a.json" \
  --format json
END_A=$(date +%s.%N)
WALL_A=$(awk "BEGIN {printf \"%.2f\", ${END_A} - ${START_A}}")
echo "Range A wall time: ${WALL_A} s"
echo ""

echo "=== Step 3: Range B sweep (0.90-1.06, n=1000) ==="
START_B=$(date +%s.%N)
PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
gridflow sweep \
  --plan "${SWEEPS_DIR}/range_b_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hc_range_b:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_range_b.json" \
  --format json
END_B=$(date +%s.%N)
WALL_B=$(awk "BEGIN {printf \"%.2f\", ${END_B} - ${START_B}}")
echo "Range B wall time: ${WALL_B} s"
echo ""

echo "=== Step 4: Custom sweep (0.92-1.05, n=1000) ==="
START_C=$(date +%s.%N)
PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
gridflow sweep \
  --plan "${SWEEPS_DIR}/custom_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hc_custom:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_custom.json" \
  --format json
END_C=$(date +%s.%N)
WALL_C=$(awk "BEGIN {printf \"%.2f\", ${END_C} - ${START_C}}")
echo "Custom threshold wall time: ${WALL_C} s"
echo ""

echo "=== Step 5: Reproducibility verification (rerun Range B) ==="
PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}" \
gridflow sweep \
  --plan "${SWEEPS_DIR}/range_b_sweep.yaml" \
  --connector opendss \
  --metric-plugin "hc_range_b:HostingCapacityMetric" \
  --output "${RESULTS_DIR}/sweep_range_b_rerun.json" \
  --format json
python "${TOOLS_DIR}/verify_reproducibility.py" \
  "${RESULTS_DIR}/sweep_range_b.json" \
  "${RESULTS_DIR}/sweep_range_b_rerun.json"
echo ""

echo "=== Done. Range A=${WALL_A}s  Range B=${WALL_B}s  Custom=${WALL_C}s ==="
echo "Total experiments: 3000 (+ 1000 rerun = 4000)"
