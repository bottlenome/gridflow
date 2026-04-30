"""Protocols for dataset loaders and registries.

Spec: ``docs/dataset_contribution.md``.

Concrete loader implementations live in the adapter layer
(``gridflow.adapter.dataset``). The interfaces here are pure Domain.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from .dataset import DatasetMetadata, DatasetSpec, DatasetTimeSeries


@runtime_checkable
class DatasetLoader(Protocol):
    """A pure function from :class:`DatasetSpec` to :class:`DatasetTimeSeries`.

    Implementations are responsible for:
      * Honouring the ``spec.dataset_id`` to dispatch to the correct
        underlying source.
      * Slicing by ``spec.time_range`` and ``spec.channel_filter``.
      * Validating that the returned payload matches the recorded
        ``metadata.sha256`` (= reproducibility invariant).

    The loader does **not** decide where to cache or what to fetch — it
    is a pure transformer. Caching is handled by the registry layer.
    """

    name: str

    def supports(self, dataset_id: str) -> bool: ...

    def load(self, spec: DatasetSpec) -> DatasetTimeSeries: ...


@runtime_checkable
class DatasetRegistry(Protocol):
    """Catalogue of registered datasets.

    A registry knows the metadata of every dataset that has been
    contributed to gridflow. It does not necessarily hold the data
    payloads — those are loaded on demand via :class:`DatasetLoader`.
    """

    def list_ids(self) -> tuple[str, ...]:
        """Return the IDs of all known datasets, sorted lexicographically."""

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        """Return metadata for a registered dataset.

        Raises ``KeyError`` if not registered.
        """

    def find_by_source(self, source: str) -> tuple[DatasetMetadata, ...]:
        """Return all datasets whose source matches (substring, case-insensitive)."""

    def filter_by_license(self, *, redistributable: bool) -> tuple[DatasetMetadata, ...]:
        """Return datasets whose license permits redistribution.

        ``redistributable=True`` excludes proprietary / registration-required
        sources.
        """
