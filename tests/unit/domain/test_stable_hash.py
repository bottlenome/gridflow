"""Tests for the deterministic hashing utility (issue #19)."""

from __future__ import annotations

import subprocess
import sys

import pytest

from gridflow.domain.util.stable_hash import derive_seed, stable_hash, stable_unit_float


class TestStableHash:
    def test_deterministic_within_process(self) -> None:
        assert stable_hash("a", 1, 2.0) == stable_hash("a", 1, 2.0)

    def test_non_negative_63_bit(self) -> None:
        for parts in [("x",), (1,), (-999999,), (3.14,), (None,), ((1, 2, 3),)]:
            h = stable_hash(*parts)
            assert 0 <= h < (1 << 63)

    def test_type_tagging_distinguishes_int_and_str(self) -> None:
        assert stable_hash(1) != stable_hash("1")

    def test_bool_distinct_from_int(self) -> None:
        # bool is an int subclass; the tag must keep them apart.
        assert stable_hash(True) != stable_hash(1)
        assert stable_hash(False) != stable_hash(0)

    def test_order_significant(self) -> None:
        assert stable_hash(1, 2) != stable_hash(2, 1)

    def test_nesting_distinguished(self) -> None:
        assert stable_hash((1, 2)) != stable_hash((12,))
        assert stable_hash((1, 2), 3) != stable_hash(1, (2, 3))

    def test_negative_zero_normalised(self) -> None:
        assert stable_hash(-0.0) == stable_hash(0.0)

    def test_unsupported_type_rejected(self) -> None:
        with pytest.raises(TypeError, match="unsupported type"):
            stable_hash(object())

    def test_stable_across_processes(self) -> None:
        # The whole point: no per-process salt. Recompute in a fresh
        # interpreter (which has a different PYTHONHASHSEED) and compare.
        code = "from gridflow.domain.util.stable_hash import stable_hash;print(stable_hash('kerber_dorf', 3, 0.42))"
        out = subprocess.run(
            [sys.executable, "-c", code],
            capture_output=True,
            text=True,
            check=True,
            env={"PYTHONHASHSEED": "1"},
        )
        assert int(out.stdout.strip()) == stable_hash("kerber_dorf", 3, 0.42)


class TestStableUnitFloat:
    def test_range(self) -> None:
        for i in range(100):
            v = stable_unit_float("entity", i)
            assert 0.0 <= v < 1.0

    def test_deterministic(self) -> None:
        assert stable_unit_float("c", 7) == stable_unit_float("c", 7)


class TestDeriveSeed:
    def test_distinct_per_replicate(self) -> None:
        seeds = {derive_seed(42, rep) for rep in range(10)}
        assert len(seeds) == 10  # no collisions across replicates

    def test_deterministic(self) -> None:
        assert derive_seed(42, 3) == derive_seed(42, 3)

    def test_base_seed_none_supported(self) -> None:
        # A pack with no seed must still yield distinct, stable replicate seeds.
        assert derive_seed(None, 0) != derive_seed(None, 1)
        assert derive_seed(None, 0) == derive_seed(None, 0)

    def test_base_seed_changes_stream(self) -> None:
        assert derive_seed(1, 0) != derive_seed(2, 0)
