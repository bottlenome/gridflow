#!/usr/bin/env bash
# MVP try 3 — full cross-topology stochastic HCA driver.
#
# Steps:
#   1. Register both base packs.
#   2. Sweep IEEE 13 (OpenDSS) with hosting_capacity_mw plugin.
#   3. Sweep MV ring 7-bus (pandapower) with hosting_capacity_mw plugin.
#   4. Reproducibility verification: rerun OpenDSS sweep and diff.
#   5. Compare the two SweepResult JSONs.
#   6. Generate the matplotlib stochastic_hca.png figure.
#
# Changes from try2:
#   - Corrected all labels: "MV ring 7-bus" instead of "IEEE 30"
#   - Added reproducibility verification (Step 4)
#   - compare_solvers.py uses baseline (OpenDSS) denominator
#
# Usage (from repo root):
#     bash test/mvp_try3/tools/run_cross_solver.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACKS_DIR="${HERE}/packs"
SWEEPS_DIR="${HERE}/sweep_plans"
TOOLS_DIR="${HERE}/tools"
RESULTS_DIR="${HERE}/results"

mkdir -p "${RESULTS_DIR}"

# tools/ goes onto PYTHONPATH so the metric plugin is importable as
# ``hosting_capacity:HostingCapacityMetric`` regardless of cwd.
export PYTHONPATH="${TOOLS_DIR}${PYTHONPATH:+:${PYTHONPATH}}"

PLUGIN_SPEC="hosting_capacity:HostingCapacityMetric"

echo "=== Step 1: register base packs ==="
gridflow scenario register "${PACKS_DIR}/ieee13_sweep_base.yaml"
gridflow scenario register "${PACKS_DIR}/mv_ring_pp_sweep_base.yaml"
echo ""

START_OPENDSS=$(date +%s.%N)
echo "=== Step 2: OpenDSS sweep (IEEE 13-node, 4.16 kV, 200 random placements) ==="
gridflow sweep \
  --plan "${SWEEPS_DIR}/opendss_sweep.yaml" \
  --connector opendss \
  --metric-plugin "${PLUGIN_SPEC}" \
  --output "${RESULTS_DIR}/sweep_opendss.json" \
  --format json
END_OPENDSS=$(date +%s.%N)
WALL_OPENDSS=$(awk "BEGIN {printf \"%.2f\", ${END_OPENDSS} - ${START_OPENDSS}}")
echo "OpenDSS sweep wall time: ${WALL_OPENDSS} s"
echo ""

START_PP=$(date +%s.%N)
echo "=== Step 3: pandapower sweep (MV ring 7-bus, 20 kV, 200 random placements) ==="
gridflow sweep \
  --plan "${SWEEPS_DIR}/pandapower_sweep.yaml" \
  --connector pandapower \
  --metric-plugin "${PLUGIN_SPEC}" \
  --output "${RESULTS_DIR}/sweep_pandapower.json" \
  --format json
END_PP=$(date +%s.%N)
WALL_PP=$(awk "BEGIN {printf \"%.2f\", ${END_PP} - ${START_PP}}")
echo "pandapower sweep wall time: ${WALL_PP} s"
echo ""

echo "=== Step 4: reproducibility verification (rerun OpenDSS + diff) ==="
gridflow sweep \
  --plan "${SWEEPS_DIR}/opendss_sweep.yaml" \
  --connector opendss \
  --metric-plugin "${PLUGIN_SPEC}" \
  --output "${RESULTS_DIR}/sweep_opendss_rerun.json" \
  --format json
python "${TOOLS_DIR}/verify_reproducibility.py" \
  "${RESULTS_DIR}/sweep_opendss.json" \
  "${RESULTS_DIR}/sweep_opendss_rerun.json"
echo ""

echo "=== Step 5: compare two networks ==="
python "${TOOLS_DIR}/compare_solvers.py" \
  --opendss "${RESULTS_DIR}/sweep_opendss.json" \
  --pandapower "${RESULTS_DIR}/sweep_pandapower.json" \
  --output "${RESULTS_DIR}/comparison.json"
echo ""

echo "=== Step 6: plot stochastic HCA figure ==="
if python -c "import matplotlib" 2>/dev/null; then
  python "${TOOLS_DIR}/plot_stochastic_hca.py" \
    --opendss "${RESULTS_DIR}/sweep_opendss.json" \
    --pandapower "${RESULTS_DIR}/sweep_pandapower.json" \
    --output "${RESULTS_DIR}/stochastic_hca.png"
else
  echo "matplotlib not installed; skipping plot."
fi
echo ""

echo "=== Done. OpenDSS=${WALL_OPENDSS}s  pandapower=${WALL_PP}s ==="
