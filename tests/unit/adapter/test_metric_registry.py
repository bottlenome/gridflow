"""Tests for the MetricRegistry + dynamic plugin loader.

Spec: ``docs/phase1_result.md`` §7.13.1 (機能 C).

The registry is the single lookup point for ``MetricCalculator``
implementations: built-in metrics are registered at startup, and
pack.yaml's ``metrics`` section can extend the registry at load time
with user-supplied Python plugins (``module:Class``).
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.adapter.benchmark.metric_registry import (
    MetricRegistry,
    PluginLoadError,
    build_default_metric_registry,
    load_metric_plugin,
)
from gridflow.adapter.benchmark.metrics import RuntimeMetric, VoltageDeviationMetric
from gridflow.domain.cdl import ExperimentMetadata
from gridflow.usecase.result import ExperimentResult


def _empty_result() -> ExperimentResult:
    metadata = ExperimentMetadata(
        experiment_id="exp-1",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        scenario_pack_id="p@1",
        connector="fake",
    )
    return ExperimentResult(experiment_id="exp-1", metadata=metadata)


# ----------------------------------------------------------------- registry


class TestMetricRegistry:
    def test_register_and_get(self) -> None:
        reg = MetricRegistry()
        m = VoltageDeviationMetric()
        reg.register(m)
        assert reg.get("voltage_deviation") is m

    def test_unknown_metric_raises(self) -> None:
        reg = MetricRegistry()
        with pytest.raises(KeyError, match="ghost"):
            reg.get("ghost")

    def test_duplicate_registration_rejected(self) -> None:
        reg = MetricRegistry()
        reg.register(VoltageDeviationMetric())
        with pytest.raises(ValueError, match="already"):
            reg.register(VoltageDeviationMetric())

    def test_names_sorted(self) -> None:
        reg = MetricRegistry()
        reg.register(RuntimeMetric())
        reg.register(VoltageDeviationMetric())
        assert reg.names() == ("runtime", "voltage_deviation")

    def test_get_many(self) -> None:
        reg = MetricRegistry()
        reg.register(VoltageDeviationMetric())
        reg.register(RuntimeMetric())
        got = reg.get_many(("voltage_deviation", "runtime"))
        assert tuple(m.name for m in got) == ("voltage_deviation", "runtime")

    def test_get_many_unknown_raises(self) -> None:
        reg = MetricRegistry()
        reg.register(VoltageDeviationMetric())
        with pytest.raises(KeyError, match="ghost"):
            reg.get_many(("voltage_deviation", "ghost"))


class TestBuildDefaultRegistry:
    def test_includes_voltage_deviation_and_runtime(self) -> None:
        reg = build_default_metric_registry()
        assert reg.get("voltage_deviation").name == "voltage_deviation"
        assert reg.get("runtime").name == "runtime"


# ----------------------------------------------------------------- plugin loader


class _FakeNonMetric:
    """A class that does NOT satisfy MetricCalculator (no calculate method)."""

    name = "fake"
    unit = "x"


_PKG_COUNTER = 0


def _build_plugin_module(tmp_path: Path, body: str) -> tuple[Path, str]:
    """Write ``body`` to ``<tmp_path>/<pkg>/fake_metric.py`` and return
    ``(syspath_root, "<pkg>.fake_metric")`` so each test gets a *new*
    package name and avoids the ``sys.modules`` cache between cases.
    """
    global _PKG_COUNTER
    _PKG_COUNTER += 1
    pkg_name = f"fake_plugin_pkg_{_PKG_COUNTER}"
    pkg = tmp_path / pkg_name
    pkg.mkdir()
    (pkg / "__init__.py").write_text("", encoding="utf-8")
    module = pkg / "fake_metric.py"
    module.write_text(body, encoding="utf-8")
    return tmp_path, f"{pkg_name}.fake_metric"


class TestLoadMetricPlugin:
    """``load_metric_plugin('module:Class')`` dynamically imports a metric."""

    def test_loads_valid_plugin(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = '''
"""Fake metric for tests."""

class HelloMetric:
    name = "hello"
    unit = "ratio"

    def calculate(self, result):
        return 0.5
'''
        sys_path_root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(sys_path_root))
        metric = load_metric_plugin(f"{module_path}:HelloMetric")
        assert metric.name == "hello"
        assert metric.calculate(_empty_result()) == 0.5

    def test_unknown_module_raises(self) -> None:
        with pytest.raises(PluginLoadError, match="import"):
            load_metric_plugin("not_a_real_module.never_existed:Anything")

    def test_unknown_attribute_raises(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = """
class OtherMetric:
    name = "other"
    unit = "x"
    def calculate(self, result):
        return 0.0
"""
        root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(root))
        with pytest.raises(PluginLoadError, match="not found"):
            load_metric_plugin(f"{module_path}:Missing")

    def test_non_metric_class_rejected(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = """
class NotAMetric:
    name = "x"
    unit = "y"
    # Missing .calculate intentionally.
"""
        root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(root))
        with pytest.raises(PluginLoadError, match="MetricCalculator"):
            load_metric_plugin(f"{module_path}:NotAMetric")

    def test_malformed_spec_raises(self) -> None:
        with pytest.raises(PluginLoadError, match="format"):
            load_metric_plugin("no_colon_here")

    def test_constructor_kwargs_passed(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        """Plugin loader supports passing constructor kwargs from pack.yaml."""
        body = """
class ParametrizedMetric:
    name = "parametrized"
    unit = "x"

    def __init__(self, threshold=0.5, label="default"):
        self.threshold = threshold
        self.label = label

    def calculate(self, result):
        return self.threshold
"""
        root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(root))
        metric = load_metric_plugin(
            f"{module_path}:ParametrizedMetric",
            kwargs={"threshold": 0.8, "label": "custom"},
        )
        assert metric.calculate(_empty_result()) == 0.8


class TestRegisterPluginsFromConfig:
    """``MetricRegistry.register_plugins(specs)`` consumes pack.yaml entries."""

    def test_loads_and_registers(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = """
class CapacityMetric:
    name = "capacity"
    unit = "MW"
    def calculate(self, result):
        return 1.5
"""
        root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(root))
        reg = MetricRegistry()
        reg.register_plugins(({"plugin": f"{module_path}:CapacityMetric"},))
        assert reg.get("capacity").name == "capacity"

    def test_with_kwargs_in_spec(self, tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
        body = """
class ParamMetric:
    name = "param"
    unit = "ratio"
    def __init__(self, k=0):
        self.k = k
    def calculate(self, result):
        return float(self.k)
"""
        root, module_path = _build_plugin_module(tmp_path, body)
        monkeypatch.syspath_prepend(str(root))
        reg = MetricRegistry()
        reg.register_plugins(
            (
                {
                    "plugin": f"{module_path}:ParamMetric",
                    "kwargs": {"k": 7},
                },
            )
        )
        assert reg.get("param").calculate(_empty_result()) == 7.0

    def test_built_in_name_skipped_when_no_plugin(self) -> None:
        """Specs without 'plugin' (just a built-in name) are no-ops at the
        registry level — they are signals for the harness, not new
        registrations."""
        reg = build_default_metric_registry()
        # Should not raise.
        reg.register_plugins(({"name": "voltage_deviation"},))
        assert reg.get("voltage_deviation").name == "voltage_deviation"
