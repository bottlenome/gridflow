"""Filesystem-backed dataset registry.

Spec: ``docs/dataset_contribution.md`` §1.3.

In-memory variant suitable for tests, plus a filesystem-backed
implementation that reads metadata json files from
``~/.gridflow/datasets/`` (or any configured root).

Both implementations satisfy ``gridflow.domain.dataset.DatasetRegistry``.
"""

from __future__ import annotations

import json
from collections.abc import Iterable, Mapping
from dataclasses import asdict
from pathlib import Path
from typing import Any

from gridflow.domain.dataset import (
    DatasetLicense,
    DatasetMetadata,
)
from gridflow.domain.dataset.dataset import LICENSE_NAMES


def _metadata_to_jsonable(m: DatasetMetadata) -> dict[str, object]:
    d: dict[str, object] = asdict(m)
    # Enum → string for JSON
    d["license"] = m.license.value
    d["units"] = [list(pair) for pair in m.units]
    d["contributors"] = list(m.contributors)
    return d


def _metadata_from_jsonable(d: Mapping[str, Any]) -> DatasetMetadata:
    return DatasetMetadata(
        dataset_id=d["dataset_id"],
        title=d["title"],
        description=d["description"],
        source=d["source"],
        license=DatasetLicense(d["license"]) if d["license"] in LICENSE_NAMES else DatasetLicense.OTHER,
        retrieval_url=d["retrieval_url"],
        doi=d["doi"],
        retrieval_method=d["retrieval_method"],
        sha256=d["sha256"],
        time_resolution_seconds=int(d["time_resolution_seconds"]),
        period_start_iso=d["period_start_iso"],
        period_end_iso=d["period_end_iso"],
        units=tuple((pair[0], pair[1]) for pair in d["units"]),
        contributors=tuple(d["contributors"]),
        added_at_iso=d["added_at_iso"],
    )


class InMemoryDatasetRegistry:
    """Holds ``DatasetMetadata`` instances in memory.

    Suitable for unit tests and small-scale workflows.
    """

    def __init__(self, metadatas: Iterable[DatasetMetadata] = ()):
        self._by_id: dict[str, DatasetMetadata] = {m.dataset_id: m for m in metadatas}

    def register(self, m: DatasetMetadata) -> None:
        self._by_id[m.dataset_id] = m

    def list_ids(self) -> tuple[str, ...]:
        return tuple(sorted(self._by_id))

    def get_metadata(self, dataset_id: str) -> DatasetMetadata:
        if dataset_id not in self._by_id:
            raise KeyError(dataset_id)
        return self._by_id[dataset_id]

    def find_by_source(self, source: str) -> tuple[DatasetMetadata, ...]:
        s = source.lower()
        return tuple(m for m in self._by_id.values() if s in m.source.lower())

    def filter_by_license(self, *, redistributable: bool) -> tuple[DatasetMetadata, ...]:
        REDIST = {
            DatasetLicense.CC0_1_0,
            DatasetLicense.CC_BY_4_0,
            DatasetLicense.CC_BY_SA_4_0,
            DatasetLicense.ODC_BY_1_0,
            DatasetLicense.APACHE_2_0,
            DatasetLicense.MIT,
            DatasetLicense.PUBLIC_DOMAIN,
        }
        if redistributable:
            return tuple(m for m in self._by_id.values() if m.license in REDIST)
        return tuple(m for m in self._by_id.values() if m.license not in REDIST)


class FilesystemDatasetRegistry(InMemoryDatasetRegistry):
    """Reads metadata JSON files from a directory tree.

    Layout: ``<root>/<source>/<name>/<version>/metadata.json`` (one file
    per dataset). The ``metadata.json`` payload is the JSON-serialised
    form of :class:`DatasetMetadata`.
    """

    def __init__(self, root: Path):
        super().__init__()
        self.root = Path(root)
        self.reload()

    def reload(self) -> None:
        self._by_id = {}
        if not self.root.exists():
            return
        for json_path in self.root.rglob("metadata.json"):
            try:
                d = json.loads(json_path.read_text(encoding="utf-8"))
                m = _metadata_from_jsonable(d)
                self._by_id[m.dataset_id] = m
            except Exception as e:
                # Skip corrupt entries but log via stderr to avoid swallow
                import sys

                print(f"[FilesystemDatasetRegistry] skipping {json_path}: {e}", file=sys.stderr)

    def write(self, m: DatasetMetadata) -> Path:
        """Persist metadata to disk, returning the path."""
        parts = m.dataset_id.split("/")
        path = self.root.joinpath(*parts) / "metadata.json"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(
            json.dumps(_metadata_to_jsonable(m), indent=2, sort_keys=True),
            encoding="utf-8",
        )
        super().register(m)
        return path
