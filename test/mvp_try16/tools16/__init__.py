"""try16 — Volt-VAR delay-robust distributed control via Stokes-stratified droop (M11).

Module map:
- feeder_radial: synthetic radial PV-rich distribution feeder + linearised DistFlow
- cloud_simulator: moving cloud shadow (1-D advection along feeder)
- controllers: M0 (uniform droop), M3 (consensus PI w/ delay), M11 (depth-graded tau)
- run_voltvar: sweep + bootstrap CI
"""
