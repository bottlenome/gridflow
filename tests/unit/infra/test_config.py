"""Tests for ConfigManager precedence and lookup semantics."""

from __future__ import annotations

from pathlib import Path

import pytest

from gridflow.domain.error import ConfigError
from gridflow.infra.config import ConfigManager


class TestConfigManager:
    def test_set_defaults_and_get(self) -> None:
        cfg = ConfigManager()
        cfg.set_defaults({"logging": {"level": "INFO"}})
        assert cfg.get("logging.level") == "INFO"

    def test_file_overrides_defaults(self, tmp_path: Path) -> None:
        cfg = ConfigManager()
        cfg.set_defaults({"logging": {"level": "INFO"}})
        path = tmp_path / "gridflow.yaml"
        path.write_text("logging:\n  level: DEBUG\n", encoding="utf-8")
        cfg.load_file(path)
        assert cfg.get("logging.level") == "DEBUG"

    def test_env_overrides_file(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = ConfigManager()
        path = tmp_path / "gridflow.yaml"
        path.write_text("logging:\n  level: DEBUG\n", encoding="utf-8")
        cfg.load_file(path)
        monkeypatch.setenv("GRIDFLOW_LOGGING__LEVEL", "ERROR")
        assert cfg.get("logging.level") == "ERROR"

    def test_set_overrides_env(self, monkeypatch: pytest.MonkeyPatch) -> None:
        cfg = ConfigManager()
        monkeypatch.setenv("GRIDFLOW_A__B", "env")
        cfg.set("a.b", "override")
        assert cfg.get("a.b") == "override"

    def test_require_missing_raises(self) -> None:
        cfg = ConfigManager()
        with pytest.raises(ConfigError):
            cfg.require("does.not.exist")

    def test_file_not_found(self, tmp_path: Path) -> None:
        cfg = ConfigManager()
        with pytest.raises(ConfigError):
            cfg.load_file(tmp_path / "nope.yaml")

    def test_malformed_yaml(self, tmp_path: Path) -> None:
        cfg = ConfigManager()
        path = tmp_path / "bad.yaml"
        path.write_text(":::not yaml", encoding="utf-8")
        with pytest.raises(ConfigError):
            cfg.load_file(path)
