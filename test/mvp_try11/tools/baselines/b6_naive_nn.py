"""B6 — Naive NN reactive baseline.

A small MLP regressor (``sklearn.neural_network.MLPRegressor``) trained
to predict the *next-step churn fraction* from a small feature vector
(time of day, day of week, recent 12-step churn average). At experiment
time, the predicted churn fraction is used to:

  * **Design phase (B6 standalone)**: pick a standby pool whose total
    capacity scales with predicted *expected* churn. The selection is
    cheapest-per-kW, mimicking how a naive practitioner might use the
    NN output.
  * **Dispatch phase (M5 hybrid)**: at runtime, the NN's prediction
    triggers dispatch when predicted churn exceeds a threshold.

This baseline materialises §5 of the ideation record: the naive NN
ignores both heavy-tail risk and causal trigger structure, predicting
only marginal expectations.
"""

from __future__ import annotations

import numpy as np
from sklearn.neural_network import MLPRegressor
from sklearn.preprocessing import StandardScaler

from ..der_pool import DER
from ..trace_synthesizer import ChurnTrace
from .common import BaselineSolution


def _make_features(trace: ChurnTrace, train_only: bool = True) -> tuple[np.ndarray, np.ndarray]:
    """Return (X, y) where X[t] = [hour_of_day, day_of_week, recent_avg_churn]
    and y[t] = next-step churn fraction. We train on *train period* only.
    """
    n_steps = len(trace.der_active_status)
    train_steps = trace.train_days * 24 * 60 // trace.timestep_min if train_only else n_steps
    n_d = len(trace.der_ids)

    # Per-step churn fraction (1 - active_fraction)
    churn = np.array(
        [1.0 - sum(row) / n_d for row in trace.der_active_status]
    )

    feats: list[list[float]] = []
    targets: list[float] = []
    window = 12
    for t in range(window, train_steps - 1):
        # Time features
        t_min = t * trace.timestep_min
        hour = (t_min // 60) % 24
        day = (t_min // (60 * 24)) % 7
        recent = float(np.mean(churn[t - window:t]))
        feats.append([float(hour), float(day), recent])
        targets.append(float(churn[t + 1]))
    if not feats:
        return np.zeros((0, 3)), np.zeros((0,))
    return np.array(feats), np.array(targets)


def _train_nn(trace: ChurnTrace, seed: int = 0) -> tuple[MLPRegressor | None, StandardScaler | None]:
    """Train a small MLP on the train period; returns (model, scaler)."""
    X, y = _make_features(trace, train_only=True)
    if X.shape[0] < 50:
        return None, None
    scaler = StandardScaler().fit(X)
    Xs = scaler.transform(X)
    nn = MLPRegressor(
        hidden_layer_sizes=(16, 8),
        max_iter=200,
        random_state=seed,
        early_stopping=True,
    )
    nn.fit(Xs, y)
    return nn, scaler


def solve_b6_naive_nn(
    pool: tuple[DER, ...],
    active_ids: frozenset[str],
    trace: ChurnTrace,
    *,
    sla_target_kw: float = 5_000.0,
    safety_factor: float = 1.0,
    seed: int = 0,
) -> BaselineSolution:
    """Use the NN's *test-period mean prediction* to size the standby pool.

    Then pick cheapest-per-kW DERs to cover ``predicted_churn_kw *
    safety_factor``.
    """
    nn, scaler = _train_nn(trace, seed=seed)
    if nn is None or scaler is None:
        # Fallback: 30% overprovisioning
        active_cap = sum(d.capacity_kw for d in pool if d.der_id in active_ids)
        predicted_kw = 0.3 * active_cap
    else:
        # Predict on test period features (no leakage of test-period y)
        n_steps = len(trace.der_active_status)
        train_steps = trace.train_days * 24 * 60 // trace.timestep_min
        churn = np.array(
            [1.0 - sum(row) / len(trace.der_ids) for row in trace.der_active_status]
        )
        # Build test features using rolling churn from train + test
        feats: list[list[float]] = []
        window = 12
        for t in range(max(window, train_steps), n_steps - 1):
            t_min = t * trace.timestep_min
            hour = (t_min // 60) % 24
            day = (t_min // (60 * 24)) % 7
            recent = float(np.mean(churn[t - window:t]))
            feats.append([float(hour), float(day), recent])
        if not feats:
            predicted_churn_frac = 0.3
        else:
            X_test = scaler.transform(np.array(feats))
            preds = nn.predict(X_test)
            predicted_churn_frac = float(np.mean(preds))
        active_cap = sum(d.capacity_kw for d in pool if d.der_id in active_ids)
        predicted_kw = predicted_churn_frac * active_cap

    target_cap = max(predicted_kw, sla_target_kw - sum(
        d.capacity_kw for d in pool if d.der_id in active_ids
    ))
    target_cap = max(0.0, target_cap) * safety_factor

    candidates = sorted(
        (d for d in pool if d.der_id not in active_ids),
        key=lambda d: d.contract_cost_standby / max(1.0, d.capacity_kw),
    )
    selected: list[DER] = []
    cap = 0.0
    for d in candidates:
        if cap >= target_cap:
            break
        selected.append(d)
        cap += d.capacity_kw

    return BaselineSolution(
        standby_ids=tuple(d.der_id for d in selected),
        objective_cost=sum(d.contract_cost_standby for d in selected),
        method_label="B6-naive_nn",
        feasible=cap >= target_cap,
    )


# ----------------------------------------------------------------- M5 dispatch policy


def naive_nn_dispatch_policy(
    *,
    trace: ChurnTrace,
    seed: int = 0,
    threshold: float = 0.3,
):
    """Build a dispatch-policy callable backed by an NN-predicted churn.

    Used by M5 (SDP design + NN dispatch). At each timestep, the NN
    predicts the upcoming churn fraction; if above ``threshold``, all
    available standby DERs are dispatched.

    Returns a closure with the same signature as
    ``vpp_simulator.all_standby_dispatch_policy``.
    """
    nn, scaler = _train_nn(trace, seed=seed)
    n_steps = len(trace.der_active_status)
    n_d = len(trace.der_ids)
    churn_history = [1.0 - sum(row) / n_d for row in trace.der_active_status]
    window = 12

    def policy(*, t_step, sla_kw, active_output_kw, standby_pool, standby_active_status):
        # Predict NN's churn at t_step+1 if possible; otherwise fall back to
        # SLA-trigger dispatch.
        if nn is None or scaler is None or t_step < window:
            # Fall back to SLA trigger
            if active_output_kw < sla_kw:
                return tuple(standby_active_status)
            return tuple(False for _ in standby_pool)
        t_min = t_step * trace.timestep_min
        hour = (t_min // 60) % 24
        day = (t_min // (60 * 24)) % 7
        recent = float(sum(churn_history[t_step - window:t_step]) / window)
        x = scaler.transform(np.array([[float(hour), float(day), recent]]))
        pred = float(nn.predict(x)[0])
        if pred > threshold or active_output_kw < sla_kw:
            return tuple(standby_active_status)
        return tuple(False for _ in standby_pool)

    return policy
