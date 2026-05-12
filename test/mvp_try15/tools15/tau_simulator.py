"""τ-aware VPP simulator (try15 M10 dispatch dynamics).

try11's vpp_simulator processed trigger events as instantaneous binary
flips on ``der_active_status[step][j]``. Real DER drop delays span
seconds-to-minutes (BMS ~5 s, residential EV ~300 s); modelling them
as zero-delay is the simplification that makes the synchronous-drop
problem maximally severe.

This module re-simulates a ChurnTrace with **τ-smeared drops**:

  * For each TriggerEvent (axis k, time t_evt, magnitude m, duration D):
    every DER j with e_{j,k} = 1 *and* a coin-flip with prob m is
    marked to drop *at time t_evt + τ_j* and recover at
    *t_evt + τ_j + D*.
  * Aggregate output A(t) = Σ cap_j · 1[j active at t] is therefore
    a step function whose down-steps are *spread by τ_j diversity*.

For pools whose τ are uniform across types, the smearing reduces to a
single delay (= same as try11). For τ-diversified pools, A(t)
descends gracefully and the SLA tail (= min A over the burst window)
is **higher than the uniform-τ case**.

The simulator produces a per-step aggregate trajectory and an SLA
violation indicator, in the same shape as try11's ``GridRunResult``,
so downstream metrics modules need no changes.
"""

from __future__ import annotations

import random
import sys
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path

_TRY11 = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11) not in sys.path:
    sys.path.insert(0, str(_TRY11))

from gridflow.domain.cdl import ExperimentMetadata  # noqa: E402
from gridflow.domain.result.results import LoadResult  # noqa: E402
from gridflow.domain.util.params import as_params  # noqa: E402
from gridflow.usecase.result import ExperimentResult  # noqa: E402

from tools.der_pool import DER, project_exposure  # noqa: E402
from tools.trace_synthesizer import ChurnTrace, TriggerEvent  # noqa: E402

from tools15.tau_pool import TauPool  # noqa: E402


@dataclass(frozen=True)
class TauRunResult:
    """Aggregate trajectory + SLA tail for a τ-aware run."""

    n_steps: int
    sla_target_kw: float
    aggregate_kw: tuple[float, ...]
    sla_violation: tuple[bool, ...]
    sla_violation_rate: float
    aggregate_min_kw: float
    aggregate_min_step: int
    train_steps: int
    test_steps: int


def tau_simulate(
    tau_pool: TauPool,
    active_ids: frozenset[str],
    standby_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    standby_dispatch_when_below: bool = True,
    seed: int = 0,
) -> TauRunResult:
    """Simulate τ-smeared trigger dynamics on a ChurnTrace.

    Each TriggerEvent fires at ``e.start_min`` minutes from t=0; an
    *exposed* DER j with random draw < e.magnitude becomes inactive at
    ``e.start_min + τ_j / 60`` minutes (= τ_j seconds delay). It
    re-activates at the event's end (``e.start_min + e.duration_min``)
    plus τ_j.

    Standby DERs are dispatched whenever the active output drops below
    SLA target (= ``standby_dispatch_when_below``).
    """
    pool = tau_pool.pool
    der_id_to_index = {d.der_id: i for i, d in enumerate(pool)}
    active_idx = tuple(der_id_to_index[i] for i in active_ids if i in der_id_to_index)
    standby_idx = tuple(der_id_to_index[i] for i in standby_ids if i in der_id_to_index)
    n_steps = len(trace.der_active_status)
    timestep_min = trace.timestep_min
    sla = trace.sla_target_kw

    # τ in minutes for time-axis arithmetic (trace events are in minutes)
    tau_min = {d.der_id: tau_pool.tau_for(d.der_id) / 60.0 for d in pool}

    # Per-step active state for each DER, initialised from trace baseline
    # (= what the trace says at t=0, e.g. for ACN-based traces). Apply
    # τ-smeared drops on top: an event for DER j flips it to False at
    # event_start + τ_j and back to True at event_end + τ_j.
    n_d = len(pool)
    active_matrix = [list(row) for row in trace.der_active_status]

    rng = random.Random(seed)
    basis = trace.trigger_basis
    for ev in trace.events:
        if ev.trigger not in basis:
            continue
        axis_idx = basis.index(ev.trigger)
        for j in range(n_d):
            if not project_exposure(pool[j], basis)[axis_idx]:
                continue
            if rng.random() >= ev.magnitude:
                continue
            t_drop_min = ev.start_min + tau_min[pool[j].der_id]
            t_recover_min = ev.start_min + ev.duration_min + tau_min[pool[j].der_id]
            step_drop = max(0, int(t_drop_min // timestep_min))
            step_recover = min(n_steps, int(t_recover_min // timestep_min))
            for step in range(step_drop, step_recover):
                active_matrix[step][j] = False

    # Compute aggregate per step
    aggregate: list[float] = []
    violation: list[bool] = []
    cap_active = tuple(pool[j].capacity_kw for j in active_idx)
    cap_standby = tuple(pool[j].capacity_kw for j in standby_idx)
    for step in range(n_steps):
        row = active_matrix[step]
        active_out = sum(cap_active[k] for k, j in enumerate(active_idx) if row[j])
        standby_avail = sum(cap_standby[k] for k, j in enumerate(standby_idx) if row[j])
        if standby_dispatch_when_below and active_out < sla:
            need = sla - active_out
            standby_out = min(standby_avail, need)
        else:
            standby_out = 0.0
        agg = active_out + standby_out
        aggregate.append(agg)
        violation.append(agg < sla)

    train_steps = trace.train_days * 24 * 60 // timestep_min
    return TauRunResult(
        n_steps=n_steps,
        sla_target_kw=sla,
        aggregate_kw=tuple(aggregate),
        sla_violation=tuple(violation),
        sla_violation_rate=sum(violation) / n_steps if n_steps > 0 else 0.0,
        aggregate_min_kw=min(aggregate) if aggregate else 0.0,
        aggregate_min_step=int(aggregate.index(min(aggregate))) if aggregate else 0,
        train_steps=train_steps,
        test_steps=n_steps - train_steps,
    )


def to_experiment_result_tau(
    run: TauRunResult,
    tau_pool: TauPool,
    active_ids: frozenset[str],
    standby_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    experiment_id: str,
    scenario_pack_id: str,
    method_label: str,
) -> ExperimentResult:
    """Wrap TauRunResult as an ExperimentResult for the BenchmarkHarness."""
    n_steps = run.n_steps
    aggregate = run.aggregate_kw
    sla = tuple(run.sla_target_kw for _ in range(n_steps))
    load_results = (
        LoadResult(asset_id="__aggregate__", demands=aggregate, supplied=aggregate),
        LoadResult(asset_id="__sla_target__", demands=sla, supplied=sla),
    )
    metadata = ExperimentMetadata(
        experiment_id=experiment_id,
        created_at=datetime.now(UTC),
        scenario_pack_id=scenario_pack_id,
        connector="try15_tau_vpp",
        seed=trace.seed,
        parameters=as_params({
            "method": method_label,
            "trace_id": trace.trace_id,
            "active_pool_size": len(active_ids),
            "standby_pool_size": len(standby_ids),
            "train_steps": run.train_steps,
            "test_steps": run.test_steps,
            "sla_target_kw": run.sla_target_kw,
        }),
    )
    return ExperimentResult(
        experiment_id=experiment_id,
        metadata=metadata,
        load_results=load_results,
    )
