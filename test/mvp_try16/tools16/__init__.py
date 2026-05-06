"""try16 — Tier-Hysteresis Reliability Bonding (M11) for VPP standby selection.

Modules:
- acn_drop_events: ACN session csv → per-DER drop event stream
- heavy_tail_fit: Pareto α MLE for inter-drop intervals + design-rule helpers
- tier_state: online tier-hysteresis state machine (Probation/Bronze/Silver/Gold)
- m11_selection: M11 dispatch selection rule using tier state
- baselines_lit: Fang 2015 (EWMA reputation) + Singh 2010 (2-state Markov reliability)
- run_heavy_sweep: M1 / M10 / M11 / Fang / Singh comparison on real ACN + bootstrap CI
"""
