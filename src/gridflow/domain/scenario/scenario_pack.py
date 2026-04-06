"""ScenarioPack and PackMetadata domain models."""

from __future__ import annotations

import enum
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path


class PackStatus(enum.Enum):
    """Scenario Pack lifecycle status."""

    DRAFT = "draft"
    VALIDATED = "validated"
    REGISTERED = "registered"
    RUNNING = "running"
    COMPLETED = "completed"


@dataclass
class PackMetadata:
    """Metadata for a Scenario Pack.

    Attributes:
        name: Metadata name.
        version: Version string.
        description: Pack description.
        author: Creator name.
        created_at: Creation timestamp.
        connector: Connector name to use.
        seed: Random seed for reproducibility.
        parameters: Additional parameters.
    """

    name: str
    version: str
    description: str
    author: str
    created_at: datetime
    connector: str
    seed: int | None = None
    parameters: dict[str, object] = field(default_factory=dict)


@dataclass
class ScenarioPack:
    """Experiment package data model.

    Attributes:
        pack_id: Unique identifier for the pack.
        name: Pack name.
        version: Version string.
        metadata: Pack metadata.
        network_dir: Path to network definition directory.
        timeseries_dir: Path to time series data directory.
        config_dir: Path to configuration directory.
        status: Current lifecycle status.
    """

    pack_id: str
    name: str
    version: str
    metadata: PackMetadata
    network_dir: Path
    timeseries_dir: Path
    config_dir: Path
    status: PackStatus = PackStatus.DRAFT
