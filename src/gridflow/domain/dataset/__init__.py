"""Domain types for real-world dataset integration.

Spec: ``docs/dataset_contribution.md``.

A :class:`Dataset` describes a real-world time-series source that can be
consumed by gridflow scenarios. Examples include:

  * VPP availability traces (Tesla Powerwall, JEPX VPP実証)
  * Distribution feeder load profiles (Pecan Street, NREL ResStock)
  * Wholesale market prices (CAISO OASIS, JEPX, ENTSO-E)
  * EV charging demand (EVNet, Open Charge Map)

Each dataset is described by a frozen :class:`DatasetMetadata` value
object and accessed via the runtime-checkable :class:`DatasetLoader`
Protocol. Concrete loaders live in
``gridflow.adapter.dataset.<source>_loader``.

Design (CLAUDE.md §0.1):
  * Metadata is frozen dataclass with deterministic provenance fields
    (DOI, license, retrieval_url, sha256 of the cached payload).
  * Loaders are pure: ``DatasetLoader.load(spec)`` returns a frozen
    :class:`DatasetTimeSeries` value.
  * Caching is content-addressed via ``sha256``; reproducibility is a
    domain invariant.
"""

from .dataset import (
    DatasetLicense,
    DatasetMetadata,
    DatasetSpec,
    DatasetTimeSeries,
    LICENSE_NAMES,
)
from .interfaces import DatasetLoader, DatasetRegistry

__all__ = (
    "DatasetLicense",
    "DatasetMetadata",
    "DatasetSpec",
    "DatasetTimeSeries",
    "LICENSE_NAMES",
    "DatasetLoader",
    "DatasetRegistry",
)
