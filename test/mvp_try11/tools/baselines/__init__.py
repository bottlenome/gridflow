"""Phase 1 baselines for the SDP comparison study (B1-B6).

Each baseline returns a frozen ``BaselineSolution`` with the selected
standby DER ID set, mirroring the SDPSolution shape so a single
:class:`vpp_simulator.simulate_vpp` call can consume any of them.
"""

from .b1_static_overprov import solve_b1_static_overprov
from .b2_stochastic_program import solve_b2_stochastic_program
from .b3_wasserstein_dro import solve_b3_wasserstein_dro
from .b4_markowitz import solve_b4_markowitz
from .b5_financial_causal import solve_b5_financial_causal
from .b6_naive_nn import solve_b6_naive_nn, naive_nn_dispatch_policy
from .common import BaselineSolution

__all__ = (
    "BaselineSolution",
    "solve_b1_static_overprov",
    "solve_b2_stochastic_program",
    "solve_b3_wasserstein_dro",
    "solve_b4_markowitz",
    "solve_b5_financial_causal",
    "solve_b6_naive_nn",
    "naive_nn_dispatch_policy",
)
