"""Inline-DSL parser for ``gridflow evaluate`` (M4 — design 03c §3.7.8).

Parses two compact CLI string forms used by the ``gridflow evaluate``
command in case-A (single-shot exploration) usage:

* ``--metric "name:Cls"``                       — built-in or zero-kwargs plugin
* ``--metric "name:module.path:Cls(kw=val,...)"``  — plugin spec with kwargs
* ``--parameter-sweep "kw:start:stop:n"``           — linspace over metric kwarg

Why an explicit grammar rather than YAML even when YAML is available
(case-B): the case-A use case is `bash` history-friendly one-liners
where `gridflow evaluate --results sweep.json --metric "hc:HC(voltage_low=0.95)"`
must work without a pre-written file. CLAUDE.md §0.5.1 motivates
keeping both surface forms — see phase2_result.md.

Grammar:

    metric_spec   := <name> ":" <plugin_path> [ "(" kwargs ")" ]
    plugin_path   := <module>           # built-in metric registered by ``name``
                  |  <module> ":" <Cls> # ``module.path:ClassName``
    kwargs        := kwarg ( "," kwarg )*
    kwarg         := <key> "=" <value>
    sweep_spec    := <kwarg_name> ":" <start> ":" <stop> ":" <n_points>
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.usecase.evaluation import MetricSpec


class EvaluateDSLError(ValueError):
    """Raised when an inline DSL string is malformed."""


@dataclass(frozen=True)
class ParameterSweepSpec:
    """Parsed ``--parameter-sweep "kw:start:stop:n"`` spec.

    Attributes:
        kwarg_name: Metric kwarg key being swept (e.g. ``"voltage_low"``).
        start: Inclusive lower endpoint.
        stop: Inclusive upper endpoint.
        n_points: Number of evenly-spaced grid points (n_points >= 2).
    """

    kwarg_name: str
    start: float
    stop: float
    n_points: int

    def __post_init__(self) -> None:
        if self.n_points < 2:
            raise ValueError(f"ParameterSweepSpec.n_points must be >= 2, got {self.n_points}")
        if self.stop <= self.start:
            raise ValueError(
                f"ParameterSweepSpec '{self.kwarg_name}': stop must be > start, "
                f"got start={self.start}, stop={self.stop}"
            )

    def grid(self) -> tuple[float, ...]:
        """Linspace(start, stop, n_points) inclusive of both endpoints."""
        step = (self.stop - self.start) / (self.n_points - 1)
        return tuple(self.start + i * step for i in range(self.n_points))


def parse_metric_spec(spec: str) -> MetricSpec:
    """Parse ``"name:module.path:Cls(kw=val,...)"`` into a :class:`MetricSpec`.

    Recognised forms:

    * ``"voltage_deviation"`` — built-in by name (no plugin)
    * ``"hc:module:Cls"``     — name ``hc``, plugin ``module:Cls``, no kwargs
    * ``"hc:module:Cls(voltage_low=0.95,confidence=0.95)"``
                              — name ``hc``, plugin ``module:Cls``, with kwargs

    The first ``:`` separates the **output name** from the rest. If
    the rest is just an identifier (no further ``:``) it is treated
    as a built-in metric reference. Anything that contains a second
    ``:`` is treated as a plugin path.
    """
    if not spec:
        raise EvaluateDSLError("empty metric spec")

    # Split off the optional kwargs tail "(...)"
    body, kwargs_part = _split_off_kwargs(spec)

    parts = body.split(":", 1)
    if len(parts) == 1:
        # Pure built-in name reference, no plugin, no kwargs allowed.
        if kwargs_part:
            raise EvaluateDSLError(f"metric spec {spec!r}: built-in metric reference cannot carry kwargs")
        return MetricSpec(name=parts[0].strip(), plugin=None)

    name, rest = parts[0].strip(), parts[1].strip()
    if not name:
        raise EvaluateDSLError(f"metric spec {spec!r}: name part is empty")
    if not rest:
        raise EvaluateDSLError(f"metric spec {spec!r}: plugin part is empty")
    if ":" not in rest:
        # ``"name:plugin_built_in_name"`` — caller chose a label different
        # from the built-in's canonical name. The Evaluator only looks at
        # ``MetricSpec.name`` to find a built-in, so we pin the lookup
        # name to ``rest`` (the actual built-in identifier) but the
        # Evaluator currently rejects this aliasing form. To keep the
        # surface honest, treat ``"name:builtin_name"`` as an error.
        raise EvaluateDSLError(f"metric spec {spec!r}: built-in references cannot be renamed inline; use 'name' alone")
    # ``rest`` is "module.path:Cls" → plugin spec.
    kwargs = _parse_kwargs(kwargs_part) if kwargs_part else ()
    return MetricSpec(name=name, plugin=rest, kwargs=kwargs)


def parse_parameter_sweep(spec: str) -> ParameterSweepSpec:
    """Parse ``"kw:start:stop:n"`` into a :class:`ParameterSweepSpec`."""
    parts = spec.split(":")
    if len(parts) != 4:
        raise EvaluateDSLError(f"parameter-sweep spec {spec!r}: expected 'kwarg:start:stop:n', got {len(parts)} parts")
    kwarg_name, start_s, stop_s, n_s = (p.strip() for p in parts)
    try:
        return ParameterSweepSpec(
            kwarg_name=kwarg_name,
            start=float(start_s),
            stop=float(stop_s),
            n_points=int(n_s),
        )
    except ValueError as exc:
        raise EvaluateDSLError(f"parameter-sweep spec {spec!r}: {exc}") from exc


# ----------------------------------------------------------------- internals


def _split_off_kwargs(spec: str) -> tuple[str, str]:
    """Return (body, kwargs_inside_parens).  Empty kwargs string if none."""
    if "(" not in spec:
        return spec, ""
    if not spec.endswith(")"):
        raise EvaluateDSLError(f"metric spec {spec!r}: '(' present but no closing ')'")
    open_idx = spec.index("(")
    body = spec[:open_idx]
    kwargs_part = spec[open_idx + 1 : -1]
    return body, kwargs_part


def _parse_kwargs(text: str) -> tuple[tuple[str, object], ...]:
    """Parse ``"k1=v1,k2=v2"`` into the canonical sorted Params tuple.

    Values are coerced to int / float / bool when they parse as such,
    otherwise kept as the trimmed string. This mirrors the YAML loader
    semantics where YAML auto-coerces scalars.
    """
    if not text:
        return ()
    pairs: list[tuple[str, object]] = []
    for raw in text.split(","):
        if "=" not in raw:
            raise EvaluateDSLError(f"metric kwargs: missing '=' in fragment {raw!r}")
        k, v = raw.split("=", 1)
        key = k.strip()
        value_str = v.strip()
        if not key:
            raise EvaluateDSLError(f"metric kwargs: empty key in fragment {raw!r}")
        pairs.append((key, _coerce(value_str)))
    return tuple(sorted(pairs, key=lambda kv: kv[0]))


def _coerce(text: str) -> object:
    """int → float → bool → str (in that priority order)."""
    if text.lower() in {"true", "false"}:
        return text.lower() == "true"
    try:
        return int(text)
    except ValueError:
        pass
    try:
        return float(text)
    except ValueError:
        pass
    return text
