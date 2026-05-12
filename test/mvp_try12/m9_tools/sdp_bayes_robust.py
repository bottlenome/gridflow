"""M9 — Bayes-Robust trigger-orthogonal portfolio (try12 contribution).

Phase 1 MS-1, addresses try11 N-2 (MILP selection bias).

The original M1 MILP (try11 ``solve_sdp_strict``) enforces
**observation-orthogonality** — i.e. selected standby DERs have observed
exposure $\\tilde{e}_{j,k} = 0$ on every active-exposed axis $k \\in E(A)$.
Under symmetric label noise rate $\\varepsilon$ on a heterogeneous pool
(prior $p_{\\tau,k}$ varies per (type, axis)), the Bayes posterior of
*true* exposure given observed-zero is

    π_{j,k} = ε p_{τ(j),k} / (ε p_{τ(j),k} + (1-ε)(1 - p_{τ(j),k}))

which is **not** uniformly small. For high-prior cells (e.g.
residential_ev × commute, p = 0.95), π ≈ 0.5; the cost-minimising MILP
exploits these label outliers, picking DERs that *look* orthogonal but
have ~50 % chance of being truly exposed.

M9 fixes this by adding a per-axis **expected-loss constraint** to the
M1 MILP:

    ∀ k ∈ E(A): Σ_j π_{j,k} · cap_j · x_j ≤ θ_k

θ_k is a designer-chosen threshold (default = 5 % of B_k). This
constraint:
  * uses the Bayes posterior π directly so MILP cannot exploit it
  * gives a **prior-independent uniform** expected-loss guarantee
    (Theorem 2): E[max_k W(S, k) | obs] ≤ max_k θ_k

The implementation reuses M1's capacity-coverage and observation-
orthogonality constraints; only the expected-loss constraint is new.
"""

from __future__ import annotations

import sys
from dataclasses import dataclass
from pathlib import Path

import pulp

# Reuse the try11 implementation infrastructure (per implementation_plan §7).
_TRY11_TOOLS = Path(__file__).resolve().parent.parent.parent / "mvp_try11"
if str(_TRY11_TOOLS) not in sys.path:
    sys.path.insert(0, str(_TRY11_TOOLS))

from tools.der_pool import DER, TRIGGER_BASIS_K3, project_exposure  # noqa: E402
from tools.sdp_optimizer import SDPSolution  # noqa: E402

# ---- Default prior table (post-perturbation) -----------------------------
#
# DEFAULT_EXPOSURE_K4 in try11 der_pool gives the type's **default** exposure;
# `make_default_pool` then applies an independent 5 %-per-axis flip. The
# resulting per-axis prior on the *post-perturbation* (= true) exposure is:
#
#   p = 0.95 if default-axis = True  (5 % flipped to False, 95 % stay True)
#   p = 0.05 if default-axis = False (5 % flipped to True,  95 % stay False)
#
# This table is the canonical prior for `solve_sdp_bayes_robust` when no
# explicit `prior_by_type_axis` is provided. Caller may override per-cell
# (sensitivity analysis, MS-5).

DEFAULT_PERTURB_RATE: float = 0.05  # mirrors try11 make_default_pool

DEFAULT_PRIOR_BY_TYPE_AXIS: dict[tuple[str, str], float] = {
    # residential_ev default K4 = (T, F, F, T): commute + comm_fault exposed
    ("residential_ev", "commute"): 0.95,
    ("residential_ev", "weather"): 0.05,
    ("residential_ev", "market"): 0.05,
    ("residential_ev", "comm_fault"): 0.95,
    # commercial_fleet default K4 = (F, F, F, T)
    ("commercial_fleet", "commute"): 0.05,
    ("commercial_fleet", "weather"): 0.05,
    ("commercial_fleet", "market"): 0.05,
    ("commercial_fleet", "comm_fault"): 0.95,
    # industrial_battery default K4 = (F, F, T, T)
    ("industrial_battery", "commute"): 0.05,
    ("industrial_battery", "weather"): 0.05,
    ("industrial_battery", "market"): 0.95,
    ("industrial_battery", "comm_fault"): 0.95,
    # heat_pump default K4 = (F, T, F, T)
    ("heat_pump", "commute"): 0.05,
    ("heat_pump", "weather"): 0.95,
    ("heat_pump", "market"): 0.05,
    ("heat_pump", "comm_fault"): 0.95,
    # utility_battery default K4 = (F, F, F, F)
    ("utility_battery", "commute"): 0.05,
    ("utility_battery", "weather"): 0.05,
    ("utility_battery", "market"): 0.05,
    ("utility_battery", "comm_fault"): 0.05,
}


def bayes_posterior(epsilon: float, prior_p: float) -> float:
    """Bayes posterior P(true=1 | observed=0) under symmetric label noise.

    π = ε p / (ε p + (1-ε)(1-p))

    Edge cases:
      * p = 0  → π = 0 (the type is never exposed; obs=0 is the certain truth)
      * p = 1  → π = 1 (always exposed; obs=0 must be a flip — but then the
                       MILP would not pick it because the constraint forces
                       Σ π·cap·x ≤ θ)
      * ε = 0  → π = 0 (noise-free observation is truth)
      * ε = 1  → π = 1 (every observation is wrong; obs=0 means truly 1)
    """
    if epsilon <= 0.0:
        return 0.0 if prior_p < 1.0 else 1.0
    if epsilon >= 1.0:
        return 1.0 if prior_p > 0.0 else 0.0
    num = epsilon * prior_p
    den = num + (1.0 - epsilon) * (1.0 - prior_p)
    if den <= 0.0:
        return 0.0
    return num / den


@dataclass(frozen=True)
class BayesRobustSDPSolution:
    """Result of M9 (Bayes-Robust SDP) MILP.

    Attributes:
        standby_ids: Selected standby DER identifiers.
        objective_cost: Total contract cost of selected standby (¥/month).
        expected_loss_per_axis: ((axis, μ_k), ...) where μ_k = Σ π_{j,k} cap_j
            for j ∈ standby. Theorem 2 guarantees μ_k ≤ θ_k for all k ∈ E(A).
        threshold_per_axis: ((axis, θ_k), ...) actually used by the MILP.
        epsilon: Label noise rate used to compute Bayes posteriors.
        feasible: True iff the MILP found an Optimal solution.
        mode: Variant label.
        trigger_basis: Trigger axes used.
        overlap_per_trigger: Per-axis count of selected DERs whose *observed*
            exposure to that axis is 1 (= orthogonality violation count;
            should be 0 for k ∈ E(A) when enforce_orthogonality is True).
        coverage_per_trigger: Per-axis capacity orthogonal to that axis,
            i.e. Σ_{j ∈ S, observed_e_jk=0} cap_j (as in M1).
    """

    standby_ids: tuple[str, ...]
    objective_cost: float
    expected_loss_per_axis: tuple[tuple[str, float], ...]
    threshold_per_axis: tuple[tuple[str, float], ...]
    epsilon: float
    feasible: bool
    mode: str
    trigger_basis: tuple[str, ...]
    overlap_per_trigger: tuple[tuple[str, int], ...]
    coverage_per_trigger: tuple[tuple[str, float], ...]

    def to_sdp_solution(self) -> SDPSolution:
        """Adapt to the legacy ``SDPSolution`` shape used by the sweep runner.

        The expected-loss / threshold / epsilon details are dropped; the
        remaining fields match ``SDPSolution`` 1-to-1.
        """
        return SDPSolution(
            standby_ids=self.standby_ids,
            objective_cost=self.objective_cost,
            trigger_basis=self.trigger_basis,
            mode=self.mode,
            feasible=self.feasible,
            overlap_per_trigger=self.overlap_per_trigger,
            coverage_per_trigger=self.coverage_per_trigger,
        )


def _exposed_active_axes(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    basis: tuple[str, ...],
) -> tuple[bool, ...]:
    active = tuple(d for d in pool if d.der_id in active_ids)
    if not active:
        return tuple(False for _ in basis)
    exposure_active = tuple(project_exposure(d, basis) for d in active)
    return tuple(any(row[k] for row in exposure_active) for k in range(len(basis)))


def solve_sdp_bayes_robust(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    burst_kw: dict[str, float],
    *,
    basis: tuple[str, ...] = TRIGGER_BASIS_K3,
    epsilon: float = DEFAULT_PERTURB_RATE,
    prior_by_type_axis: dict[tuple[str, str], float] | None = None,
    expected_loss_threshold_kw: dict[str, float] | None = None,
    expected_loss_threshold_fraction: float = 0.05,
    enforce_orthogonality: bool = True,
    mode: str = "M9-bayes-robust",
    time_limit_s: int = 60,
) -> BayesRobustSDPSolution:
    """M9 = M1 + per-axis Bayes-posterior expected-loss constraint.

    Args:
        pool: Candidate DER tuple (try12 reuses try11's pool).
        active_ids: Frozen set of DER ids in the active pool.
        burst_kw: Per-axis burst size B_k (kW).
        basis: Trigger axes used (default K3).
        epsilon: Symmetric label noise rate. Default 0.05 mirrors
            ``make_default_pool``'s perturbation rate.
        prior_by_type_axis: Mapping (type, axis) → prior P(true=1). Defaults
            to ``DEFAULT_PRIOR_BY_TYPE_AXIS`` derived from try11's
            DEFAULT_EXPOSURE_K4 + 5 %-flip.
        expected_loss_threshold_kw: Mapping axis → θ_k (kW). If None, uses
            ``expected_loss_threshold_fraction × B_k``.
        expected_loss_threshold_fraction: Default 0.05 → θ_k = 5 % of B_k.
        enforce_orthogonality: If True, observation-orthogonality is
            enforced (= M1 constraint). Set False to ablate the orthogonality
            term and isolate the expected-loss constraint's effect.
        mode: Variant label for traceability.
        time_limit_s: CBC time limit.

    Returns:
        ``BayesRobustSDPSolution``. ``feasible=False`` if CBC reports infeasible.
    """
    prior = dict(prior_by_type_axis or DEFAULT_PRIOR_BY_TYPE_AXIS)

    # Build active and candidate sets
    candidates = tuple(d for d in pool if d.der_id not in active_ids)
    n = len(candidates)
    K = len(basis)

    # Per-axis threshold θ_k
    if expected_loss_threshold_kw is None:
        theta = {ax: expected_loss_threshold_fraction * float(burst_kw.get(ax, 0.0))
                 for ax in basis}
    else:
        theta = {ax: float(expected_loss_threshold_kw.get(ax, 0.0)) for ax in basis}

    cand_exposure = tuple(project_exposure(d, basis) for d in candidates)
    exposed_active = _exposed_active_axes(pool, active_ids, basis)

    # Bayes posteriors π_{j,k} for each candidate j and axis k
    # π depends on (type τ(j), axis k) via prior. We cache one row per j.
    pi: list[tuple[float, ...]] = []
    for d in candidates:
        row = []
        for ax in basis:
            p_ja = prior.get((d.der_type, ax), 0.05)
            row.append(bayes_posterior(epsilon, p_ja))
        pi.append(tuple(row))

    if n == 0:
        return BayesRobustSDPSolution(
            standby_ids=(),
            objective_cost=0.0,
            expected_loss_per_axis=tuple((ax, 0.0) for ax in basis),
            threshold_per_axis=tuple((ax, theta[ax]) for ax in basis),
            epsilon=epsilon,
            feasible=True,
            mode=mode,
            trigger_basis=basis,
            overlap_per_trigger=tuple((ax, 0) for ax in basis),
            coverage_per_trigger=tuple((ax, 0.0) for ax in basis),
        )

    prob = pulp.LpProblem(f"sdp_{mode}", pulp.LpMinimize)
    x = [pulp.LpVariable(f"x_{i}", cat="Binary") for i in range(n)]

    prob += pulp.lpSum(
        candidates[i].contract_cost_standby * x[i] for i in range(n)
    )

    # (A) Observation-orthogonality: standby x_j = 0 if observed e_jk = 1 for
    # any k where the active set is exposed. Same as M1.
    if enforce_orthogonality:
        for k in range(K):
            if exposed_active[k]:
                prob += pulp.lpSum(
                    cand_exposure[i][k] * x[i] for i in range(n)
                ) == 0, f"orth_{basis[k]}"

    # (B) Capacity coverage: Σ_{j: e_jk=0} cap_j x_j ≥ B_k. Same as M1.
    for k in range(K):
        bk = float(burst_kw.get(basis[k], 0.0))
        if bk > 0:
            prob += pulp.lpSum(
                (0 if cand_exposure[i][k] else 1)
                * candidates[i].capacity_kw
                * x[i]
                for i in range(n)
            ) >= bk, f"cap_{basis[k]}"

    # (C) Bayes-robust expected-loss bound (= M9's new constraint)
    # For axes the active is exposed to, bound expected true-exposed capacity.
    # Note: orthogonality already forces x_j = 0 for j with observed e_jk = 1.
    # The expected-loss is therefore the sum over j with observed e_jk = 0.
    for k in range(K):
        if not exposed_active[k]:
            # Active not exposed → no expected-loss concern on this axis.
            continue
        ax = basis[k]
        prob += pulp.lpSum(
            pi[i][k] * candidates[i].capacity_kw * x[i]
            for i in range(n)
            if not cand_exposure[i][k]  # eligible per orthogonality
        ) <= theta[ax], f"bayes_loss_{ax}"

    solver = pulp.PULP_CBC_CMD(msg=False, timeLimit=time_limit_s)
    prob.solve(solver)
    feasible = pulp.LpStatus[prob.status] == "Optimal"

    if not feasible:
        return BayesRobustSDPSolution(
            standby_ids=(),
            objective_cost=float("inf"),
            expected_loss_per_axis=tuple((ax, float("nan")) for ax in basis),
            threshold_per_axis=tuple((ax, theta[ax]) for ax in basis),
            epsilon=epsilon,
            feasible=False,
            mode=mode,
            trigger_basis=basis,
            overlap_per_trigger=tuple((ax, 0) for ax in basis),
            coverage_per_trigger=tuple((ax, 0.0) for ax in basis),
        )

    def _picked(i: int) -> bool:
        v = x[i].value()
        return bool(v is not None and v > 0.5)

    selected = tuple(candidates[i].der_id for i in range(n) if _picked(i))
    cost = float(pulp.value(prob.objective))

    # Only the active-exposed axes (= E(A)) carry the orthogonality and
    # expected-loss constraints, so report bounds only for those axes
    # to keep the smoke-test invariant μ_k ≤ θ_k well-defined.
    expected_loss = tuple(
        (
            basis[k],
            float(
                sum(
                    pi[i][k] * candidates[i].capacity_kw
                    for i in range(n)
                    if _picked(i) and not cand_exposure[i][k]
                )
            ),
        )
        for k in range(K)
        if exposed_active[k]
    )
    overlap = tuple(
        (
            basis[k],
            sum(int(cand_exposure[i][k]) for i in range(n) if _picked(i)),
        )
        for k in range(K)
    )
    coverage = tuple(
        (
            basis[k],
            float(
                sum(
                    (0.0 if cand_exposure[i][k] else 1.0)
                    * candidates[i].capacity_kw
                    for i in range(n)
                    if _picked(i)
                )
            ),
        )
        for k in range(K)
    )

    return BayesRobustSDPSolution(
        standby_ids=selected,
        objective_cost=cost,
        expected_loss_per_axis=expected_loss,
        threshold_per_axis=tuple(
            (basis[k], theta[basis[k]]) for k in range(K) if exposed_active[k]
        ),
        epsilon=epsilon,
        feasible=True,
        mode=mode,
        trigger_basis=basis,
        overlap_per_trigger=overlap,
        coverage_per_trigger=coverage,
    )
