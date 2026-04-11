#!/usr/bin/env bash
# MVP try 1 — full DER sweep driver.
#
# 1. Register 5 Scenario Packs (DER 0/25/50/75/100%).
# 2. Run each pack 3 times with seed=42 to exercise reproducibility.
# 3. Run verify_reproducibility.py on the 15 JSON outputs.
# 4. Run gridflow benchmark on the 0% ↔ 100% pair.
# 5. Run plot_hosting_capacity.py to produce the headline figure.
# 6. Record a wall-clock measurement for the whole thing.
#
# Usage (from test/mvp_try1):
#     ./tools/run_der_sweep.sh
# or from anywhere:
#     bash test/mvp_try1/tools/run_der_sweep.sh

set -euo pipefail

HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
PACK_DIR="${HERE}/packs"
RESULTS_DIR="${HERE}/results"
TOOLS_DIR="${HERE}/tools"

mkdir -p "${RESULTS_DIR}"

PENS=(00 25 50 75 100)

echo "=== Step 1: register 5 packs ==="
for p in "${PENS[@]}"; do
  echo "--- ieee13_der_${p} ---"
  gridflow scenario register "${PACK_DIR}/der_${p}.yaml"
done
echo ""

echo "=== Step 2: run each pack 3 times (seed=42) ==="
SWEEP_START=$(date +%s.%N)
for p in "${PENS[@]}"; do
  for run in 1 2 3; do
    out="${RESULTS_DIR}/der_${p}_run${run}.json"
    echo "--- ieee13_der_${p} run ${run} -> ${out} ---"
    gridflow run "ieee13_der_${p}@1.0.0" \
      --steps 1 \
      --seed 42 \
      --format json \
      > "${out}"
  done
done
SWEEP_END=$(date +%s.%N)
SWEEP_WALL=$(awk "BEGIN {printf \"%.2f\", ${SWEEP_END} - ${SWEEP_START}}")
echo ""
echo "Sweep wall time: ${SWEEP_WALL} s"
echo ""

echo "=== Step 3: verify reproducibility (3 runs per pack) ==="
python "${TOOLS_DIR}/verify_reproducibility.py" "${RESULTS_DIR}"/der_*_run*.json
echo ""

echo "=== Step 4: benchmark 0% vs 100% ==="
# Pull the experiment_ids of the first run for der_00 and der_100 from the
# results files so we can feed them back into gridflow benchmark.
exp_00=$(python - <<'PY'
import json
import sys
with open("test/mvp_try1/results/der_00_run1.json") as fh:
    print(json.load(fh)["experiment_id"])
PY
)
exp_100=$(python - <<'PY'
import json
import sys
with open("test/mvp_try1/results/der_100_run1.json") as fh:
    print(json.load(fh)["experiment_id"])
PY
)
echo "baseline ${exp_00} vs candidate ${exp_100}"
gridflow benchmark \
  --baseline "${exp_00}" \
  --candidate "${exp_100}" \
  --format json \
  > "${RESULTS_DIR}/benchmark_00_vs_100.json"
cat "${RESULTS_DIR}/benchmark_00_vs_100.json"
echo ""

echo "=== Step 5: plot hosting-capacity figure ==="
if python -c "import matplotlib" 2>/dev/null; then
  python "${TOOLS_DIR}/plot_hosting_capacity.py" \
    "${RESULTS_DIR}"/der_*_run1.json \
    -o "${RESULTS_DIR}/hosting_capacity.png"
  echo "Figure written to ${RESULTS_DIR}/hosting_capacity.png"
else
  echo "matplotlib not installed; skipping plot step."
  echo "Install with:  pip install matplotlib"
fi
echo ""

echo "=== Done. Sweep wall time: ${SWEEP_WALL} s ==="
