"""VPP-specific MetricCalculator implementations.

Spec: ``test/mvp_try11/implementation_plan.md`` §7.3.

Each metric is a small frozen dataclass that complies with the
:class:`gridflow.adapter.benchmark.metrics.base.MetricCalculator`
runtime-checkable Protocol (``name``, ``unit``, ``calculate``).

Metrics:
  * SLATailViolationRatio — fraction of timesteps where aggregate < target
  * SLATailViolationRatioTest — same restricted to the test period
  * TotalContractCost — sum of standby contract costs (active is fixed)
  * BurstCompensationRate — average compensation when violations occur
  * OODGap — train SLA violation ratio - test SLA violation ratio
  * StandbyPoolSize — number of standby DERs (sanity / cost proxy)

All metrics consume the gridflow ``ExperimentResult`` produced by
``vpp_simulator.to_experiment_result``. The aggregate output and SLA
target are recovered from the synthetic ``__aggregate__`` and
``__sla_target__`` load entries.

Because metric calculators in gridflow have signature ``(ExperimentResult)
-> float`` and take no additional config at call time, parameters like
``standby_pool_size`` are passed via :attr:`ExperimentResult.metadata.parameters`.
"""

from __future__ import annotations

from dataclasses import dataclass

from gridflow.usecase.result import ExperimentResult


def _aggregate_and_target(result: ExperimentResult) -> tuple[tuple[float, ...], tuple[float, ...]]:
    """Recover aggregate (kW) and target (kW) per-step from the synthetic loads."""
    agg: tuple[float, ...] | None = None
    tgt: tuple[float, ...] | None = None
    for lr in result.load_results:
        if lr.asset_id == "__aggregate__":
            agg = lr.supplied
        elif lr.asset_id == "__sla_target__":
            tgt = lr.supplied
    if agg is None or tgt is None:
        raise ValueError(
            "ExperimentResult missing __aggregate__/__sla_target__ — was it produced by vpp_simulator?"
        )
    return agg, tgt


def _train_test_split(result: ExperimentResult) -> tuple[int, int]:
    params = dict(result.metadata.parameters)
    train_steps = int(params.get("train_steps", 0))
    test_steps = int(params.get("test_steps", 0))
    return train_steps, test_steps


@dataclass(frozen=True)
class SLATailViolationRatio:
    """Fraction of timesteps with aggregate < SLA target (full horizon)."""

    name: str = "sla_violation_ratio"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        agg, tgt = _aggregate_and_target(result)
        n = len(agg)
        if n == 0:
            return 0.0
        violations = sum(1 for a, t in zip(agg, tgt) if a < t)
        return violations / n


@dataclass(frozen=True)
class SLATailViolationRatioTest:
    """SLA violation ratio restricted to the test period."""

    name: str = "sla_violation_ratio_test"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        agg, tgt = _aggregate_and_target(result)
        train_steps, test_steps = _train_test_split(result)
        if test_steps == 0:
            return 0.0
        agg_test = agg[train_steps:train_steps + test_steps]
        tgt_test = tgt[train_steps:train_steps + test_steps]
        violations = sum(1 for a, t in zip(agg_test, tgt_test) if a < t)
        return violations / len(agg_test)


@dataclass(frozen=True)
class SLATailViolationRatioTrain:
    """SLA violation ratio restricted to the train period."""

    name: str = "sla_violation_ratio_train"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        agg, tgt = _aggregate_and_target(result)
        train_steps, _ = _train_test_split(result)
        if train_steps == 0:
            return 0.0
        agg_train = agg[:train_steps]
        tgt_train = tgt[:train_steps]
        violations = sum(1 for a, t in zip(agg_train, tgt_train) if a < t)
        return violations / len(agg_train)


@dataclass(frozen=True)
class OODGap:
    """OOD gap = test SLA violation ratio - train SLA violation ratio.

    Positive values mean degradation under OOD/extreme conditions in the
    test period. SDP's structural guarantee predicts a small / zero gap
    on basis-internal traces (C1, C2, C5) and a non-zero gap on C4 (out-
    of-basis trigger).
    """

    name: str = "ood_gap"
    unit: str = "ratio_diff"

    def calculate(self, result: ExperimentResult) -> float:
        train_metric = SLATailViolationRatioTrain().calculate(result)
        test_metric = SLATailViolationRatioTest().calculate(result)
        return test_metric - train_metric


@dataclass(frozen=True)
class StandbyPoolSize:
    """Number of standby DERs (read from metadata.parameters)."""

    name: str = "standby_pool_size"
    unit: str = "count"

    def calculate(self, result: ExperimentResult) -> float:
        for k, v in result.metadata.parameters:
            if k == "standby_pool_size":
                return float(v)
        return 0.0


@dataclass(frozen=True)
class BurstCompensationRate:
    """Average aggregate / SLA-target ratio over violation steps.

    Reports how much of the contracted target was actually delivered
    when a violation occurred. 1.0 = no violations; 0.0 = total blackout.
    """

    name: str = "burst_compensation_rate"
    unit: str = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        agg, tgt = _aggregate_and_target(result)
        violation_pairs = [(a, t) for a, t in zip(agg, tgt) if a < t]
        if not violation_pairs:
            return 1.0
        total_a = sum(a for a, _ in violation_pairs)
        total_t = sum(t for _, t in violation_pairs)
        return total_a / total_t if total_t > 0 else 0.0


VPP_METRICS: tuple = (
    SLATailViolationRatio(),
    SLATailViolationRatioTest(),
    SLATailViolationRatioTrain(),
    OODGap(),
    StandbyPoolSize(),
    BurstCompensationRate(),
)
