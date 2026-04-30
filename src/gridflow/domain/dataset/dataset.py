"""Frozen value objects for real-world datasets.

Spec: ``docs/dataset_contribution.md``.

The dataset domain decouples *what* a dataset is (metadata, license,
provenance) from *how* it is fetched (loader implementations). All
types here are frozen dataclasses with hashable equality.
"""

from __future__ import annotations

import enum
from dataclasses import dataclass, field

from gridflow.domain.util.params import Params


class DatasetLicense(enum.Enum):
    """SPDX-style license identifier for a dataset."""

    CC_BY_4_0 = "CC-BY-4.0"
    CC_BY_SA_4_0 = "CC-BY-SA-4.0"
    CC0_1_0 = "CC0-1.0"
    ODC_BY_1_0 = "ODC-BY-1.0"
    APACHE_2_0 = "Apache-2.0"
    MIT = "MIT"
    PROPRIETARY_RESEARCH = "Proprietary-Research-Use-Only"
    PUBLIC_DOMAIN = "Public-Domain"
    OTHER = "Other"


LICENSE_NAMES: tuple[str, ...] = tuple(member.value for member in DatasetLicense)


@dataclass(frozen=True)
class DatasetMetadata:
    """Provenance metadata for a real-world dataset.

    Attributes:
        dataset_id: Stable identifier within the gridflow registry.
            Convention: ``<source>/<name>/<version>`` (e.g.
            ``pecanstreet/residential_ev/2024-01``).
        title: Human-readable name.
        description: One-paragraph description of contents.
        source: Organisation / project (e.g. "Pecan Street Inc.").
        license: SPDX-style identifier. Use
            :class:`DatasetLicense.PROPRIETARY_RESEARCH` for non-redistributable.
        retrieval_url: Canonical URL where the dataset can be obtained.
            Empty string if local-only.
        doi: DOI string (with or without ``https://doi.org/`` prefix).
            Empty string if no DOI.
        retrieval_method: How to obtain the dataset:
            ``"public_download"`` / ``"registration_required"`` /
            ``"private"`` / ``"synthetic"``.
        sha256: SHA-256 digest of the canonical payload (after any
            normalisation steps documented in the loader).
        time_resolution_seconds: Sample period in seconds.
        period_start_iso: ISO-8601 start of the available range.
        period_end_iso: ISO-8601 end of the available range.
        units: Tuple of ``(channel_name, unit)`` pairs. e.g.
            ``(("active_power", "kW"), ("availability", "fraction"))``.
        contributors: Tuple of contributors (gridflow PR authors etc.)
            for accountability.
        added_at_iso: When the dataset was added to the registry.
    """

    dataset_id: str
    title: str
    description: str
    source: str
    license: DatasetLicense
    retrieval_url: str
    doi: str
    retrieval_method: str
    sha256: str
    time_resolution_seconds: int
    period_start_iso: str
    period_end_iso: str
    units: tuple[tuple[str, str], ...]
    contributors: tuple[str, ...]
    added_at_iso: str


@dataclass(frozen=True)
class DatasetSpec:
    """A request for a slice of a dataset.

    A spec selects a portion of a registered dataset for use in an
    experiment. Loaders honour the spec to return a :class:`DatasetTimeSeries`.

    Attributes:
        dataset_id: ID of a registered :class:`DatasetMetadata`.
        time_range: (start_iso, end_iso) inclusive of start, exclusive of end.
            Empty tuple means "use the full available range".
        channel_filter: Tuple of channel names to retain. Empty = all.
        params: Optional source-specific parameters (e.g. household IDs,
            station IDs, region filters) as the canonical frozen
            params-tuple.
    """

    dataset_id: str
    time_range: tuple[str, str] = ()
    channel_filter: tuple[str, ...] = ()
    params: Params = ()


@dataclass(frozen=True)
class DatasetTimeSeries:
    """The data payload returned by a loader.

    A multi-channel time series, value-objects only. Concrete numerical
    arrays are tuples of floats — preserving frozenness at the cost of
    some memory. Adapters may convert to numpy on the fly when needed.

    Attributes:
        spec: The spec that produced this slice.
        metadata: Metadata of the source dataset.
        timestamps_iso: Per-step ISO-8601 timestamps.
        channels: Per-channel data; a tuple of
            ``(channel_name, units, values)`` triples where ``values`` is
            a tuple of floats aligned with ``timestamps_iso``.
    """

    spec: DatasetSpec
    metadata: DatasetMetadata
    timestamps_iso: tuple[str, ...]
    channels: tuple[tuple[str, str, tuple[float, ...]], ...]

    @property
    def n_steps(self) -> int:
        return len(self.timestamps_iso)

    def channel(self, name: str) -> tuple[float, ...]:
        for ch_name, _unit, values in self.channels:
            if ch_name == name:
                return values
        raise KeyError(f"channel '{name}' not in dataset {self.metadata.dataset_id}")
