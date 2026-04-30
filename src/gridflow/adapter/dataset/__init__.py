"""Adapter-layer dataset loaders.

Spec: ``docs/dataset_contribution.md``.

Each concrete loader is a separate module so contributors can add new
sources by adding a single file.

Currently registered:
  * SyntheticLoader              (gridflow/synthetic_vpp_churn/*) — CC0
  * PecanStreetLoader            (pecanstreet/*)                  — Proprietary
  * CAISOLoader                  (caiso/*)                        — Public-Domain
  * AEMOTeslaVPPLoader           (aemo/tesla_vpp_*)               — Public-Domain
  * JEPXLoader                   (jepx/*)                         — CC-BY-4.0
  * NRELResStockLoader           (nrel/resstock_*)                — CC-BY-4.0

Stubs (Pecan/CAISO/AEMO/JEPX/NREL) require user-provided cached CSV at
``$GRIDFLOW_DATASET_ROOT/<dataset_id>/data.csv``. See each loader docstring.
"""

from .aemo_tesla_vpp_loader import AEMO_TESLA_VPP_METADATA, AEMOTeslaVPPLoader
from .caiso_loader import CAISO_SYSTEM_LOAD_METADATA, CAISOLoader
from .jepx_loader import JEPX_SPOT_PRICE_METADATA, JEPXLoader
from .nrel_resstock_loader import NREL_RESSTOCK_METADATA, NRELResStockLoader
from .pecan_street_loader import (
    PECAN_STREET_RESIDENTIAL_EV_METADATA,
    PecanStreetLoader,
)
from gridflow.domain.dataset import DatasetLoader, DatasetMetadata

from .synthetic_loader import SYNTHETIC_VPP_METADATA, SyntheticLoader

# Convenience: every metadata block in one tuple for catalog seeding
ALL_REGISTERED_METADATAS: tuple[DatasetMetadata, ...] = (
    SYNTHETIC_VPP_METADATA,
    PECAN_STREET_RESIDENTIAL_EV_METADATA,
    CAISO_SYSTEM_LOAD_METADATA,
    AEMO_TESLA_VPP_METADATA,
    JEPX_SPOT_PRICE_METADATA,
    NREL_RESSTOCK_METADATA,
)

# Convenience: every loader available
ALL_LOADERS: tuple[DatasetLoader, ...] = (
    SyntheticLoader(),
    PecanStreetLoader(),
    CAISOLoader(),
    AEMOTeslaVPPLoader(),
    JEPXLoader(),
    NRELResStockLoader(),
)


__all__ = (
    "AEMO_TESLA_VPP_METADATA",
    "ALL_LOADERS",
    "ALL_REGISTERED_METADATAS",
    "CAISO_SYSTEM_LOAD_METADATA",
    "JEPX_SPOT_PRICE_METADATA",
    "NREL_RESSTOCK_METADATA",
    "PECAN_STREET_RESIDENTIAL_EV_METADATA",
    "SYNTHETIC_VPP_METADATA",
    "AEMOTeslaVPPLoader",
    "CAISOLoader",
    "JEPXLoader",
    "NRELResStockLoader",
    "PecanStreetLoader",
    "SyntheticLoader",
)
