"""Deterministic, cross-process-stable hashing for reproducible research.

Rationale (CLAUDE.md §0.2 — 再現性が生命線; issue #19):
    Python's builtin :func:`hash` is salted per process (PEP 456) for str /
    bytes, so any synthetic attribute or seed derived from it changes between
    runs. In a research trial (``test/mvp_try16``) that non-determinism turned
    a tail-metric ranking into an artifact that survived self-review as a
    "discovery". The fix there was to hand-roll a SHA-256 hash; this module
    makes that the standard, blessed path so no trial has a reason to reach
    for the builtin again.

Guarantees:
    * Same input → same output, in this and every other process, forever
      (SHA-256 is fixed).
    * Distinct *typed* inputs almost never collide: values are serialised with
      a type tag, so ``stable_hash("1")`` != ``stable_hash(1)`` and
      ``stable_hash((1, 2))`` != ``stable_hash((12,))``.
    * Nested tuples / lists of the supported scalar types are supported.

Supported leaf types: ``str``, ``bytes``, ``bool``, ``int``, ``float``,
``None``. Containers: ``tuple`` / ``list`` of supported values. Anything else
raises :class:`TypeError` rather than silently stringifying — a silent
``repr`` fallback would reintroduce the very non-determinism this module
exists to remove (object ``repr`` often embeds an address).
"""

from __future__ import annotations

import hashlib
import struct
from collections.abc import Sequence
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from hashlib import _Hash

# A 63-bit mask keeps results non-negative and inside the range accepted by
# ``random.Random(seed)`` and ordinary signed-64 integer comparisons.
_MASK_63 = (1 << 63) - 1


def _feed(hasher: _Hash, value: object) -> None:
    """Absorb ``value`` into ``hasher`` with a leading type tag.

    The type tag is what makes the encoding injective across types: two values
    that would serialise to the same bytes still differ because their tags do.
    """
    if value is None:
        hasher.update(b"N")
    elif isinstance(value, bool):
        # Must precede ``int`` — bool is an int subclass.
        hasher.update(b"b\x01" if value else b"b\x00")
    elif isinstance(value, int):
        hasher.update(b"i")
        # Sign byte + big-endian magnitude, so length is unambiguous.
        neg = value < 0
        mag = -value if neg else value
        body = mag.to_bytes((mag.bit_length() + 7) // 8, "big")
        hasher.update(b"-" if neg else b"+")
        hasher.update(struct.pack(">I", len(body)))
        hasher.update(body)
    elif isinstance(value, float):
        # IEEE-754 big-endian is a fixed 8-byte representation; NaN/inf hash
        # deterministically too. Normalise -0.0 to 0.0 so they don't diverge.
        hasher.update(b"f")
        normalised = 0.0 if value == 0.0 else value
        hasher.update(struct.pack(">d", normalised))
    elif isinstance(value, bytes):
        hasher.update(b"y")
        hasher.update(struct.pack(">I", len(value)))
        hasher.update(value)
    elif isinstance(value, str):
        encoded = value.encode("utf-8")
        hasher.update(b"s")
        hasher.update(struct.pack(">I", len(encoded)))
        hasher.update(encoded)
    elif isinstance(value, (tuple, list)):
        seq: Sequence[object] = value
        hasher.update(b"t")
        hasher.update(struct.pack(">I", len(seq)))
        for item in seq:
            _feed(hasher, item)
    else:
        raise TypeError(
            f"stable_hash: unsupported type {type(value).__name__!r}. "
            "Supported: str, bytes, bool, int, float, None, and tuple/list of these. "
            "Refusing to fall back to repr() because it can embed non-deterministic "
            "object addresses (the exact failure mode this module prevents)."
        )


def stable_hash(*parts: object) -> int:
    """Return a deterministic non-negative 63-bit int for ``parts``.

    The parts are hashed as an ordered tuple, so argument order is
    significant and ``stable_hash(1, 2) != stable_hash(2, 1)``.
    """
    hasher = hashlib.sha256()
    _feed(hasher, tuple(parts))
    digest = hasher.digest()
    return int.from_bytes(digest[:8], "big") & _MASK_63


def stable_unit_float(*parts: object) -> float:
    """Deterministic float in ``[0.0, 1.0)`` derived from ``parts``.

    Useful for synthesising per-entity attributes (capacity, cost, τ) without
    a stateful RNG and without the salted builtin :func:`hash`.
    """
    # 53 bits of mantissa precision is all a float can hold.
    return (stable_hash(*parts) >> 10) / float(1 << 53)


def derive_seed(base_seed: object, *parts: object) -> int:
    """Derive a child seed from a base seed plus discriminators.

    Deterministic and stable across processes. ``base_seed`` may be ``None``
    (treated as its own tagged value) so callers can derive from a pack whose
    seed is unset. Distinct ``parts`` yield distinct seeds; the same
    ``(base_seed, *parts)`` always yields the same seed.
    """
    return stable_hash("gridflow.seed", base_seed, *parts)


__all__ = ["derive_seed", "stable_hash", "stable_unit_float"]
