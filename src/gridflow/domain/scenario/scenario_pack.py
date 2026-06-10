"""ScenarioPack and PackMetadata domain models."""

from __future__ import annotations

import enum
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path

from gridflow.domain.error import PackValidationError
from gridflow.domain.util.params import Params, params_to_dict


class PackStatus(enum.Enum):
    """Scenario Pack lifecycle status."""

    DRAFT = "draft"
    VALIDATED = "validated"
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass(frozen=True)
class PackMetadata:
    """Metadata for a Scenario Pack.

    Frozen & hashable. All attributes are immutable; the free-form ``parameters``
    field uses the tuple-of-tuples convention from ``gridflow.domain.util.params``.

    Attributes:
        name: Metadata name.
        version: Version string.
        description: Pack description.
        author: Creator name.
        created_at: Creation timestamp.
        connector: Connector name to use.
        seed: Random seed for reproducibility.
        parameters: Additional parameters.
        baseline: True if this pack is an official baseline researchers
            are expected to clone and compare against (AS-5 (1)).
        citation: Bibliographic reference for the baseline (paper /
            dataset the pack reproduces); empty when not applicable.
    """

    name: str
    version: str
    description: str
    author: str
    created_at: datetime
    connector: str
    seed: int | None = None
    parameters: Params = ()
    baseline: bool = False
    citation: str = ""

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation."""
        return {
            "name": self.name,
            "version": self.version,
            "description": self.description,
            "author": self.author,
            "created_at": self.created_at.isoformat(),
            "connector": self.connector,
            "seed": self.seed,
            "parameters": params_to_dict(self.parameters),
            "baseline": self.baseline,
            "citation": self.citation,
        }


@dataclass(frozen=True)
class ScenarioPack:
    """Experiment package data model.

    Frozen dataclass. Lifecycle status changes must go through
    :meth:`with_status`, which returns a *new* instance — the ``Registry``
    implementation is responsible for persisting the new reference.

    Attributes:
        pack_id: Unique identifier for the pack.
        name: Pack name.
        version: Version string.
        metadata: Pack metadata.
        network_dir: Path to network definition directory.
        timeseries_dir: Path to time series data directory.
        config_dir: Path to configuration directory.
        status: Current lifecycle status.
        cloned_from: ``pack_id`` of the pack this one was cloned from
            (provenance for baseline-comparison studies, AS-5 (1));
            empty for packs created from scratch.
    """

    pack_id: str
    name: str
    version: str
    metadata: PackMetadata
    network_dir: Path
    timeseries_dir: Path
    config_dir: Path
    status: PackStatus = PackStatus.DRAFT
    cloned_from: str = ""

    def with_status(self, new_status: PackStatus) -> ScenarioPack:
        """Return a copy of this pack with ``status`` replaced.

        Preferred API for lifecycle transitions — direct field assignment is
        impossible because the dataclass is frozen.
        """
        from dataclasses import replace

        return replace(self, status=new_status)

    def clone(self, new_pack_id: str) -> ScenarioPack:
        """Return a derivative copy of this pack under a new identity.

        AS-5 (1): researchers clone a baseline pack and swap in their own
        method to write comparison papers. The clone keeps all content and
        the ``citation`` (provenance), but:

        * starts in ``DRAFT`` status,
        * is never itself a baseline (``metadata.baseline = False``),
        * records this pack's ``pack_id`` in ``cloned_from``.

        Raises:
            PackValidationError: If ``new_pack_id`` is empty or identical
                to this pack's ``pack_id``.
        """
        from dataclasses import replace

        if not new_pack_id:
            raise PackValidationError("clone: new_pack_id must not be empty")
        if new_pack_id == self.pack_id:
            raise PackValidationError(f"clone: new_pack_id must differ from the original pack_id '{self.pack_id}'")
        return replace(
            self,
            pack_id=new_pack_id,
            metadata=replace(self.metadata, baseline=False),
            status=PackStatus.DRAFT,
            cloned_from=self.pack_id,
        )

    def to_dict(self) -> dict[str, object]:
        """Convert to dictionary representation (JSON-serialisable)."""
        return {
            "pack_id": self.pack_id,
            "name": self.name,
            "version": self.version,
            "metadata": self.metadata.to_dict(),
            "network_dir": str(self.network_dir),
            "timeseries_dir": str(self.timeseries_dir),
            "config_dir": str(self.config_dir),
            "status": self.status.value,
            "cloned_from": self.cloned_from,
        }

    def validate(self) -> None:
        """Validate pack structural invariants.

        Only pure (non-IO) checks belong here — filesystem presence is verified
        by the Registry implementation at ingest time.

        Raises:
            PackValidationError: If any invariant is violated.
        """
        if not self.pack_id:
            raise PackValidationError("ScenarioPack.pack_id must not be empty")
        if not self.name:
            raise PackValidationError("ScenarioPack.name must not be empty")
        if not self.version:
            raise PackValidationError("ScenarioPack.version must not be empty")
        if self.metadata.name != self.name:
            raise PackValidationError(
                f"ScenarioPack.name '{self.name}' does not match metadata.name '{self.metadata.name}'"
            )
        if self.metadata.version != self.version:
            raise PackValidationError(
                f"ScenarioPack.version '{self.version}' does not match metadata.version '{self.metadata.version}'"
            )
        if not self.metadata.connector:
            raise PackValidationError("ScenarioPack.metadata.connector must not be empty")
