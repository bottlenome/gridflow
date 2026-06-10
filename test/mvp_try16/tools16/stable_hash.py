"""Process-stable string digest for deterministic synthetic attributes.

Python's builtin ``hash(str)`` is salted per process (PEP 456), so any
station-attribute mapping derived from it changes between runs unless
``PYTHONHASHSEED`` is pinned.  The original try16 sweep used
``abs(hash(sid))``, which silently broke cross-process reproducibility
(policy §4.2 B).  All synthetic attribute derivation now goes through
:func:`stable_hash` (SHA-256, first 8 bytes, unsigned).
"""

from __future__ import annotations

import hashlib


def stable_hash(text: str) -> int:
    """Deterministic 64-bit unsigned digest of ``text`` (same in every process)."""
    return int.from_bytes(hashlib.sha256(text.encode("utf-8")).digest()[:8], "big")
