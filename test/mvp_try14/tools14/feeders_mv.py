"""MV feeder extension for try14: CIGRE MV (22 kV, 50 MVA, 15-bus).

try11 / 12 / 13 used only LV demo feeders (400 V, 0.16-0.95 MVA).
try14 adds the standard CIGRE MV benchmark to address the reviewer's
"deployable scale" question. CIGRE MV is a 14-bus 22 kV network with
2 trafos and 18 loads, and is included with pandapower out of the
box (no extra dependency).

This module extends try11's feeders.py FEEDER_NAMES + make_feeder by
monkey-patching: at import time, FEEDER_NAMES gains "cigre_mv" and the
make_feeder factory delegates to pandapower's
``create_cigre_network_mv`` for that name. We reuse try11's
map_pool_to_feeder, grid_impact, and grid_simulator wholesale.

A companion FeederVppConfig for cigre_mv is registered via
register_cigre_mv_config() — call once at module import.
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandapower.networks as pn

_TRY11 = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

from tools import feeders as _try11_feeders  # noqa: E402
from tools import feeder_config as _try11_feeder_config  # noqa: E402


CIGRE_MV_TRAFO_MVA: float = 50.0
CIGRE_MV_NAME: str = "cigre_mv"


def _make_cigre_mv():
    """Construct CIGRE MV pandapower network (14-bus 22 kV)."""
    return pn.create_cigre_network_mv()


def register_cigre_mv() -> None:
    """Patch try11's ``feeders.py`` so cigre_mv flows through the existing
    ``make_feeder`` / ``map_pool_to_feeder`` / ``grid_impact`` machinery.

    This is intentionally a runtime monkey-patch: try11 is FROZEN code
    we don't want to modify, and try14's ``feeders_mv`` is the place to
    register new feeders. After this call:

      * ``tools.feeders.FEEDER_NAMES`` includes ``"cigre_mv"``
      * ``tools.feeders.make_feeder("cigre_mv")`` returns a fresh net
      * ``tools.feeder_config.FEEDER_TRAFO_MVA["cigre_mv"]`` = 50.0
    """
    if CIGRE_MV_NAME not in _try11_feeders.FEEDER_NAMES:
        _try11_feeders.FEEDER_NAMES = _try11_feeders.FEEDER_NAMES + (CIGRE_MV_NAME,)

    original_make_feeder = _try11_feeders.make_feeder

    def patched_make_feeder(name: str):
        if name == CIGRE_MV_NAME:
            return _make_cigre_mv()
        return original_make_feeder(name)

    _try11_feeders.make_feeder = patched_make_feeder

    if CIGRE_MV_NAME not in _try11_feeder_config.FEEDER_TRAFO_MVA:
        _try11_feeder_config.FEEDER_TRAFO_MVA[CIGRE_MV_NAME] = CIGRE_MV_TRAFO_MVA


# Register on import so downstream modules see the MV feeder immediately.
register_cigre_mv()
