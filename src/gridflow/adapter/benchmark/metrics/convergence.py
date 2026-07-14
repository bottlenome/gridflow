"""Non-convergence-rate metric: fraction of steps whose solve did not converge.

Issue #22. The runner already marks a failed solve as ``StepStatus.ERROR``
("solver did not converge"), but nothing rolled that up into an aggregatable
number, so a sweep could average metrics over silently non-converged cells. As
a built-in metric this makes convergence first-class: ``non_convergence_rate``
of 0.0 means every step converged, and any sweep/benchmark now surfaces
degraded convergence in its aggregates instead of hiding it.

``non_convergence_rate`` (rather than a convergence rate) so that, like the
other metrics, lower is better.
"""

from __future__ import annotations

from gridflow.usecase.result import ExperimentResult, StepStatus


class NonConvergenceRateMetric:
    name = "non_convergence_rate"
    unit = "ratio"

    def calculate(self, result: ExperimentResult) -> float:
        if not result.steps:
            # No steps → nothing failed to converge.
            return 0.0
        non_converged = sum(1 for step in result.steps if step.status is not StepStatus.SUCCESS)
        return non_converged / len(result.steps)
