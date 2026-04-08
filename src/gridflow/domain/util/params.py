"""Helpers for the ``tuple[tuple[str, object], ...]`` params convention.

Rationale (phase0_result §7.2 5.8, CLAUDE.md §0 妥協なき設計原則):
    Frozen dataclasses must not hold mutable containers. Every ``parameters`` /
    ``metadata`` / ``properties`` style attribute is therefore a *sorted* tuple
    of ``(key, value)`` pairs, which is hashable, deeply immutable, and has a
    deterministic ordering for equality/hash.

    Because tuple-of-tuples is inconvenient to read/write directly, all access
    in the codebase is routed through these small function helpers. Do **not**
    scatter ``dict(obj.parameters)`` calls — prefer :func:`get_param` /
    :func:`params_to_dict` so we keep a single place to revisit if the convention
    ever changes.
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping
from typing import TypeAlias

Params: TypeAlias = tuple[tuple[str, object], ...]
"""Canonical type alias for the frozen params representation."""


def as_params(mapping: Mapping[str, object] | Iterable[tuple[str, object]] | None) -> Params:
    """Normalise a mapping or pair-iterable into the canonical :data:`Params` form.

    The output is sorted by key so two equivalent inputs always yield identical
    tuples (and thus identical hashes).

    Args:
        mapping: Source mapping or iterable of ``(key, value)`` pairs. ``None``
            is accepted as shorthand for "no params" and returns an empty tuple.

    Returns:
        A tuple of ``(key, value)`` pairs sorted by key.

    Raises:
        TypeError: If any key is not a string.
    """
    if mapping is None:
        return ()
    items: Iterable[tuple[str, object]]
    items = mapping.items() if isinstance(mapping, Mapping) else mapping
    materialised = tuple(items)
    for key, _ in materialised:
        if not isinstance(key, str):
            raise TypeError(f"Params keys must be str, got {type(key).__name__}")
    return tuple(sorted(materialised, key=lambda kv: kv[0]))


def get_param(params: Params, key: str, default: object = None) -> object:
    """Look up ``key`` in a :data:`Params` tuple.

    O(n) scan — acceptable because params are small (≤ a few dozen entries).

    Args:
        params: Params tuple to search.
        key: Key to look up.
        default: Value returned if the key is absent.

    Returns:
        The stored value, or ``default`` if not found.
    """
    for k, v in params:
        if k == key:
            return v
    return default


def params_to_dict(params: Params) -> dict[str, object]:
    """Rehydrate a :data:`Params` tuple into a plain ``dict``.

    Only use when you truly need a dict (e.g. JSON serialisation boundary).
    Prefer :func:`get_param` for single lookups.
    """
    return dict(params)
