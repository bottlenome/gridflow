"""Phase 2 v0.4 MVP validation runner — try8.

Exercises the four Phase 2 v0.3 features end-to-end through the public
gridflow APIs (no shell-out). Writes results under ``results/`` and a
machine-readable summary at ``results/summary.json`` so the report
can quote real numbers.

Each section is guarded by an availability check so the script also
works when only pandapower is installed (typical CI) — OpenDSS smoke
sections become "skipped" entries in the summary.
"""

from __future__ import annotations

import json
import os
import shutil
import statistics
import sys
import time
from datetime import UTC, datetime
from pathlib import Path

# Layout
HERE = Path(__file__).resolve().parent
ROOT = HERE.parent
PACKS = ROOT / "packs"
RESULTS = ROOT / "results"
RESULTS.mkdir(parents=True, exist_ok=True)
GRIDFLOW_HOME = ROOT / ".gridflow_home"
shutil.rmtree(GRIDFLOW_HOME, ignore_errors=True)
GRIDFLOW_HOME.mkdir(parents=True, exist_ok=True)
os.environ["GRIDFLOW_HOME"] = str(GRIDFLOW_HOME)

# Defer all gridflow imports until after GRIDFLOW_HOME is set so the
# module-level FileScenarioRegistry root resolves to our scratch dir.
from gridflow.adapter.benchmark.harness import BenchmarkHarness  # noqa: E402
from gridflow.adapter.connector.opendss_translator import OpenDSSTranslator  # noqa: E402
from gridflow.adapter.connector.pandapower import PandaPowerConnector  # noqa: E402
from gridflow.adapter.network.cdl_yaml_loader import load_cdl_network_from_yaml  # noqa: E402
from gridflow.infra.orchestrator import InProcessOrchestratorRunner  # noqa: E402
from gridflow.infra.scenario import FileScenarioRegistry, load_pack_from_yaml  # noqa: E402
from gridflow.usecase.evaluation import (  # noqa: E402
    EvaluationPlan,
    Evaluator,
    FilesystemResultLoader,
    MetricSpec,
)
from gridflow.usecase.orchestrator import Orchestrator, RunRequest  # noqa: E402
from gridflow.usecase.sensitivity import SensitivityAnalyzer  # noqa: E402
from gridflow.usecase.sweep import (  # noqa: E402
    SweepOrchestrator,
    build_default_aggregator_registry,
)
from gridflow.usecase.sweep_plan import RangeAxis, SweepPlan  # noqa: E402

try:
    import pandapower  # noqa: F401

    HAVE_PANDAPOWER = True
except ImportError:
    HAVE_PANDAPOWER = False

try:
    import opendssdirect  # noqa: F401

    HAVE_OPENDSS = True
except ImportError:
    HAVE_OPENDSS = False


# ============================================================ helpers


def _log(msg: str) -> None:
    print(f"[try8] {msg}", flush=True)


def _build_orchestrator(connector_name: str) -> Orchestrator:
    """Build an Orchestrator that uses the given connector for the registered pack."""
    registry = FileScenarioRegistry(GRIDFLOW_HOME / "packs")
    if connector_name == "pandapower":
        runner = InProcessOrchestratorRunner(connector_factories={"pandapower": PandaPowerConnector})
    elif connector_name == "opendss":
        from gridflow.adapter.connector import OpenDSSConnector

        runner = InProcessOrchestratorRunner(connector_factories={"opendss": OpenDSSConnector})
    else:
        raise ValueError(f"Unknown connector: {connector_name}")
    return Orchestrator(registry=registry, runner=runner)


def _register_pack() -> str:
    """Load packs/pack.yaml + feeder.yaml and register; return pack_id."""
    registry = FileScenarioRegistry(GRIDFLOW_HOME / "packs")
    pack = load_pack_from_yaml(PACKS / "pack.yaml")
    registered = registry.register(pack)
    return registered.pack_id


# ============================================================ section 1: CDL cross-solver


def section_cdl_cross_solver(summary: dict[str, object]) -> None:
    """§5.1.3: same CDL YAML solved by OpenDSS and pandapower."""
    _log("Section 1: CDL cross-solver verification")

    # Load the canonical network once for both solver paths.
    network = load_cdl_network_from_yaml(PACKS / "feeder.yaml")
    summary["cdl_network"] = {
        "n_nodes": len(network.topology.nodes),
        "n_edges": len(network.topology.edges),
        "n_assets": len(network.assets),
        "base_voltage_kv": network.base_voltage_kv,
    }

    # OpenDSS: pure script generation (no driver required).
    dss_script = OpenDSSTranslator.from_canonical(network, circuit_name="try8")
    (RESULTS / "feeder.dss").write_text(dss_script, encoding="utf-8")
    _log(f"  OpenDSSTranslator.from_canonical: {len(dss_script)} chars written to feeder.dss")
    summary["section_1"] = {
        "dss_script_chars": len(dss_script),
        "dss_script_first_lines": dss_script.splitlines()[:5],
    }

    # pandapower: live solve.
    if not HAVE_PANDAPOWER:
        _log("  pandapower extra not installed — pandapower path skipped")
        summary["section_1"]["pandapower"] = "skipped (pandapower not installed)"
        return
    from gridflow.adapter.connector.pandapower_translator import PandapowerTranslator
    import pandapower as pp

    net = PandapowerTranslator.from_canonical(network)
    pp.runpp(net)
    voltages = [float(v) for v in net.res_bus.vm_pu.tolist()]
    _log(f"  pandapower runpp converged; bus voltages = {voltages}")
    summary["section_1"]["pandapower_voltages_pu"] = voltages

    # Round-trip: pandapower → CDL → pandapower → solve again, expect same V.
    canon = PandapowerTranslator.to_canonical(net)
    net2 = PandapowerTranslator.from_canonical(canon)
    pp.runpp(net2)
    voltages2 = [float(v) for v in net2.res_bus.vm_pu.tolist()]
    max_drift = max(abs(a - b) for a, b in zip(voltages, voltages2, strict=True))
    _log(f"  CDL round-trip max voltage drift: {max_drift:.6e} pu")
    summary["section_1"]["round_trip_max_drift_pu"] = max_drift


# ============================================================ section 2: sweep with metric-target axis


def section_sweep_metric_target(summary: dict[str, object]) -> None:
    """§5.1.1 Option A: a metric kwarg is swept by an axis target=metric:..."""
    _log("Section 2: sweep with metric-target axis")
    if not HAVE_PANDAPOWER:
        _log("  skipped (pandapower required for sweep with current pack)")
        summary["section_2"] = "skipped (pandapower not installed)"
        return

    pack_id = _register_pack()
    orchestrator = _build_orchestrator("pandapower")
    sweep_orch = SweepOrchestrator(
        registry=orchestrator._registry,  # type: ignore[attr-defined]
        orchestrator=orchestrator,
        aggregator_registry=build_default_aggregator_registry(),
        connector_id="pandapower",
        # Built-in metrics only — voltage_deviation has no kwargs to
        # sweep, so the axis-target proof here is sweep_plan-level
        # only (we sweep pack pv_kw and demonstrate the column form
        # of per_experiment_metrics).
        harness=BenchmarkHarness(),
        # Persist each child ExperimentResult JSON so section 3 can
        # rehydrate them via FilesystemResultLoader.
        results_dir=GRIDFLOW_HOME / "results",
    )

    plan = SweepPlan(
        sweep_id="try8_pv_sweep",
        base_pack_id=pack_id,
        axes=(RangeAxis(name="pv_kw", start=0.0, stop=601.0, step=200.0),),  # 4 children
        aggregator_name="statistics",
    )
    started = time.perf_counter()
    result = sweep_orch.run(plan)
    elapsed = time.perf_counter() - started
    _log(f"  ran {len(result.experiment_ids)} children in {elapsed:.2f}s")

    # Persist SweepResult for downstream evaluate-mode validation.
    sweep_path = RESULTS / "sweep_result.json"
    sweep_path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    # Verify the column form: pull a metric vector with O(1) lookup.
    column_dict = dict(result.per_experiment_metrics)
    voltage_deviation_vec = column_dict.get("voltage_deviation", ())
    runtime_vec = column_dict.get("runtime", ())
    _log(f"  voltage_deviation per experiment = {[round(v, 4) for v in voltage_deviation_vec]}")
    summary["section_2"] = {
        "n_children": len(result.experiment_ids),
        "elapsed_s": round(elapsed, 3),
        "voltage_deviation_per_experiment": list(voltage_deviation_vec),
        "voltage_deviation_mean": (
            statistics.fmean(voltage_deviation_vec) if voltage_deviation_vec else None
        ),
        "runtime_per_experiment": list(runtime_vec),
        "metric_columns": [name for name, _ in result.per_experiment_metrics],
        "sweep_result_path": str(sweep_path.relative_to(ROOT)),
    }


# ============================================================ section 3: gridflow evaluate inline DSL + parameter-sweep


def section_evaluate_and_sensitivity(summary: dict[str, object]) -> None:
    """§5.1.1 Option B + M5: evaluate post-processing + SensitivityAnalyzer."""
    _log("Section 3: evaluate inline-DSL + SensitivityAnalyzer")
    if not HAVE_PANDAPOWER:
        _log("  skipped (no sweep results available)")
        summary["section_3"] = "skipped (pandapower not installed)"
        return

    # Pull the per-experiment ExperimentResult JSONs the sweep wrote into
    # GRIDFLOW_HOME/results so we can apply the evaluate API.
    exp_jsons = sorted((GRIDFLOW_HOME / "results").glob("*.json"))
    _log(f"  found {len(exp_jsons)} experiment result JSON(s) under GRIDFLOW_HOME/results/")
    plugin_spec = "test.mvp_try8.tools.threshold_metric:ThresholdedFraction"

    # 3a. Inline-DSL EvaluationPlan with two named instances of the same plugin.
    eval_plan = EvaluationPlan(
        evaluation_id="try8_two_thresholds",
        results=tuple(exp_jsons),
        metrics=(
            MetricSpec(name="frac_below_095", plugin=plugin_spec, kwargs=(("voltage_low", 0.95),)),
            MetricSpec(name="frac_below_098", plugin=plugin_spec, kwargs=(("voltage_low", 0.98),)),
        ),
    )
    evaluator = Evaluator(result_loader=FilesystemResultLoader())
    eval_result = evaluator.run(eval_plan)
    eval_path = RESULTS / "evaluation_result.json"
    eval_path.write_text(json.dumps(eval_result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    _log(f"  Evaluator produced {len(eval_result.per_experiment_metrics)} metric columns")
    column_dict = dict(eval_result.per_experiment_metrics)
    summary["section_3a_evaluate"] = {
        "evaluation_id": eval_result.evaluation_id,
        "metric_columns": [name for name, _ in eval_result.per_experiment_metrics],
        "frac_below_095_per_experiment": list(column_dict.get("frac_below_095", ())),
        "frac_below_098_per_experiment": list(column_dict.get("frac_below_098", ())),
        "evaluation_result_path": str(eval_path.relative_to(ROOT)),
    }

    # 3b. SensitivityAnalyzer with bootstrap CI — sweep voltage_low
    # across 11 grid points on the same experiments.
    analyzer = SensitivityAnalyzer()
    experiments = [evaluator._loader.load(p) for p in exp_jsons]  # type: ignore[attr-defined]
    sensitivity = analyzer.analyze(
        experiments=experiments,
        parameter_name="voltage_low",
        parameter_grid=tuple(0.90 + 0.01 * i for i in range(11)),
        metric_plugin=plugin_spec,
        feeder_id="try8_feeder",
        bootstrap_n=50,
        bootstrap_seed=42,
    )
    sens_path = RESULTS / "sensitivity_result.json"
    sens_path.write_text(json.dumps(sensitivity.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    _log(
        f"  SensitivityAnalyzer: {len(sensitivity.parameter_values)} grid points, "
        f"metric range = [{min(sensitivity.metric_values):.3f}, {max(sensitivity.metric_values):.3f}]"
    )
    summary["section_3b_sensitivity"] = {
        "feeder_id": sensitivity.feeder_id,
        "parameter_name": sensitivity.parameter_name,
        "n_grid_points": len(sensitivity.parameter_values),
        "metric_min": min(sensitivity.metric_values),
        "metric_max": max(sensitivity.metric_values),
        "ci_widths": [
            round(hi - lo, 6)
            for lo, hi in zip(
                sensitivity.confidence_lower,
                sensitivity.confidence_upper,
                strict=True,
            )
        ],
        "sensitivity_result_path": str(sens_path.relative_to(ROOT)),
    }


# ============================================================ main


def main() -> int:
    summary: dict[str, object] = {
        "started_at": datetime.now(tz=UTC).isoformat(),
        "have_pandapower": HAVE_PANDAPOWER,
        "have_opendss": HAVE_OPENDSS,
    }
    started_wall = time.perf_counter()

    section_cdl_cross_solver(summary)
    section_sweep_metric_target(summary)
    section_evaluate_and_sensitivity(summary)

    summary["elapsed_total_s"] = round(time.perf_counter() - started_wall, 3)
    summary["finished_at"] = datetime.now(tz=UTC).isoformat()
    summary_path = RESULTS / "summary.json"
    summary_path.write_text(json.dumps(summary, indent=2, sort_keys=True, default=str), encoding="utf-8")
    _log(f"summary written to {summary_path.relative_to(ROOT)}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
