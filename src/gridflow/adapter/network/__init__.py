"""Adapters translating CDL canonical networks to solver-native inputs.

Spec: ``docs/phase1_result.md`` §5.1.3.

The :class:`~gridflow.domain.cdl.CDLNetwork` is the solver-agnostic
description of a power system. This package hosts:

* :mod:`gridflow.adapter.network.cdl_yaml_loader` — YAML → CDLNetwork
* :mod:`gridflow.adapter.network.cdl_to_dss`    — CDLNetwork → OpenDSS script
* :mod:`gridflow.adapter.network.cdl_to_pandapower` — CDLNetwork → pp.network

Converters live here (not in each connector) so every connector shares
the same canonical translation — cross-solver comparisons are then
"same CDL, different solver", not "two accidentally-different inputs".
"""

from gridflow.adapter.network.cdl_to_dss import cdl_to_dss
from gridflow.adapter.network.cdl_to_pandapower import cdl_to_pandapower
from gridflow.adapter.network.cdl_yaml_loader import (
    CDLNetworkLoadError,
    load_cdl_network_from_dict,
    load_cdl_network_from_yaml,
)

__all__ = [
    "CDLNetworkLoadError",
    "cdl_to_dss",
    "cdl_to_pandapower",
    "load_cdl_network_from_dict",
    "load_cdl_network_from_yaml",
]
