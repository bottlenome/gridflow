"""Tests for OutputFormatter rendering paths."""

from __future__ import annotations

import json

from gridflow.adapter.cli.formatter import OutputFormat, OutputFormatter


class TestOutputFormatter:
    def test_plain_dict(self) -> None:
        out = OutputFormatter(OutputFormat.PLAIN).render({"k": "v"})
        assert out == "k: v"

    def test_plain_list_of_dicts(self) -> None:
        out = OutputFormatter(OutputFormat.PLAIN).render([{"a": 1}, {"a": 2}])
        assert "a: 1" in out and "a: 2" in out

    def test_json_renders_sorted(self) -> None:
        out = OutputFormatter(OutputFormat.JSON).render({"b": 1, "a": 2})
        parsed = json.loads(out)
        assert parsed == {"a": 2, "b": 1}

    def test_table_header_and_rows(self) -> None:
        out = OutputFormatter(OutputFormat.TABLE).render(
            [{"pack_id": "a@1", "status": "ok"}, {"pack_id": "b@2", "status": "ok"}]
        )
        lines = out.splitlines()
        assert "pack_id" in lines[0]
        assert any("a@1" in line for line in lines[2:])
