"""Load a ``ScenarioPack`` from a ``pack.yaml`` file on disk.

This is an Infrastructure helper: it reads YAML, builds the immutable Domain
model, then hands it off to the Registry. Validation errors bubble up as
``PackValidationError`` (Domain).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import cast

import yaml

from gridflow.domain.error import PackValidationError
from gridflow.domain.scenario.scenario_pack import PackMetadata, PackStatus, ScenarioPack
from gridflow.domain.util.params import as_params


def _coerce_created_at(raw: object) -> datetime:
    """Parse a ``created_at`` value from YAML into a timezone-aware datetime."""
    if raw is None:
        return datetime.now(tz=UTC)
    if isinstance(raw, datetime):
        return raw if raw.tzinfo is not None else raw.replace(tzinfo=UTC)
    if isinstance(raw, str):
        # datetime.fromisoformat handles "2026-01-01T00:00:00+00:00" style
        parsed = datetime.fromisoformat(raw)
        return parsed if parsed.tzinfo is not None else parsed.replace(tzinfo=UTC)
    raise PackValidationError(f"Unsupported created_at type: {type(raw).__name__}")


def load_pack_from_yaml(yaml_path: Path, *, pack_id: str | None = None) -> ScenarioPack:
    """Build a ``ScenarioPack`` from a ``pack.yaml`` file.

    Schema (relaxed for MVP):
        pack:
          name: str
          version: str
          description: str
          author: str
          connector: str
          seed: int | null
          created_at: ISO8601 datetime (optional, defaults to now)
        parameters:           # optional, becomes metadata.parameters
          key: value
          ...
        network:              # optional; directory resolution hint
          dir: relative path, defaults to yaml_path.parent

    Args:
        yaml_path: Path to the YAML file.
        pack_id: Explicit pack ID. When ``None``, uses
            ``"{name}@{version}"``.

    Returns:
        A fully-populated :class:`ScenarioPack` in ``DRAFT`` status.

    Raises:
        PackValidationError: On missing required fields or schema errors.
    """
    if not yaml_path.exists():
        raise PackValidationError(f"pack.yaml not found: {yaml_path}")

    raw_text = yaml_path.read_text(encoding="utf-8")
    try:
        data = yaml.safe_load(raw_text) or {}
    except yaml.YAMLError as exc:
        raise PackValidationError(f"Malformed YAML: {yaml_path}") from exc

    if not isinstance(data, dict):
        raise PackValidationError(f"pack.yaml root must be a mapping, got {type(data).__name__}")

    pack_section = data.get("pack")
    if not isinstance(pack_section, dict):
        raise PackValidationError("pack.yaml must contain a top-level 'pack' mapping")

    required = ("name", "version", "description", "author", "connector")
    for key in required:
        if not pack_section.get(key):
            raise PackValidationError(f"pack.{key} is required")

    name = str(pack_section["name"])
    version = str(pack_section["version"])

    metadata = PackMetadata(
        name=name,
        version=version,
        description=str(pack_section["description"]),
        author=str(pack_section["author"]),
        created_at=_coerce_created_at(pack_section.get("created_at")),
        connector=str(pack_section["connector"]),
        seed=cast("int | None", pack_section.get("seed")),
        parameters=as_params(cast("dict[str, object] | None", data.get("parameters"))),
    )

    base_dir = yaml_path.parent
    network_section = data.get("network")
    if isinstance(network_section, dict) and "dir" in network_section:
        network_dir = (base_dir / str(network_section["dir"])).resolve()
    else:
        network_dir = base_dir
    timeseries_dir = (base_dir / "timeseries") if (base_dir / "timeseries").exists() else base_dir
    config_dir = (base_dir / "config") if (base_dir / "config").exists() else base_dir

    pack = ScenarioPack(
        pack_id=pack_id or f"{name}@{version}",
        name=name,
        version=version,
        metadata=metadata,
        network_dir=network_dir,
        timeseries_dir=timeseries_dir,
        config_dir=config_dir,
        status=PackStatus.DRAFT,
    )
    pack.validate()
    return pack
