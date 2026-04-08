"""Filesystem-backed ``ScenarioRegistry`` implementation.

Storage layout::

    <root>/
      <pack_id>/
        pack.json        # serialised ScenarioPack.to_dict() + status

Only a JSON index is written; the original YAML/network files stay wherever
``network_dir`` points. This keeps the registry side-effect-light and makes it
trivial to inspect state during tests.
"""

from __future__ import annotations

import contextlib
import json
import re
from datetime import UTC, datetime
from pathlib import Path

from gridflow.domain.error import PackNotFoundError, PackValidationError, RegistryError
from gridflow.domain.scenario.registry import ScenarioRegistry
from gridflow.domain.scenario.scenario_pack import (
    PackMetadata,
    PackStatus,
    ScenarioPack,
)
from gridflow.domain.util.params import as_params

_VALID_PACK_ID = re.compile(r"^[A-Za-z0-9._@+-]+$")


def _parse_iso(value: str) -> datetime:
    dt = datetime.fromisoformat(value)
    return dt if dt.tzinfo is not None else dt.replace(tzinfo=UTC)


class FileScenarioRegistry(ScenarioRegistry):
    """Directory-backed registry. One subdirectory per pack."""

    def __init__(self, root: Path) -> None:
        self._root = Path(root)
        self._root.mkdir(parents=True, exist_ok=True)

    # ------------------------------------------------------------------ write

    def register(self, pack: ScenarioPack) -> ScenarioPack:
        pack.validate()
        if not _VALID_PACK_ID.match(pack.pack_id):
            raise PackValidationError(f"Invalid pack_id '{pack.pack_id}': allowed characters are [A-Za-z0-9._@+-]")
        registered = pack.with_status(PackStatus.REGISTERED)
        self._write(registered)
        return registered

    def update_status(self, pack_id: str, new_status: PackStatus) -> ScenarioPack:
        current = self.get(pack_id)
        updated = current.with_status(new_status)
        self._write(updated)
        return updated

    def delete(self, pack_id: str) -> None:
        target = self._pack_file(pack_id)
        if not target.exists():
            raise PackNotFoundError(f"pack_id '{pack_id}' not found", context={"pack_id": pack_id})
        target.unlink()
        # Non-empty dir — leave it alone.
        with contextlib.suppress(OSError):
            target.parent.rmdir()

    # ------------------------------------------------------------------- read

    def get(self, pack_id: str) -> ScenarioPack:
        target = self._pack_file(pack_id)
        if not target.exists():
            raise PackNotFoundError(f"pack_id '{pack_id}' not found", context={"pack_id": pack_id})
        return self._read(target)

    def list_all(self) -> tuple[ScenarioPack, ...]:
        packs: list[ScenarioPack] = []
        for pack_dir in sorted(self._root.iterdir()):
            pack_file = pack_dir / "pack.json"
            if pack_file.exists():
                packs.append(self._read(pack_file))
        return tuple(packs)

    # --------------------------------------------------------------- internals

    def _pack_file(self, pack_id: str) -> Path:
        return self._root / pack_id / "pack.json"

    def _write(self, pack: ScenarioPack) -> None:
        target = self._pack_file(pack.pack_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        tmp = target.with_suffix(".json.tmp")
        try:
            tmp.write_text(json.dumps(pack.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
            tmp.replace(target)
        except OSError as exc:
            raise RegistryError(
                f"Failed to persist pack '{pack.pack_id}'",
                context={"pack_id": pack.pack_id, "target": str(target)},
                cause=exc,
            ) from exc

    def _read(self, pack_file: Path) -> ScenarioPack:
        try:
            data = json.loads(pack_file.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise RegistryError(
                f"Corrupted pack index: {pack_file}",
                context={"target": str(pack_file)},
                cause=exc,
            ) from exc

        meta_raw = data["metadata"]
        metadata = PackMetadata(
            name=meta_raw["name"],
            version=meta_raw["version"],
            description=meta_raw["description"],
            author=meta_raw["author"],
            created_at=_parse_iso(meta_raw["created_at"]),
            connector=meta_raw["connector"],
            seed=meta_raw.get("seed"),
            parameters=as_params(meta_raw.get("parameters") or {}),
        )
        return ScenarioPack(
            pack_id=data["pack_id"],
            name=data["name"],
            version=data["version"],
            metadata=metadata,
            network_dir=Path(data["network_dir"]),
            timeseries_dir=Path(data["timeseries_dir"]),
            config_dir=Path(data["config_dir"]),
            status=PackStatus(data["status"]),
        )
