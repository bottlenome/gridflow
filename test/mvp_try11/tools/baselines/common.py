"""Shared types for B1-B6 baselines."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass(frozen=True)
class BaselineSolution:
    """Standby selection from a baseline method.

    Mirrors the shape of :class:`tools.sdp_optimizer.SDPSolution` so the
    same simulator can consume both. ``feasible=False`` indicates the
    baseline was unable to construct a standby that meets coverage.
    """

    standby_ids: tuple[str, ...]
    objective_cost: float
    method_label: str
    feasible: bool
