# MVP try 2: Stochastic HCA + cross-solver + custom metric

User-paper-quality MVP scenario.

- **Parent doc**: [../../docs/mvp_scenario_v2.md](../../docs/mvp_scenario_v2.md)
- **Background**: [../../docs/research_landscape.md](../../docs/research_landscape.md)
- **Why this scenario**: [../../docs/phase1_result.md §7.12.2](../../docs/phase1_result.md)
- **Difference vs try 1**: [`mvp_scenario.md §0.5`](../../docs/mvp_scenario.md)

## Goal

Demonstrate the **paper-writing path** a researcher can walk with gridflow:

1. Author a *single* base pack + a *single* sweep_plan.yaml.
2. Run **500 random PV placements** with `gridflow sweep` on **two solvers**:
   * IEEE 13 / OpenDSS via runtime PV insertion (`OpenDSSConnector`)
   * IEEE 30 / pandapower via `create_sgen` (`PandaPowerConnector`)
3. Both sweeps run the **same custom metric** (`hosting_capacity_mw`) loaded
   as a `pack.yaml` plugin.
4. Compare the two solvers, plot the violation distributions and
   hosting-capacity bars, and produce a publication-ready figure +
   numbers in **< 5 minutes**.

The key point is that **a researcher could write a paper around this output**:
the data is novel-enough, reproducible, comparable, and the metric is
declarative (committed in git).

## Folder layout

```
test/mvp_try2/
├── README.md
├── packs/
│   ├── ieee13_sweep_base.dss      (Solve-less base, IEEE 13)
│   ├── ieee13_sweep_base.yaml     (OpenDSS base pack)
│   └── ieee30_pp_sweep_base.yaml  (pandapower base pack via case_ieee30)
├── sweep_plans/
│   ├── opendss_sweep.yaml         (500 random placements, IEEE 13)
│   └── pandapower_sweep.yaml      (500 random placements, IEEE 30)
├── tools/
│   ├── hosting_capacity.py        (custom MetricCalculator plugin)
│   ├── run_cross_solver.sh        (one-shot wrapper)
│   ├── compare_solvers.py         (cross-solver comparison)
│   └── plot_stochastic_hca.py     (matplotlib figure)
├── results/
│   └── .gitkeep                   (sweep outputs land here)
└── report.md                      (post-run report)
```

## How to run

```bash
cd test/mvp_try2
./tools/run_cross_solver.sh
```

That command:

1. Registers both base packs.
2. Runs `gridflow sweep --plan sweep_plans/opendss_sweep.yaml --connector opendss`
3. Runs `gridflow sweep --plan sweep_plans/pandapower_sweep.yaml --connector pandapower`
4. Computes `hosting_capacity_mw` from each sweep result.
5. Generates `results/stochastic_hca.png` and `results/comparison.json`.

## Prerequisites

- gridflow installed (`pip install -e .`)
- OpenDSSDirect.py (`pip install OpenDSSDirect.py`)
- pandapower (`pip install pandapower`)
- matplotlib (`pip install matplotlib`)

## Why this is a *user-paper* MVP and try 1 was not

`test/mvp_try1/` shows engineering reproducibility for a 5-point manual sweep.
`test/mvp_try2/` shows that gridflow lets a researcher run **a 1000-experiment
stochastic study across 2 solvers with a custom metric they define**, and get
publication-ready output in minutes — work that would otherwise take days of
hand-rolled scripts. See `phase1_result.md §7.12.2` for the full discussion.
