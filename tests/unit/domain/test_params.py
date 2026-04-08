"""Tests for the tuple-of-tuples params helper."""

from __future__ import annotations

import pytest

from gridflow.domain.util.params import as_params, get_param, params_to_dict


class TestAsParams:
    def test_accepts_none(self) -> None:
        assert as_params(None) == ()

    def test_sorts_by_key(self) -> None:
        p = as_params({"b": 2, "a": 1, "c": 3})
        assert p == (("a", 1), ("b", 2), ("c", 3))

    def test_accepts_iterable(self) -> None:
        p = as_params([("x", 10), ("y", 20)])
        assert p == (("x", 10), ("y", 20))

    def test_rejects_non_string_keys(self) -> None:
        with pytest.raises(TypeError):
            as_params({1: "bad"})  # type: ignore[dict-item]

    def test_same_input_produces_same_hash(self) -> None:
        assert hash(as_params({"a": 1, "b": 2})) == hash(as_params({"b": 2, "a": 1}))


class TestGetParam:
    def test_found(self) -> None:
        p = as_params({"k": "v"})
        assert get_param(p, "k") == "v"

    def test_default(self) -> None:
        assert get_param((), "missing", default=42) == 42


class TestParamsToDict:
    def test_roundtrip(self) -> None:
        source = {"a": 1, "b": "two"}
        assert params_to_dict(as_params(source)) == source
