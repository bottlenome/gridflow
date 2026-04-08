"""YAML-first configuration manager with env-var override.

Lookup precedence (highest first) per DD-CFG-001:
    1. Explicit overrides passed to :meth:`set`
    2. Environment variables ``GRIDFLOW_<KEY>`` (nested keys join by ``__``)
    3. The parsed YAML file(s)
    4. Built-in defaults registered via :meth:`set_defaults`

Values are accessed with dotted keys: ``cfg.get("logging.level")``.
"""

from __future__ import annotations

import os
from pathlib import Path
from typing import Any

import yaml

from gridflow.domain.error import ConfigError


class ConfigManager:
    """Hierarchical YAML + env-var configuration holder."""

    _ENV_PREFIX = "GRIDFLOW_"

    def __init__(self) -> None:
        self._defaults: dict[str, Any] = {}
        self._file: dict[str, Any] = {}
        self._overrides: dict[str, Any] = {}

    # ---------------------------------------------------------------- loading

    def load_file(self, path: Path) -> None:
        """Load configuration from a YAML file.

        Subsequent calls merge on top of the previous state (later wins).

        Raises:
            ConfigError: If the file is missing or malformed.
        """
        if not path.exists():
            raise ConfigError(f"Config file not found: {path}", context={"path": str(path)})
        try:
            parsed = yaml.safe_load(path.read_text(encoding="utf-8")) or {}
        except yaml.YAMLError as exc:
            raise ConfigError(f"Malformed YAML config: {path}", context={"path": str(path)}, cause=exc) from exc
        if not isinstance(parsed, dict):
            raise ConfigError(
                f"Config root must be a mapping, got {type(parsed).__name__}",
                context={"path": str(path)},
            )
        self._file = _deep_merge(self._file, parsed)

    def set_defaults(self, defaults: dict[str, Any]) -> None:
        """Register built-in defaults (lowest precedence layer)."""
        self._defaults = _deep_merge(self._defaults, defaults)

    # ----------------------------------------------------------------- access

    def set(self, key: str, value: Any) -> None:
        """Set an explicit override (highest precedence, in-process only)."""
        _set_nested(self._overrides, key.split("."), value)

    def get(self, key: str, default: Any | None = None) -> Any:
        """Retrieve a configuration value by dotted key."""
        parts = key.split(".")

        override = _get_nested(self._overrides, parts)
        if override is not _MISSING:
            return override

        env_value = self._lookup_env(parts)
        if env_value is not None:
            return env_value

        file_value = _get_nested(self._file, parts)
        if file_value is not _MISSING:
            return file_value

        default_value = _get_nested(self._defaults, parts)
        if default_value is not _MISSING:
            return default_value

        return default

    def require(self, key: str) -> Any:
        """Look up a value that must exist.

        Raises:
            ConfigError: If the key is unset.
        """
        value = self.get(key, default=_MISSING)
        if value is _MISSING:
            raise ConfigError(f"Required config key missing: {key}", context={"key": key})
        return value

    def as_dict(self) -> dict[str, Any]:
        """Return the fully-merged configuration as a plain dict."""
        merged = _deep_merge(self._defaults, self._file)
        merged = _deep_merge(merged, self._overrides)
        return merged

    # ----------------------------------------------------------------- internals

    def _lookup_env(self, parts: list[str]) -> str | None:
        env_key = self._ENV_PREFIX + "__".join(p.upper() for p in parts)
        return os.environ.get(env_key)


# ----------------------------------------------------------------- helpers


class _Missing:
    """Sentinel for "key not present" — distinct from ``None``."""


_MISSING = _Missing()


def _deep_merge(base: dict[str, Any], overlay: dict[str, Any]) -> dict[str, Any]:
    """Return a new dict where ``overlay`` values win on conflicts."""
    result = dict(base)
    for key, value in overlay.items():
        existing = result.get(key)
        if isinstance(existing, dict) and isinstance(value, dict):
            result[key] = _deep_merge(existing, value)
        else:
            result[key] = value
    return result


def _set_nested(container: dict[str, Any], parts: list[str], value: Any) -> None:
    cursor: dict[str, Any] = container
    for part in parts[:-1]:
        nxt = cursor.get(part)
        if not isinstance(nxt, dict):
            nxt = {}
            cursor[part] = nxt
        cursor = nxt
    cursor[parts[-1]] = value


def _get_nested(container: dict[str, Any], parts: list[str]) -> Any:
    cursor: Any = container
    for part in parts:
        if not isinstance(cursor, dict) or part not in cursor:
            return _MISSING
        cursor = cursor[part]
    return cursor
