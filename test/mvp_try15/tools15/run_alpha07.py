"""Run M1 vs M10 at α=0.70 (harder operating point) — same as try12-13 setup."""

from __future__ import annotations

import sys
from pathlib import Path

_HERE = Path(__file__).resolve().parent
_TRY11 = _HERE.parent.parent / "mvp_try11"
for p in (_TRY11, _HERE.parent):
    if str(p) not in sys.path:
        sys.path.insert(0, str(p))

from tools.feeder_config import FEEDER_TRAFO_MVA, FeederVppConfig  # noqa: E402

# Patch get_feeder_config to use α=0.70
_orig = None
from tools import feeder_config as _fc  # noqa: E402

def _alpha07_config(name: str) -> FeederVppConfig:
    trafo = FEEDER_TRAFO_MVA.get(name, 0.40)
    sla_kw = round(trafo * 1000 * 0.70)
    burst = (
        ("commute", float(sla_kw)),
        ("weather", float(sla_kw * 0.30)),
        ("market", float(sla_kw * 0.30)),
        ("comm_fault", float(sla_kw * 0.20)),
    )
    n_active_ev = max(5, int(sla_kw * 0.70 / 7.0))
    return FeederVppConfig(name, float(sla_kw), burst, n_active_ev)

_fc.get_feeder_config = _alpha07_config

# Now run the standard sweep with the patched config
from tools15.run_m1_vs_m10 import main as run_main  # noqa: E402

if __name__ == "__main__":
    sys.argv = ["run_alpha07", "--output", str(_HERE.parent / "results")]
    sys.exit(run_main())
