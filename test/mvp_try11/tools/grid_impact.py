"""DistFlow voltage and line-loading impact matrices for grid-aware CTOP.

Spec: F-M2 C3 reviewer concern resolution.

For each feeder, compute two matrices over the bus / line index sets:

  V_impact[i, j] = ∂V_i / ∂P_j  (voltage at bus i per kW injected at bus j)
  L_impact[k, j] = ∂L_k / ∂P_j  (line loading % per kW injected at bus j)

These linearise the DistFlow network model around the no-injection
operating point. Combined with the baseline voltage / loading (from
existing loads only) they give a closed-form linear constraint on the
MILP variables x_j ∈ {0,1}:

  V_baseline[i] + sum_j cap_j * V_impact[i, b(j)] * x_j  ≤  V_max
  L_baseline[k] + sum_j cap_j * L_impact[k, b(j)] * x_j  ≤  L_max

where b(j) is the bus assigned to DER j.

Computation: for each candidate bus, modify the base network to inject
a small probe (1 kW) at that bus, run pandapower, record the resulting
voltage and line-loading deltas. This is O(N_buses) PF calls per
feeder; cached on disk (json) to avoid recomputation.

Linearity assumption is valid for small perturbations and for radial
networks without binding tap changers — the standard DistFlow regime.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandapower as pp

from .feeders import make_feeder

# Probe size for the linearisation (kW)
PROBE_KW: float = 1.0


@dataclass(frozen=True)
class GridImpactMatrix:
    """Cached impact matrices for a feeder.

    Attributes:
        feeder_name: Name of the feeder.
        bus_indices: Tuple of bus indices in the order matching matrix columns/rows.
        line_indices: Tuple of line indices.
        baseline_v_pu: Per-bus voltage at the no-DER equilibrium (existing loads only).
        baseline_line_pct: Per-line loading % at the no-DER equilibrium.
        v_impact_per_kw: Matrix of shape (n_buses, n_buses); v_impact[i, b] is
            the voltage perturbation at bus_indices[i] per kW injected at bus
            bus_indices[b].
        l_impact_per_kw: Matrix of shape (n_lines, n_buses); l_impact[k, b] is
            the line-loading-pct perturbation at line_indices[k] per kW
            injected at bus bus_indices[b].
    """

    feeder_name: str
    bus_indices: tuple[int, ...]
    line_indices: tuple[int, ...]
    baseline_v_pu: tuple[float, ...]
    baseline_line_pct: tuple[float, ...]
    v_impact_per_kw: tuple[tuple[float, ...], ...]
    l_impact_per_kw: tuple[tuple[float, ...], ...]

    def to_dict(self) -> dict:
        return {
            "feeder_name": self.feeder_name,
            "bus_indices": list(self.bus_indices),
            "line_indices": list(self.line_indices),
            "baseline_v_pu": list(self.baseline_v_pu),
            "baseline_line_pct": list(self.baseline_line_pct),
            "v_impact_per_kw": [list(r) for r in self.v_impact_per_kw],
            "l_impact_per_kw": [list(r) for r in self.l_impact_per_kw],
        }

    @classmethod
    def from_dict(cls, d: dict) -> GridImpactMatrix:
        return cls(
            feeder_name=d["feeder_name"],
            bus_indices=tuple(d["bus_indices"]),
            line_indices=tuple(d["line_indices"]),
            baseline_v_pu=tuple(d["baseline_v_pu"]),
            baseline_line_pct=tuple(d["baseline_line_pct"]),
            v_impact_per_kw=tuple(tuple(r) for r in d["v_impact_per_kw"]),
            l_impact_per_kw=tuple(tuple(r) for r in d["l_impact_per_kw"]),
        )


def _baseline_pf(feeder_name: str) -> tuple[np.ndarray, np.ndarray, list[int], list[int]]:
    """Run a baseline PF (existing loads, no DERs) and return per-bus V and per-line loading."""
    net = make_feeder(feeder_name)
    bus_indices = list(net.bus.index)
    line_indices = list(net.line.index) if len(net.line) > 0 else []
    try:
        pp.runpp(net, numba=False)
        v = net.res_bus.vm_pu.reindex(bus_indices).fillna(1.0).values
        if line_indices:
            line_load = net.res_line.loading_percent.reindex(line_indices).fillna(0.0).values
        else:
            line_load = np.zeros(0)
    except Exception:
        v = np.ones(len(bus_indices))
        line_load = np.zeros(len(line_indices))
    return v, line_load, bus_indices, line_indices


def compute_impact_matrix(feeder_name: str) -> GridImpactMatrix:
    """Compute the voltage / line-loading impact matrices for a feeder.

    For each bus b in the feeder, run a power flow with a small (PROBE_KW)
    sgen at b and record the resulting voltage deltas and line-loading
    deltas. The result is normalised per-kW to give linear sensitivities.
    """
    baseline_v, baseline_line, bus_indices, line_indices = _baseline_pf(feeder_name)
    n_buses = len(bus_indices)
    n_lines = len(line_indices)

    v_impact = np.zeros((n_buses, n_buses))
    l_impact = np.zeros((max(n_lines, 1), n_buses))

    for col, b in enumerate(bus_indices):
        net = make_feeder(feeder_name)
        sgen_idx = pp.create_sgen(net, bus=int(b), p_mw=PROBE_KW / 1000.0,
                                  name=f"probe_{b}")
        try:
            pp.runpp(net, numba=False)
            v_perturbed = net.res_bus.vm_pu.reindex(bus_indices).fillna(1.0).values
            v_impact[:, col] = (v_perturbed - baseline_v) / PROBE_KW
            if n_lines > 0:
                l_perturbed = net.res_line.loading_percent.reindex(line_indices).fillna(0.0).values
                l_impact[:n_lines, col] = (l_perturbed - baseline_line) / PROBE_KW
        except Exception:
            # Leave the column at zero on divergence
            pass

    return GridImpactMatrix(
        feeder_name=feeder_name,
        bus_indices=tuple(bus_indices),
        line_indices=tuple(line_indices),
        baseline_v_pu=tuple(float(v) for v in baseline_v),
        baseline_line_pct=tuple(float(v) for v in baseline_line),
        v_impact_per_kw=tuple(tuple(float(x) for x in row) for row in v_impact),
        l_impact_per_kw=tuple(tuple(float(x) for x in row) for row in l_impact[:n_lines]),
    )


_CACHE: dict[str, GridImpactMatrix] = {}


def get_impact_matrix(feeder_name: str, cache_dir: Path | None = None) -> GridImpactMatrix:
    """Return cached or freshly-computed impact matrix for ``feeder_name``."""
    if feeder_name in _CACHE:
        return _CACHE[feeder_name]
    cache_dir = cache_dir or (Path(__file__).resolve().parent.parent / "results" / "grid_impact_cache")
    cache_dir.mkdir(parents=True, exist_ok=True)
    cache_file = cache_dir / f"{feeder_name}.json"
    if cache_file.exists():
        d = json.loads(cache_file.read_text(encoding="utf-8"))
        m = GridImpactMatrix.from_dict(d)
    else:
        m = compute_impact_matrix(feeder_name)
        cache_file.write_text(json.dumps(m.to_dict(), indent=2), encoding="utf-8")
    _CACHE[feeder_name] = m
    return m
