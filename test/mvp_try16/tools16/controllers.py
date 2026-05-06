"""Three Volt-VAR controllers compared in try16.

  * M0  — uniform droop (baseline; all inverters share the same tau, K)
  * M3  — consensus-PI with comm delay (literature baseline)
  * M11 — Stokes-stratified droop (try16 contribution): tau_j scales
          with electrical depth d_j of the inverter from substation.

Each controller has the same interface:

    state_init(feeder, params) -> ControllerState
    step(state, V_t, dt) -> (Q_t, new_state)

so that ``run_voltvar.simulate`` can drive any of them.

Common conventions:
  * Q sign: positive Q = inverter *injecting* reactive power (raises V)
  * Q is bounded by [-pv_cap_kw, +pv_cap_kw] per inverter
  * Each inverter sees ONLY its own bus voltage (M0, M11) or its
    neighbour-set bus voltages with comm delay (M3)
"""

from __future__ import annotations

from dataclasses import dataclass, field

from .feeder_radial import RadialFeeder


# ---------- M0: uniform droop ----------
@dataclass
class M0State:
    feeder: RadialFeeder
    tau_s: float
    k_droop: float       # Q (kW) per pu of voltage error per kW of cap
    v_ref_pu: float
    q: list[float] = field(default_factory=list)

    def __post_init__(self):
        if not self.q:
            self.q = [0.0] * self.feeder.n_bus


def m0_init(feeder: RadialFeeder, *, tau_s: float = 5.0,
            k_droop: float = 18.0, v_ref_pu: float = 1.00) -> M0State:
    return M0State(feeder=feeder, tau_s=tau_s, k_droop=k_droop, v_ref_pu=v_ref_pu)


def m0_step(state: M0State, v_pu: tuple[float, ...], dt: float) -> tuple[float, ...]:
    """Each inverter: dQ/dt = (1/tau)(K * (Vref - V) * cap - Q)."""
    n = state.feeder.n_bus
    new_q = list(state.q)
    for i in range(n):
        cap = state.feeder.pv_cap_kw[i]
        if cap <= 0:
            new_q[i] = 0.0
            continue
        target = state.k_droop * (state.v_ref_pu - v_pu[i]) * cap
        target = max(-cap, min(cap, target))
        new_q[i] = state.q[i] + (dt / state.tau_s) * (target - state.q[i])
        new_q[i] = max(-cap, min(cap, new_q[i]))
    state.q = new_q
    return tuple(new_q)


# ---------- M3: consensus-PI with comm delay ----------
@dataclass
class M3State:
    feeder: RadialFeeder
    tau_s: float
    k_p: float
    k_i: float
    delay_s: float       # uniform comm delay
    v_ref_pu: float
    q: list[float] = field(default_factory=list)
    integ: list[float] = field(default_factory=list)
    v_history: list[tuple[float, ...]] = field(default_factory=list)
    t_steps: int = 0

    def __post_init__(self):
        n = self.feeder.n_bus
        if not self.q:
            self.q = [0.0] * n
        if not self.integ:
            self.integ = [0.0] * n


def m3_init(feeder: RadialFeeder, *, tau_s: float = 5.0,
            k_p: float = 18.0, k_i: float = 6.0,
            delay_s: float = 0.50, v_ref_pu: float = 1.00) -> M3State:
    return M3State(feeder=feeder, tau_s=tau_s, k_p=k_p, k_i=k_i,
                   delay_s=delay_s, v_ref_pu=v_ref_pu)


def m3_step(state: M3State, v_pu: tuple[float, ...], dt: float) -> tuple[float, ...]:
    """Consensus-PI: each inverter uses a *delayed* mean of ALL bus voltages.

    The delayed mean models comm-shared global state, with comm latency
    state.delay_s.  This is a fair literature-style baseline for
    distributed coordination.
    """
    state.v_history.append(v_pu)
    delay_steps = max(1, int(round(state.delay_s / dt)))
    if len(state.v_history) > delay_steps:
        v_delayed = state.v_history[-delay_steps - 1]
    else:
        v_delayed = state.v_history[0]
    n = state.feeder.n_bus
    # Consensus: each inverter regulates against the delayed *neighbourhood mean*
    mean_v = sum(v_delayed) / n
    new_q = list(state.q)
    for i in range(n):
        cap = state.feeder.pv_cap_kw[i]
        if cap <= 0:
            new_q[i] = 0.0
            continue
        err_local = state.v_ref_pu - v_pu[i]
        err_consensus = state.v_ref_pu - mean_v
        # P-term: local (instant), I-term: consensus (delayed)
        target = (state.k_p * err_local + state.k_i * state.integ[i]) * cap
        state.integ[i] += dt * err_consensus
        # anti-windup
        state.integ[i] = max(-1.0, min(1.0, state.integ[i]))
        target = max(-cap, min(cap, target))
        new_q[i] = state.q[i] + (dt / state.tau_s) * (target - state.q[i])
        new_q[i] = max(-cap, min(cap, new_q[i]))
    state.q = new_q
    state.t_steps += 1
    return tuple(new_q)


# ---------- M11: Stokes-stratified droop ----------
@dataclass
class M11State:
    feeder: RadialFeeder
    tau_min_s: float
    tau_max_s: float
    k_droop_base: float
    v_ref_pu: float
    q: list[float] = field(default_factory=list)
    tau_per_bus_s: tuple[float, ...] = ()
    k_per_bus: tuple[float, ...] = ()

    def __post_init__(self):
        n = self.feeder.n_bus
        if not self.q:
            self.q = [0.0] * n
        d_pu = self.feeder.depth_pu
        d_max = max(d_pu) if max(d_pu) > 0 else 1.0
        if not self.tau_per_bus_s:
            # Stokes-stratified tau: end buses (large d) need fastest
            # tracking (smallest tau) because their dV/dP sensitivity
            # is largest in LinDistFlow (X_cum * N proportional to d).
            self.tau_per_bus_s = tuple(
                self.tau_max_s - (self.tau_max_s - self.tau_min_s) * (d / d_max)
                for d in d_pu
            )
        if not self.k_per_bus:
            # K-grading: end buses get higher K because their effective
            # voltage authority (dV_j/dQ_j ∝ X_cum to bus j) is highest.
            # Substation buses are V-clamped by the slack and do not
            # benefit from high gain.  Schedule (linear in depth ratio):
            #   K_j = k_droop_base * (0.3 + 1.7 * d_j / d_max)
            # so substation gets 0.3*K_base, end gets 2.0*K_base.
            self.k_per_bus = tuple(
                self.k_droop_base * (0.3 + 1.7 * (d / d_max))
                for d in d_pu
            )


def m11_init(feeder: RadialFeeder, *, tau_min_s: float = 0.3,
             tau_max_s: float = 25.0, k_droop: float = 18.0,
             v_ref_pu: float = 1.00) -> M11State:
    """Stokes-stratified droop: tau_j increases linearly with depth.

    Rationale (Theorem 6, theorems.md): a depth-graded LPF cascade
    decouples the spatio-temporal cloud-edge propagation from the
    feeder voltage hunting mode.  Equivalent to graded sediment beds
    where Stokes terminal velocity stratifies particles without
    coordination.
    """
    return M11State(feeder=feeder, tau_min_s=tau_min_s,
                    tau_max_s=tau_max_s, k_droop_base=k_droop, v_ref_pu=v_ref_pu)


def m11_step(state: M11State, v_pu: tuple[float, ...], dt: float) -> tuple[float, ...]:
    n = state.feeder.n_bus
    new_q = list(state.q)
    for i in range(n):
        cap = state.feeder.pv_cap_kw[i]
        if cap <= 0:
            new_q[i] = 0.0
            continue
        k_i = state.k_per_bus[i]
        target = k_i * (state.v_ref_pu - v_pu[i]) * cap
        target = max(-cap, min(cap, target))
        tau_i = state.tau_per_bus_s[i]
        new_q[i] = state.q[i] + (dt / tau_i) * (target - state.q[i])
        new_q[i] = max(-cap, min(cap, new_q[i]))
    state.q = new_q
    return tuple(new_q)
