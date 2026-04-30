"""Grid-aware VPP simulator — pandapower power flow per timestep.

Spec: F-M2 multi-feeder extension of `vpp_simulator.py`.

Where the original ``simulate_vpp`` only computed *aggregate output*,
this module additionally:
  * places each DER as a generator (gen) on its assigned feeder bus
  * runs a power-flow at every timestep
  * collects per-timestep voltage profile and line loading
  * computes voltage_violation_ratio and line_overload metrics

A subsampled timestep set is used to keep run time tractable: by default
1 power flow every 12 steps (= every hour at 5-min resolution).

Design (CLAUDE.md §0.1):
  * grid_simulate is a pure function of (pool, active, standby, feeder,
    trace, dispatch_policy, sample_every).
  * Result is a frozen GridRunResult; ExperimentResult adapter is in
    `to_grid_experiment_result`.
  * pandapower is invoked with numba=False for cross-platform stability.
"""

from __future__ import annotations

from dataclasses import dataclass
from datetime import UTC, datetime
from typing import Callable

import pandapower as pp

from gridflow.domain.cdl import ExperimentMetadata
from gridflow.domain.result.results import LoadResult
from gridflow.domain.util.params import as_params
from gridflow.usecase.result import ExperimentResult

from .der_pool import DER
from .feeders import DerBusMap, make_feeder
from .grid_impact import get_impact_matrix
from .trace_synthesizer import ChurnTrace
from .vpp_simulator import all_standby_dispatch_policy


# Default: sample every 12 timesteps (=1 hour at 5-min resolution)
DEFAULT_SAMPLE_EVERY: int = 12

# Voltage violation thresholds (per-unit)
VOLTAGE_UPPER_PU: float = 1.05
VOLTAGE_LOWER_PU: float = 0.95


@dataclass(frozen=True)
class GridRunResult:
    """Result of a grid-aware VPP simulation.

    Attributes:
        n_steps: Total trace steps.
        sample_every: Power-flow sampling stride.
        n_pf_runs: Number of power-flow runs actually executed.
        sla_target_kw: Contracted SLA threshold.
        feeder_name: Name of the feeder simulated.
        aggregate_kw: Per-step aggregate output (kW).
        sla_violation: Per-step bool — aggregate < target.
        voltage_min_pu_sampled: Per-sampled-step minimum bus voltage (pu).
        voltage_max_pu_sampled: Per-sampled-step maximum bus voltage (pu).
        line_max_load_pct_sampled: Per-sampled-step max line loading (%).
        pf_diverged: Per-sampled-step bool — power flow diverged.
        train_steps / test_steps: Train/test split.
        baseline_voltage_min_pu: V_min (pu) under existing load only (= no DER
            injection). Time-independent constant computed from the feeder
            grid_impact baseline. Shared across all sampled steps.
        baseline_voltage_max_pu: V_max (pu) under existing load only.
        baseline_line_load_pct: Max line loading (%) under existing load only.
    """

    n_steps: int
    sample_every: int
    n_pf_runs: int
    sla_target_kw: float
    feeder_name: str
    aggregate_kw: tuple[float, ...]
    sla_violation: tuple[bool, ...]
    voltage_min_pu_sampled: tuple[float, ...]
    voltage_max_pu_sampled: tuple[float, ...]
    line_max_load_pct_sampled: tuple[float, ...]
    pf_diverged: tuple[bool, ...]
    train_steps: int
    test_steps: int
    baseline_voltage_min_pu: float
    baseline_voltage_max_pu: float
    baseline_line_load_pct: float


def grid_simulate(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    standby_ids: frozenset[str],
    trace: ChurnTrace,
    feeder_name: str,
    bus_map: DerBusMap,
    dispatch_policy: Callable[..., tuple[bool, ...]] = all_standby_dispatch_policy,
    sample_every: int = DEFAULT_SAMPLE_EVERY,
) -> GridRunResult:
    """Walk ``trace`` and run pandapower at every ``sample_every``-th step.

    Active and standby DERs are added as static generators (sgen) on
    their mapped buses. Per-step output is taken from ``trace`` plus the
    dispatch policy. Voltages and line loadings are recorded from each
    PF run; intermediate (non-sampled) steps reuse the most recent PF
    snapshot for SLA accounting.
    """
    der_id_to_index = {d.der_id: i for i, d in enumerate(pool)}
    active_idx = tuple(der_id_to_index[i] for i in active_ids if i in der_id_to_index)
    standby_idx = tuple(der_id_to_index[i] for i in standby_ids if i in der_id_to_index)
    standby_pool = tuple(pool[i] for i in standby_idx)

    bus_lookup = dict(bus_map.bus_of)
    n_steps = len(trace.der_active_status)

    # Build base pandapower net once; we'll add sgen entries and modify p_mw
    base_net = make_feeder(feeder_name)
    # Add a sgen for every member DER (active or standby), p_mw initially 0
    sgen_by_der: dict[str, int] = {}
    for j in active_idx + standby_idx:
        d = pool[j]
        bus = bus_lookup.get(d.der_id, bus_map.substation_bus)
        sgen_idx = pp.create_sgen(
            base_net, bus=int(bus), p_mw=0.0, name=d.der_id, type="DER",
        )
        sgen_by_der[d.der_id] = int(sgen_idx)

    aggregate: list[float] = []
    violation: list[bool] = []
    v_min_samples: list[float] = []
    v_max_samples: list[float] = []
    line_load_samples: list[float] = []
    pf_div_samples: list[bool] = []

    last_v_min, last_v_max, last_line_load, last_div = 1.0, 1.0, 0.0, False
    pf_runs = 0

    for t_step in range(n_steps):
        row = trace.der_active_status[t_step]
        # Active output
        active_out_kw = sum(
            pool[i].capacity_kw for i in active_idx if row[i]
        )
        # Standby dispatch decision
        standby_status = tuple(row[i] for i in standby_idx)
        dispatch = dispatch_policy(
            t_step=t_step,
            sla_kw=trace.sla_target_kw,
            active_output_kw=active_out_kw,
            standby_pool=standby_pool,
            standby_active_status=standby_status,
        )
        standby_out_kw = sum(
            standby_pool[k].capacity_kw
            for k in range(len(standby_idx))
            if dispatch[k] and standby_status[k]
        )
        agg = active_out_kw + standby_out_kw
        aggregate.append(agg)
        violation.append(agg < trace.sla_target_kw)

        # Power flow only on sample_every-th step
        if t_step % sample_every == 0:
            # Update sgen p_mw for every DER member
            for j in active_idx:
                d = pool[j]
                p_mw = (d.capacity_kw / 1000.0) if row[j] else 0.0
                base_net.sgen.loc[sgen_by_der[d.der_id], "p_mw"] = p_mw
            for k, j in enumerate(standby_idx):
                d = pool[j]
                if dispatch[k] and standby_status[k]:
                    p_mw = d.capacity_kw / 1000.0
                else:
                    p_mw = 0.0
                base_net.sgen.loc[sgen_by_der[d.der_id], "p_mw"] = p_mw
            try:
                pp.runpp(base_net, numba=False)
                v_min = float(base_net.res_bus.vm_pu.min())
                v_max = float(base_net.res_bus.vm_pu.max())
                line_load = float(base_net.res_line.loading_percent.max()) if len(base_net.line) > 0 else 0.0
                div = False
            except Exception:
                v_min, v_max, line_load, div = 0.5, 1.5, 200.0, True

            last_v_min, last_v_max, last_line_load, last_div = v_min, v_max, line_load, div
            v_min_samples.append(v_min)
            v_max_samples.append(v_max)
            line_load_samples.append(line_load)
            pf_div_samples.append(div)
            pf_runs += 1

    train_steps = trace.train_days * 24 * 60 // trace.timestep_min

    # Baseline (existing-load only, no DER injection) is time-independent
    # under static-load pandapower runpp. Pull it from the cached impact
    # matrix so we only pay for the baseline PF once per feeder.
    impact = get_impact_matrix(feeder_name)
    if impact.baseline_v_pu:
        baseline_v_min = float(min(impact.baseline_v_pu))
        baseline_v_max = float(max(impact.baseline_v_pu))
    else:
        baseline_v_min = 1.0
        baseline_v_max = 1.0
    baseline_line_max = (
        float(max(impact.baseline_line_pct)) if impact.baseline_line_pct else 0.0
    )

    return GridRunResult(
        n_steps=n_steps,
        sample_every=sample_every,
        n_pf_runs=pf_runs,
        sla_target_kw=trace.sla_target_kw,
        feeder_name=feeder_name,
        aggregate_kw=tuple(aggregate),
        sla_violation=tuple(violation),
        voltage_min_pu_sampled=tuple(v_min_samples),
        voltage_max_pu_sampled=tuple(v_max_samples),
        line_max_load_pct_sampled=tuple(line_load_samples),
        pf_diverged=tuple(pf_div_samples),
        train_steps=train_steps,
        test_steps=n_steps - train_steps,
        baseline_voltage_min_pu=baseline_v_min,
        baseline_voltage_max_pu=baseline_v_max,
        baseline_line_load_pct=baseline_line_max,
    )


def to_grid_experiment_result(
    run: GridRunResult,
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    standby_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    experiment_id: str,
    scenario_pack_id: str,
    method_label: str,
) -> ExperimentResult:
    """Wrap a GridRunResult as gridflow ExperimentResult.

    Synthetic loads carry both VPP-level signals (__aggregate__,
    __sla_target__) and grid-level signals (__voltage_min__,
    __voltage_max__, __line_load_max__).
    """
    n_steps = run.n_steps
    sample_every = run.sample_every

    def _expand_sampled(samples: tuple[float, ...]) -> tuple[float, ...]:
        """Expand a sampled series back to per-timestep by holding values."""
        full = [0.0] * n_steps
        for i in range(n_steps):
            j = i // sample_every
            if j < len(samples):
                full[i] = samples[j]
            elif samples:
                full[i] = samples[-1]
        return tuple(full)

    aggregate = run.aggregate_kw
    sla = tuple(run.sla_target_kw for _ in range(n_steps))
    v_min_full = _expand_sampled(run.voltage_min_pu_sampled)
    v_max_full = _expand_sampled(run.voltage_max_pu_sampled)
    line_load_full = _expand_sampled(run.line_max_load_pct_sampled)
    baseline_v_min_full = tuple(run.baseline_voltage_min_pu for _ in range(n_steps))
    baseline_v_max_full = tuple(run.baseline_voltage_max_pu for _ in range(n_steps))
    baseline_line_full = tuple(run.baseline_line_load_pct for _ in range(n_steps))

    load_results = (
        LoadResult(asset_id="__aggregate__",
                   demands=aggregate, supplied=aggregate),
        LoadResult(asset_id="__sla_target__",
                   demands=sla, supplied=sla),
        LoadResult(asset_id="__voltage_min__",
                   demands=v_min_full, supplied=v_min_full),
        LoadResult(asset_id="__voltage_max__",
                   demands=v_max_full, supplied=v_max_full),
        LoadResult(asset_id="__line_load_max__",
                   demands=line_load_full, supplied=line_load_full),
        LoadResult(asset_id="__voltage_baseline_min__",
                   demands=baseline_v_min_full, supplied=baseline_v_min_full),
        LoadResult(asset_id="__voltage_baseline_max__",
                   demands=baseline_v_max_full, supplied=baseline_v_max_full),
        LoadResult(asset_id="__line_load_baseline_max__",
                   demands=baseline_line_full, supplied=baseline_line_full),
    )

    metadata = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime.now(UTC),
        scenario_pack_id=scenario_pack_id,
        connector="try11_grid_vpp",
        seed=trace.seed,
        parameters=as_params({
            "method": method_label,
            "trace_id": trace.trace_id,
            "feeder": run.feeder_name,
            "active_pool_size": len(active_ids),
            "standby_pool_size": len(standby_ids),
            "train_steps": run.train_steps,
            "test_steps": run.test_steps,
            "sla_target_kw": run.sla_target_kw,
            "n_pf_runs": run.n_pf_runs,
        }),
    )

    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=metadata,
        load_results=load_results,
    )
