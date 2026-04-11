"""MetricRegistry + dynamic plugin loader.

Spec: ``docs/phase1_result.md`` §7.13.1 (機能 C).

The registry is a name → ``MetricCalculator`` map. It is used by the
:class:`BenchmarkHarness` and the sweep aggregator pipeline to resolve
metric names from configuration. Built-in metrics are registered via
:func:`build_default_metric_registry`; user-defined metrics can be added
either programmatically (``register``) or declaratively from a
``pack.yaml`` ``metrics`` section via :meth:`MetricRegistry.register_plugins`.

The plugin loader supports the simple ``module.path:ClassName`` form so
``pack.yaml`` can stay declarative:

.. code-block:: yaml

    metrics:
      - name: voltage_deviation        # built-in (no plugin field)
      - plugin: "my_pkg.my_metric:HostingCapacityMetric"
        kwargs:
          confidence: 0.95

The plugin class must satisfy the :class:`MetricCalculator` Protocol
(``name``, ``unit``, ``calculate(result)``); a runtime check at load
time fails fast with :class:`PluginLoadError` if it does not.
"""

from __future__ import annotations

import importlib
from collections.abc import Iterable, Mapping
from dataclasses import dataclass, field
from typing import Any

from gridflow.adapter.benchmark.metrics import (
    BUILTIN_METRICS,
    MetricCalculator,
)


class PluginLoadError(ImportError):
    """Raised when a metric plugin spec cannot be loaded or fails the
    :class:`MetricCalculator` Protocol contract."""


# ----------------------------------------------------------------- registry


@dataclass
class MetricRegistry:
    """Name → :class:`MetricCalculator` lookup with plugin support."""

    _metrics: dict[str, MetricCalculator] = field(default_factory=dict)

    def register(self, metric: MetricCalculator) -> None:
        if metric.name in self._metrics:
            raise ValueError(f"metric '{metric.name}' already registered")
        self._metrics[metric.name] = metric

    def get(self, name: str) -> MetricCalculator:
        if name not in self._metrics:
            raise KeyError(f"metric '{name}' not registered; known: {self.names()}")
        return self._metrics[name]

    def get_many(self, names: Iterable[str]) -> tuple[MetricCalculator, ...]:
        return tuple(self.get(name) for name in names)

    def names(self) -> tuple[str, ...]:
        return tuple(sorted(self._metrics.keys()))

    def register_plugins(self, specs: Iterable[Mapping[str, Any]]) -> None:
        """Register every plugin in ``specs``.

        Each spec is a dict with one of two shapes:

        * ``{"name": <built-in>}``  → no-op (the harness/sweep selects
          built-in metrics by name; this entry is just a declaration).
        * ``{"plugin": "module:Class", "kwargs": {...}}`` → dynamic
          import + register.

        Mixing both shapes in the same spec is allowed (a built-in
        ``name`` for the registered key plus a ``plugin`` to override
        the implementation).
        """
        for spec in specs:
            if "plugin" not in spec:
                # Pure built-in selection — nothing to register here.
                continue
            plugin_path = spec["plugin"]
            kwargs = spec.get("kwargs") or {}
            if not isinstance(kwargs, Mapping):
                raise PluginLoadError(
                    f"metric spec {plugin_path}: 'kwargs' must be a mapping, got {type(kwargs).__name__}"
                )
            metric = load_metric_plugin(plugin_path, kwargs=dict(kwargs))
            self.register(metric)


def build_default_metric_registry() -> MetricRegistry:
    """Factory: registry pre-populated with the built-in metrics."""
    reg = MetricRegistry()
    for metric in BUILTIN_METRICS:
        reg.register(metric)
    return reg


# ----------------------------------------------------------------- loader


def load_metric_plugin(
    spec: str,
    *,
    kwargs: Mapping[str, Any] | None = None,
) -> MetricCalculator:
    """Dynamically import a :class:`MetricCalculator` from a ``module:Class``
    string and instantiate it.

    Args:
        spec: ``"package.module:ClassName"`` plugin path.
        kwargs: Optional constructor kwargs forwarded to ``ClassName(**kwargs)``.

    Raises:
        PluginLoadError: If the spec is malformed, the module / class
            cannot be imported, the class cannot be instantiated with
            the given kwargs, or the resulting instance does not satisfy
            the :class:`MetricCalculator` Protocol.
    """
    if ":" not in spec:
        raise PluginLoadError(f"plugin spec '{spec}' has invalid format; expected 'module.path:ClassName'")
    module_path, class_name = spec.split(":", 1)
    if not module_path or not class_name:
        raise PluginLoadError(f"plugin spec '{spec}' has invalid format; expected 'module.path:ClassName'")

    try:
        module = importlib.import_module(module_path)
    except ImportError as exc:
        raise PluginLoadError(f"failed to import module '{module_path}' for metric plugin '{spec}': {exc}") from exc

    if not hasattr(module, class_name):
        raise PluginLoadError(f"class '{class_name}' not found in module '{module_path}' for plugin '{spec}'")
    cls = getattr(module, class_name)

    try:
        instance = cls(**(kwargs or {}))
    except TypeError as exc:
        raise PluginLoadError(f"failed to instantiate {spec} with kwargs={kwargs!r}: {exc}") from exc

    if not isinstance(instance, MetricCalculator):
        raise PluginLoadError(
            f"plugin {spec} does not implement the MetricCalculator Protocol "
            f"(missing 'name'/'unit'/'calculate'); got {type(instance).__name__}"
        )
    return instance


__all__ = [
    "MetricRegistry",
    "PluginLoadError",
    "build_default_metric_registry",
    "load_metric_plugin",
]
