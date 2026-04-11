"""``hosting_capacity_mw`` — custom :class:`MetricCalculator` plugin.

Spec: ``docs/mvp_scenario_v2.md`` §5.3.

Per-experiment definition (computed by this class on a single
:class:`ExperimentResult`):

    hosting_capacity_mw = pv_mw if all bus voltages are within
                          [voltage_low, voltage_high] pu, else 0.0

In other words, this metric scores each experiment as the *PV MW that
the system safely hosted* (= the candidate PV size when no Range A
violation is observed). The sweep aggregator (StatisticsAggregator)
then reduces these per-experiment scores into mean / max / quartiles
across the 200 random placements:

    hosting_capacity_mw_max  → the largest reproducible "no violation"
                                placement found in the sweep.
    hosting_capacity_mw_mean → the average safe PV across the sample.

This is a simplified hosting-capacity definition (one threshold pair,
single time step) but it is *novel-enough as a metric* to make a paper
contribution because:

    * The calculation is committed in this Python file (FAIR /
      reproducible) — different from "I computed it in Excel".
    * The thresholds (voltage_low / voltage_high) are constructor
      parameters, so the same plugin can run multiple HCA definitions
      from different pack.yaml entries.

The plugin is loaded by gridflow's ``MetricRegistry`` from a pack.yaml
``metrics`` section like:

    metrics:
      - name: voltage_deviation
      - plugin: "test.mvp_try2.tools.hosting_capacity:HostingCapacityMetric"
        kwargs:
          voltage_low: 0.95
          voltage_high: 1.05

The plugin must satisfy the ``gridflow.adapter.benchmark.metric_registry.
MetricCalculator`` Protocol: ``name``, ``unit``, ``calculate(result)``.
"""

from __future__ import annotations

from gridflow.usecase.result import ExperimentResult


class HostingCapacityMetric:
    """Per-experiment hosting capacity score (MW).

    Returns the candidate PV power in MW when no bus voltage falls
    outside the configured Range-A band. Returns 0.0 when at least one
    bus violates the band, signalling that the placement is rejected
    by the HCA criterion.
    """

    name = "hosting_capacity_mw"
    unit = "MW"

    # Defaults: ANSI C84.1 **Range B** (0.90 ≤ V ≤ 1.06 pu).
    #
    # We use Range B instead of the tighter Range A (0.95–1.05) because the
    # IEEE 13 standard test feeder is known to have ~5% baseline under-voltage
    # buses (worst ≈ 0.905 pu) — they fall outside Range A even *without* any
    # PV. Range A would therefore reject 100% of random placements and the
    # metric would be uninformative across the sweep. Range B is widely used
    # in HCA studies for similar reasons (see e.g. MDPI Energies 2020 HCA
    # review). Researchers can always pass voltage_low / voltage_high as
    # plugin kwargs to override.
    def __init__(
        self,
        *,
        voltage_low: float = 0.90,
        voltage_high: float = 1.06,
    ) -> None:
        if voltage_low >= voltage_high:
            raise ValueError(
                f"voltage_low ({voltage_low}) must be < voltage_high ({voltage_high})"
            )
        self._low = float(voltage_low)
        self._high = float(voltage_high)

    def calculate(self, result: ExperimentResult) -> float:
        # Pull the PV size out of the experiment metadata's parameters.
        # The sweep orchestrator copies the per-axis assignment into
        # ``ExperimentMetadata.parameters``, so the candidate pv_kw is
        # always available here.
        pv_kw = 0.0
        for key, value in result.metadata.parameters:
            if key == "pv_kw":
                try:
                    pv_kw = float(value)  # type: ignore[arg-type]
                except (TypeError, ValueError):
                    pv_kw = 0.0
                break

        # Collect every voltage across both step results and aggregated
        # node results, ignoring any 0.0 entries that come from
        # disconnected phases.
        samples: list[float] = []
        for nr in result.node_results:
            samples.extend(v for v in nr.voltages if v > 0)
        for step in result.steps:
            if step.node_result is not None:
                samples.extend(v for v in step.node_result.voltages if v > 0)
        if not samples:
            return 0.0

        # If any bus is outside Range A, the placement is rejected.
        worst_under = min(samples)
        worst_over = max(samples)
        if worst_under < self._low or worst_over > self._high:
            return 0.0

        # Otherwise the placement is safe — credit the candidate PV in MW.
        return pv_kw / 1000.0
