"""Typer CLI entry point — ``gridflow`` command.

Subcommands (MVP):
    scenario register <yaml>
    scenario list
    scenario get <pack_id>
    run <pack_id> [--steps N] [--seed N] [--output DIR]
    results <experiment_id>
    benchmark --compare <baseline_exp> <candidate_exp>

All commands share state through a single :class:`CLIContext` built in
:func:`_build_context`; tests instantiate the ``CLIContext`` directly and call
the underlying command functions instead of going through typer.
"""

from __future__ import annotations

import json
import os
import uuid
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import typer

from gridflow.adapter.benchmark import BenchmarkHarness, ReportGenerator
from gridflow.adapter.benchmark.metric_registry import (
    build_default_metric_registry,
    load_metric_plugin,
)
from gridflow.adapter.cli.evaluate_dsl import (
    EvaluateDSLError,
    parse_metric_spec,
    parse_parameter_sweep,
)
from gridflow.adapter.cli.formatter import OutputFormat, OutputFormatter
from gridflow.adapter.connector import OpenDSSConnector
from gridflow.adapter.connector.opendss_control import OpenDSSGridModel, PVDeviceSpec
from gridflow.adapter.export import PaperExporter, load_comparison_table_json
from gridflow.domain.error import (
    BenchmarkError,
    ConfigError,
    ExperimentNotFoundError,
    ExportError,
    GridflowError,
    PackNotFoundError,
)
from gridflow.domain.scenario.registry import ScenarioRegistry
from gridflow.domain.util.params import get_param
from gridflow.infra.container_manager import (
    ContainerEndpoint,
    NoOpContainerManager,
)
from gridflow.infra.logging import configure_logging, get_logger
from gridflow.infra.orchestrator import (
    ContainerOrchestratorRunner,
    InProcessOrchestratorRunner,
)
from gridflow.infra.scenario import FileScenarioRegistry, load_pack_from_yaml
from gridflow.usecase.control import (
    ControllableDevice,
    LocalDroop,
    NoControl,
    run_control_experiment,
)
from gridflow.usecase.cross_validation import EngineCrossValidator
from gridflow.usecase.evaluation import (
    EvaluationPlan,
    Evaluator,
    FilesystemResultLoader,
)
from gridflow.usecase.evaluation_yaml_loader import (
    EvaluationPlanLoadError,
    load_evaluation_plan_from_yaml,
)
from gridflow.usecase.interfaces import ConnectorInterface, OrchestratorRunner
from gridflow.usecase.orchestrator import Orchestrator, RunRequest
from gridflow.usecase.result import ExperimentResult, StepResult
from gridflow.usecase.sensitivity import SensitivityAnalyzer
from gridflow.usecase.sweep import (
    ChildProgress,
    SweepOrchestrator,
    build_default_aggregator_registry,
)
from gridflow.usecase.sweep_yaml_loader import load_sweep_plan_bundle_from_yaml
from gridflow.usecase.violation_attribution import ViolationAttributor

app = typer.Typer(
    name="gridflow",
    add_completion=False,
    help="Grid simulation and benchmarking CLI.",
    no_args_is_help=True,
)

scenario_app = typer.Typer(help="Manage Scenario Packs.", no_args_is_help=True)
app.add_typer(scenario_app, name="scenario")

export_app = typer.Typer(
    help="Export results into publication-ready artifacts.",
    no_args_is_help=True,
)
app.add_typer(export_app, name="export")


# Typer default singletons (ruff B008: Option/Argument must not be inline defaults).
_YAML_ARG = typer.Argument(..., exists=True, readable=True, help="Path to pack.yaml")
_PACK_ID_OPT = typer.Option(None, "--id", help="Override pack_id")
_PACK_ID_ARG = typer.Argument(...)
_RUN_PACK_ARG = typer.Argument(..., help="Registered pack_id")
_RUN_STEPS_OPT = typer.Option(1, "--steps", "-n", help="Number of solver steps")
_RUN_SEED_OPT = typer.Option(None, "--seed", help="Override seed from pack")
_RUN_CONNECTOR_OPT = typer.Option("opendss", "--connector", help="Connector name")
_RUN_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
_RESULTS_ID_ARG = typer.Argument(...)
_RESULTS_FMT_OPT = typer.Option("json", "--format", help="plain|json|table")
_VALIDATE_PACK_ARG = typer.Argument(..., help="Registered pack_id to solve on every engine")
_VALIDATE_ENGINES_OPT = typer.Option(
    "opendss,pandapower",
    "--engines",
    help="Comma-separated connector names to cross-check (>=2). The first is the reference.",
)
_VALIDATE_TOL_OPT = typer.Option(
    1e-6,
    "--tol",
    min=0.0,
    help="Max absolute per-node voltage difference (pu) still counted as agreement.",
)
_VALIDATE_STEPS_OPT = typer.Option(1, "--steps", "-n", help="Number of solver steps per engine")
_VALIDATE_OUTPUT_OPT = typer.Option(None, "--output", help="Write CrossValidationReport JSON to this path")
_VALIDATE_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
_ATTR_BASELINE_OPT = typer.Option(..., "--baseline", help="No-control (existing-load) experiment_id")
_ATTR_CANDIDATE_OPT = typer.Option(..., "--candidate", help="With-control experiment_id to attribute")
_ATTR_VMIN_OPT = typer.Option(..., "--v-min", help="Envelope lower bound (pu). Required — no default band.")
_ATTR_VMAX_OPT = typer.Option(..., "--v-max", help="Envelope upper bound (pu). Required — no default band.")
_ATTR_OUTPUT_OPT = typer.Option(None, "--output", help="Write ViolationAttribution JSON to this path")
_ATTR_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
_CTRL_PACK_ARG = typer.Argument(..., help="Registered pack_id to run the control study on")
_CTRL_STRATEGY_OPT = typer.Option("local_droop", "--strategy", help="Control strategy: no_control | local_droop")
_CTRL_PV_BUS_OPT = typer.Option(
    ..., "--pv-bus", help="Bus (with phases) the controllable PV attaches to, e.g. 675.1.2.3"
)
_CTRL_PV_KW_OPT = typer.Option(..., "--pv-kw", help="Controllable PV active power (kW)")
_CTRL_PV_KV_OPT = typer.Option(4.16, "--pv-kv", help="PV line-to-line nominal voltage (kV)")
_CTRL_PV_PHASES_OPT = typer.Option(3, "--pv-phases", help="PV phase count")
_CTRL_SENSE_BUS_OPT = typer.Option(
    None, "--sense-bus", help="Bus the controller senses (default: the PV bus without its phase suffix)"
)
_CTRL_KVAR_LIMIT_OPT = typer.Option(
    ..., "--kvar-limit", help="Inverter reactive limit (kvar); action clamped to +/- this"
)
_CTRL_RELAX_OPT = typer.Option(
    0.3, "--relaxation", min=0.0, help="Loop damping in (0,1]; <1 avoids bang-bang on stiff feeders"
)
_CTRL_MAXITERS_OPT = typer.Option(40, "--max-iters", help="Max control iterations")
_CTRL_FREEZE_OPT = typer.Option(
    False, "--freeze-regulators", help="Hold regulator/cap taps fixed (isolate the Volt-VAR effect)"
)
_CTRL_OUTPUT_OPT = typer.Option(None, "--output", help="Write the ExperimentResult JSON to this path")
_CTRL_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
_BENCH_BASE_OPT = typer.Option(
    ..., "--baseline", help="Baseline experiment_id. Repeat to pass replicates for a statistical comparison."
)
_BENCH_CAND_OPT = typer.Option(
    ..., "--candidate", help="Candidate experiment_id. Repeat to pass replicates for a statistical comparison."
)
_BENCH_OUTPUT_OPT = typer.Option(None, "--output", help="Write JSON report to path")
_BENCH_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
_BENCH_ALPHA_OPT = typer.Option(0.05, "--alpha", help="Significance level (statistical comparison).")
_BENCH_CORRECTION_OPT = typer.Option(
    "holm", "--correction", help="Multiple-comparison correction: holm | bh (statistical comparison)."
)
_BENCH_BOOTSTRAP_N_OPT = typer.Option(
    2000, "--bootstrap-n", min=0, help="Bootstrap resamples for the mean CIs (statistical comparison)."
)
_BENCH_SEED_OPT = typer.Option(0, "--seed", help="Seed for permutation/bootstrap resampling (deterministic).")
_SWEEP_PLAN_OPT = typer.Option(
    ...,
    "--plan",
    exists=True,
    readable=True,
    help="Path to sweep_plan.yaml",
)
_SWEEP_CONNECTOR_OPT = typer.Option(
    "opendss",
    "--connector",
    help="Connector name to drive every child experiment",
)
_SWEEP_OUTPUT_OPT = typer.Option(
    None,
    "--output",
    help="Write SweepResult JSON to this path (default: stdout)",
)
_SWEEP_FMT_OPT = typer.Option("json", "--format", help="plain|json|table")
_SWEEP_RESUME_OPT = typer.Option(
    False,
    "--resume",
    help=(
        "Reuse already-computed child results under GRIDFLOW_HOME/results "
        "(matched by the plan's deterministic experiment ids). Only the "
        "missing cells are simulated; skipped cells are logged."
    ),
)
_SWEEP_METRIC_PLUGIN_OPT = typer.Option(
    None,
    "--metric-plugin",
    help=(
        "Custom MetricCalculator plugin in 'module.path:ClassName' form. "
        "Repeatable. Plugins are loaded into the sweep's BenchmarkHarness "
        "and their values feed the aggregator."
    ),
)
_EVAL_PLAN_OPT = typer.Option(
    None,
    "--plan",
    exists=True,
    readable=True,
    help="Path to evaluation.yaml (case-B form). Mutually exclusive with --results / --metric inline-DSL form.",
)
_EVAL_RESULTS_OPT = typer.Option(
    None,
    "--results",
    exists=True,
    readable=True,
    help=(
        "Inline-DSL form (case A): SweepResult JSON, results dir, or single ExperimentResult JSON. "
        "Combine with --metric (repeatable) and optional --parameter-sweep."
    ),
)
_EVAL_METRIC_OPT = typer.Option(
    None,
    "--metric",
    help=(
        "Inline metric spec — repeatable. Forms: 'name' (built-in), "
        "'name:module:Cls', 'name:module:Cls(k=v,...)'. Required with --results."
    ),
)
_EVAL_PARAMETER_SWEEP_OPT = typer.Option(
    None,
    "--parameter-sweep",
    help=(
        "Trigger SensitivityAnalyzer with one inline-DSL grid: "
        "'kwarg:start:stop:n'. Requires exactly one --metric with a plugin."
    ),
)
_EVAL_FEEDER_ID_OPT = typer.Option(
    "unknown",
    "--feeder-id",
    help="Provenance label written to SensitivityResult.feeder_id (--parameter-sweep only).",
)
_EVAL_BOOTSTRAP_N_OPT = typer.Option(
    0,
    "--bootstrap-n",
    min=0,
    help=(
        "If > 0, resample experiments this many times per grid point and "
        "emit a 95% percentile CI on the mean (--parameter-sweep only)."
    ),
)
_EVAL_BOOTSTRAP_SEED_OPT = typer.Option(
    0,
    "--bootstrap-seed",
    help="Seed for --bootstrap-n resampling (deterministic; --parameter-sweep only).",
)
_EVAL_OUTPUT_OPT = typer.Option(
    None,
    "--output",
    help="Write EvaluationResult / SensitivityResult JSON to this path (default: stdout)",
)
_EVAL_FMT_OPT = typer.Option("json", "--format", help="plain|json|table")


# ---------------------------------------------------------------------- context


@dataclass
class CLIContext:
    """Bag of dependencies shared by every CLI command.

    Exposed publicly so tests can build one with in-memory fakes and call
    command functions directly, skipping the typer layer.

    Attributes:
        connector_factory: ``(connector_id: str) → ConnectorInterface``.
            Consumed to build the per-connector factory map passed to
            :class:`InProcessOrchestratorRunner`; this keeps the
            monkeypatch-friendly indirection that tests rely on while
            giving the runner a clean ``{id: Callable}`` registry.
    """

    registry: ScenarioRegistry
    results_dir: Path
    formatter: OutputFormatter
    harness: BenchmarkHarness
    report_gen: ReportGenerator
    connector_factory: Callable[[str], ConnectorInterface]


def _build_context(fmt: OutputFormat = OutputFormat.PLAIN) -> CLIContext:
    root = Path(os.environ.get("GRIDFLOW_HOME", str(Path.home() / ".gridflow")))
    registry = FileScenarioRegistry(root / "packs")
    results_dir = root / "results"
    results_dir.mkdir(parents=True, exist_ok=True)
    return CLIContext(
        registry=registry,
        results_dir=results_dir,
        formatter=OutputFormatter(fmt),
        harness=BenchmarkHarness(),
        report_gen=ReportGenerator(),
        connector_factory=_default_connector_factory,
    )


def _default_connector_factory(name: str) -> ConnectorInterface:
    if name == "opendss":
        return OpenDSSConnector()
    if name == "pandapower":
        # Imported lazily so the CLI keeps working when the [pandapower]
        # extra is not installed.
        from gridflow.adapter.connector.pandapower import PandaPowerConnector

        return PandaPowerConnector()
    raise GridflowError(f"Unknown connector: {name}")


# ---------------------------------------------------------------------- runner selection


def build_runner_from_env(
    *,
    connector: str,
    connector_factory: Callable[[str], ConnectorInterface],
) -> OrchestratorRunner:
    """Pick an :class:`OrchestratorRunner` based on process environment.

    The selection is driven by the ``GRIDFLOW_RUNNER`` environment
    variable so that the same CLI works identically from a developer
    shell (``inprocess`` default) and from inside the ``gridflow-core``
    Docker Compose service (``container`` set by the compose file).

    Supported values:
        * ``inprocess`` (default): instantiate
          :class:`InProcessOrchestratorRunner` with a factory that
          delegates to the caller-provided ``connector_factory``.
        * ``container``: instantiate :class:`ContainerOrchestratorRunner`
          backed by :class:`NoOpContainerManager`. The CLI always runs
          *inside* a docker-compose service, so sibling containers are
          already live via ``depends_on: service_healthy``; the runner
          only needs to speak REST. Host-side scripts that want full
          docker-compose lifecycle control should construct
          :class:`DockerComposeContainerManager` directly.

    Container mode environment variables:
        * ``GRIDFLOW_CONNECTOR_ENDPOINTS``: comma-separated list of
          ``connector_id=service_name@base_url`` triples, e.g.
          ``opendss=opendss-connector@http://opendss-connector:8000``.
          At least one endpoint is required.

    Raises:
        ConfigError: On invalid / missing env vars.
    """
    runner_name = os.environ.get("GRIDFLOW_RUNNER", "inprocess").strip().lower()
    if runner_name in {"", "inprocess", "in-process", "local"}:
        return InProcessOrchestratorRunner(
            connector_factories={connector: lambda: connector_factory(connector)},
        )
    if runner_name in {"container", "docker", "compose"}:
        endpoints = _parse_container_endpoints()
        # The CLI lives inside a docker-compose service; sibling
        # containers are already started via ``depends_on: service_healthy``
        # so the runner only needs to speak REST, not control Docker.
        # Host-side scripts that want full lifecycle control can build
        # ``ContainerOrchestratorRunner`` with ``DockerComposeContainerManager``
        # directly (Phase 2).
        manager = NoOpContainerManager()
        return ContainerOrchestratorRunner(
            container_manager=manager,
            endpoints=endpoints,
        )
    raise ConfigError(
        f"Unknown GRIDFLOW_RUNNER value: {runner_name!r}. Expected 'inprocess' or 'container'.",
        context={"GRIDFLOW_RUNNER": runner_name},
    )


def _parse_container_endpoints() -> dict[str, ContainerEndpoint]:
    """Parse ``GRIDFLOW_CONNECTOR_ENDPOINTS`` into a runner endpoint map.

    Format: ``id=service@url[,id2=service2@url2...]``.
    """
    raw = os.environ.get("GRIDFLOW_CONNECTOR_ENDPOINTS", "").strip()
    if not raw:
        raise ConfigError(
            "GRIDFLOW_CONNECTOR_ENDPOINTS is required when GRIDFLOW_RUNNER=container",
            context={"expected_format": "id=service@url[,...]"},
        )
    endpoints: dict[str, ContainerEndpoint] = {}
    for entry in raw.split(","):
        entry = entry.strip()
        if not entry:
            continue
        if "=" not in entry or "@" not in entry:
            raise ConfigError(
                f"invalid endpoint entry: {entry!r}",
                context={"expected_format": "id=service@url"},
            )
        connector_id, service_and_url = entry.split("=", 1)
        service_name, base_url = service_and_url.split("@", 1)
        endpoints[connector_id.strip()] = ContainerEndpoint(
            connector_id=connector_id.strip(),
            service_name=service_name.strip(),
            base_url=base_url.strip(),
        )
    if not endpoints:
        raise ConfigError(
            "GRIDFLOW_CONNECTOR_ENDPOINTS parsed to empty map",
            context={"raw": raw},
        )
    return endpoints


# ---------------------------------------------------------------------- helpers


def _save_result(ctx: CLIContext, result: ExperimentResult) -> Path:
    path = ctx.results_dir / f"{result.experiment_id}.json"
    path.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    return path


def _load_result(ctx: CLIContext, experiment_id: str) -> ExperimentResult:
    path = ctx.results_dir / f"{experiment_id}.json"
    if not path.exists():
        raise ExperimentNotFoundError(
            f"Experiment '{experiment_id}' not found",
            context={"experiment_id": experiment_id, "path": str(path)},
        )
    data = json.loads(path.read_text(encoding="utf-8"))
    return _rehydrate_experiment_result(data)


def _rehydrate_experiment_result(data: dict[str, Any]) -> ExperimentResult:
    """Minimal ``to_dict`` → ``ExperimentResult`` round-trip for the CLI."""
    from datetime import datetime

    from gridflow.domain.cdl import ExperimentMetadata
    from gridflow.domain.result import NodeResult
    from gridflow.domain.util.params import as_params
    from gridflow.usecase.result import StepStatus

    meta_raw: dict[str, Any] = data["metadata"]
    metadata = ExperimentMetadata(
        experiment_id=meta_raw["experiment_id"],
        created_at=datetime.fromisoformat(meta_raw["created_at"]),
        scenario_pack_id=meta_raw["scenario_pack_id"],
        connector=meta_raw["connector"],
        seed=meta_raw.get("seed"),
        parameters=as_params(meta_raw.get("parameters") or {}),
    )

    steps: list[StepResult] = []
    for s in data.get("steps") or []:
        nr_raw = s.get("node_result")
        nr = None
        if isinstance(nr_raw, dict):
            nr = NodeResult(node_id=nr_raw["node_id"], voltages=tuple(nr_raw["voltages"]))
        bus_voltages = tuple((str(bus), float(v)) for bus, v in (s.get("bus_voltages") or ()))
        steps.append(
            StepResult(
                step_id=int(s["step_id"]),
                timestamp=datetime.fromisoformat(s["timestamp"]),
                status=StepStatus(s["status"]),
                elapsed_ms=float(s.get("elapsed_ms", 0.0)),
                node_result=nr,
                bus_voltages=bus_voltages,
                error=s.get("error"),
            )
        )

    node_results: list[NodeResult] = []
    for n in data.get("node_results") or []:
        node_results.append(NodeResult(node_id=n["node_id"], voltages=tuple(n["voltages"])))

    metrics_raw: dict[str, Any] = data.get("metrics") or {}
    metrics = tuple(sorted((k, float(v)) for k, v in metrics_raw.items()))

    return ExperimentResult(
        experiment_id=str(data["experiment_id"]),
        metadata=metadata,
        steps=tuple(steps),
        node_results=tuple(node_results),
        metrics=metrics,
        elapsed_s=float(data.get("elapsed_s", 0.0)),
    )


# ---------------------------------------------------------------------- commands


@scenario_app.command("register")
def scenario_register(
    yaml_path: Path = _YAML_ARG,
    pack_id: str | None = _PACK_ID_OPT,
) -> None:
    """Register a Scenario Pack from a ``pack.yaml`` file."""
    ctx = _build_context()
    pack = load_pack_from_yaml(yaml_path, pack_id=pack_id)
    registered = ctx.registry.register(pack)
    typer.echo(ctx.formatter.render({"pack_id": registered.pack_id, "status": registered.status.value}))


@scenario_app.command("list")
def scenario_list() -> None:
    """List all registered Scenario Packs."""
    ctx = _build_context()
    rows = [
        {"pack_id": p.pack_id, "name": p.name, "version": p.version, "status": p.status.value}
        for p in ctx.registry.list_all()
    ]
    typer.echo(ctx.formatter.render(rows))


@scenario_app.command("get")
def scenario_get(pack_id: str = _PACK_ID_ARG) -> None:
    """Show a single registered pack."""
    ctx = _build_context()
    try:
        pack = ctx.registry.get(pack_id)
    except PackNotFoundError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(ctx.formatter.render(pack.to_dict()))


_CLONE_NEW_ID_OPT = typer.Option(..., "--id", help="pack_id for the clone")


@scenario_app.command("clone")
def scenario_clone(
    pack_id: str = _PACK_ID_ARG,
    new_id: str = _CLONE_NEW_ID_OPT,
) -> None:
    """Clone a registered pack under a new pack_id (AS-5 baseline workflow).

    The clone keeps all content and the citation, drops the baseline flag,
    records ``cloned_from`` provenance, and is registered immediately so the
    researcher can edit parameters and run a comparison experiment.
    """
    ctx = _build_context()
    try:
        original = ctx.registry.get(pack_id)
        registered = ctx.registry.register(original.clone(new_id))
    except GridflowError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    typer.echo(
        ctx.formatter.render(
            {
                "pack_id": registered.pack_id,
                "cloned_from": registered.cloned_from,
                "baseline": registered.metadata.baseline,
                "status": registered.status.value,
            }
        )
    )


@app.command("run")
def run_command(
    pack_id: str = _RUN_PACK_ARG,
    steps: int = _RUN_STEPS_OPT,
    seed: int | None = _RUN_SEED_OPT,
    connector: str = _RUN_CONNECTOR_OPT,
    fmt: str = _RUN_FMT_OPT,
) -> None:
    """Run an experiment end-to-end and persist the result."""
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.run")

    # Pick in-process vs container runner from the environment
    # (GRIDFLOW_RUNNER). The CLI stays Phase 1-scoped (one connector per
    # run) while the runner is already multi-connector-capable per spec
    # 03d §3.8.2.
    try:
        runner = build_runner_from_env(
            connector=connector,
            connector_factory=ctx.connector_factory,
        )
    except GridflowError as exc:
        log.error("runner_selection_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    orchestrator = Orchestrator(registry=ctx.registry, runner=runner)
    try:
        result = orchestrator.run(
            RunRequest(
                pack_id=pack_id,
                connector_id=connector,
                total_steps=steps,
                seed=seed,
            )
        )
    except GridflowError as exc:
        log.error("run_failed", pack_id=pack_id, error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    path = _save_result(ctx, result)
    log.info(
        "experiment_completed",
        experiment_id=result.experiment_id,
        pack_id=pack_id,
        elapsed_s=result.elapsed_s,
    )
    typer.echo(
        ctx.formatter.render(
            {
                "experiment_id": result.experiment_id,
                "pack_id": pack_id,
                "steps": len(result.steps),
                "elapsed_s": result.elapsed_s,
                "result_path": str(path),
            }
        )
    )


@app.command("validate-engines")
def validate_engines_command(
    pack_id: str = _VALIDATE_PACK_ARG,
    engines: str = _VALIDATE_ENGINES_OPT,
    tol: float = _VALIDATE_TOL_OPT,
    steps: int = _VALIDATE_STEPS_OPT,
    output: Path | None = _VALIDATE_OUTPUT_OPT,
    fmt: str = _VALIDATE_FMT_OPT,
) -> None:
    """Solve one pack on multiple engines and cross-check the results (#20).

    Runs ``pack_id`` through each ``--engines`` connector, then compares every
    engine's node voltages against the first (reference) engine within ``--tol``
    and reports any solver that failed to converge. Exits non-zero when the
    engines disagree — so a single-engine quirk (numerical artifact, local
    optimum, bug) can no longer masquerade as a physical result.
    """
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.validate_engines")

    engine_names = [e.strip() for e in engines.split(",") if e.strip()]
    if len(engine_names) < 2:
        typer.echo("--engines needs at least two comma-separated connector names.")
        raise typer.Exit(code=2)
    if len(engine_names) != len(set(engine_names)):
        typer.echo(f"--engines must be unique, got {engine_names}.")
        raise typer.Exit(code=2)

    results_by_engine: list[tuple[str, ExperimentResult]] = []
    for engine in engine_names:
        try:
            runner = build_runner_from_env(connector=engine, connector_factory=ctx.connector_factory)
            orchestrator = Orchestrator(registry=ctx.registry, runner=runner)
            result = orchestrator.run(RunRequest(pack_id=pack_id, connector_id=engine, total_steps=steps))
        except GridflowError as exc:
            log.error("validate_engine_run_failed", engine=engine, error_code=exc.error_code, message=exc.message)
            typer.echo(f"engine '{engine}' failed: {exc}")
            raise typer.Exit(code=1) from exc
        results_by_engine.append((engine, result))

    try:
        report = EngineCrossValidator().validate(
            pack_id=pack_id,
            results_by_engine=results_by_engine,
            tol=tol,
        )
    except GridflowError as exc:
        log.error("validate_engines_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(report.to_dict(), indent=2, sort_keys=True), encoding="utf-8")

    log.info(
        "validate_engines_completed",
        pack_id=pack_id,
        engines=engine_names,
        agree=report.agree,
        tol=tol,
    )
    typer.echo(ctx.formatter.render(report.to_dict()))
    if not report.agree:
        # Non-zero exit is the machine-readable verdict: the engines disagree
        # (or one did not converge), so any result built on a single engine is
        # suspect until reconciled.
        raise typer.Exit(code=1)


@app.command("attribute-violations")
def attribute_violations_command(
    baseline: str = _ATTR_BASELINE_OPT,
    candidate: str = _ATTR_CANDIDATE_OPT,
    v_min: float = _ATTR_VMIN_OPT,
    v_max: float = _ATTR_VMAX_OPT,
    output: Path | None = _ATTR_OUTPUT_OPT,
    fmt: str = _ATTR_FMT_OPT,
) -> None:
    """Split a candidate's voltage violations into pre-existing vs induced (#24).

    Compares the with-control ``--candidate`` against the no-control
    ``--baseline`` over the required ``--v-min`` / ``--v-max`` envelope and
    reports ``baseline_only`` (already out of band under existing load — not the
    controller's doing) vs ``dispatch_induced`` (the controller pushed it out of
    band) vs ``total``. This prevents crediting a controller for pre-existing
    violations it cannot fix — the try11 "5x reduction" misjudgment.
    """
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.attribute_violations")

    base = _load_result(ctx, baseline)
    cand = _load_result(ctx, candidate)
    try:
        attribution = ViolationAttributor().attribute(
            baseline=base,
            candidate=cand,
            v_min=v_min,
            v_max=v_max,
        )
    except GridflowError as exc:
        log.error("attribute_violations_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(attribution.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    typer.echo(ctx.formatter.render(attribution.to_dict()))


@app.command("control")
def control_command(
    pack_id: str = _CTRL_PACK_ARG,
    strategy: str = _CTRL_STRATEGY_OPT,
    pv_bus: str = _CTRL_PV_BUS_OPT,
    pv_kw: float = _CTRL_PV_KW_OPT,
    pv_kv: float = _CTRL_PV_KV_OPT,
    pv_phases: int = _CTRL_PV_PHASES_OPT,
    sense_bus: str | None = _CTRL_SENSE_BUS_OPT,
    kvar_limit: float = _CTRL_KVAR_LIMIT_OPT,
    relaxation: float = _CTRL_RELAX_OPT,
    max_iters: int = _CTRL_MAXITERS_OPT,
    freeze_regulators: bool = _CTRL_FREEZE_OPT,
    output: Path | None = _CTRL_OUTPUT_OPT,
    fmt: str = _CTRL_FMT_OPT,
) -> None:
    """Run a Volt-VAR control strategy on a feeder and persist the result (#29).

    A controllable PV inverter (``--pv-bus``/``--pv-kw``) is placed on the
    feeder; the chosen ``--strategy`` sets its reactive power to regulate the
    sensed bus. The result is a normal ExperimentResult, so its experiment_id
    feeds straight into ``gridflow benchmark`` — letting a new strategy be
    compared statistically against the reference ``no_control`` / ``local_droop``
    (the method comparison the framework previously could not do).
    """
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.control")

    strategies = {"no_control": NoControl, "local_droop": LocalDroop}
    if strategy not in strategies:
        typer.echo(f"--strategy must be one of {sorted(strategies)}, got {strategy!r}.")
        raise typer.Exit(code=2)

    try:
        pack = ctx.registry.get(pack_id)
    except GridflowError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    master_name = str(get_param(pack.metadata.parameters, "master_file") or "IEEE13Nodeckt.dss")
    master_path = pack.network_dir / master_name
    if not master_path.exists():
        typer.echo(f"master DSS file not found for pack '{pack_id}': {master_path}")
        raise typer.Exit(code=1)

    resolved_sense = sense_bus or pv_bus.split(".", 1)[0]
    spec = PVDeviceSpec(
        device_id="PV", sense_bus=resolved_sense, inject_bus=pv_bus, kw=pv_kw, kv=pv_kv, phases=pv_phases
    )
    device = ControllableDevice(device_id="PV", bus=resolved_sense, kvar_limit=kvar_limit)
    experiment_id = f"ctrl-{strategy}-{uuid.uuid4().hex[:10]}"
    try:
        grid = OpenDSSGridModel(master_path=str(master_path), devices=(spec,), freeze_regulators=freeze_regulators)
        result = run_control_experiment(
            grid,
            (device,),
            strategies[strategy](),
            experiment_id=experiment_id,
            pack_id=pack_id,
            connector="opendss",
            parameters={"pv_bus": pv_bus, "pv_kw": pv_kw, "sense_bus": resolved_sense, "kvar_limit": kvar_limit},
            max_iters=max_iters,
            relaxation=relaxation,
        )
    except GridflowError as exc:
        log.error("control_failed", pack_id=pack_id, error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    path = _save_result(ctx, result)
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(result.to_dict(), indent=2, sort_keys=True), encoding="utf-8")
    params = dict(result.metadata.parameters)
    vmax = max(result.node_results[0].voltages, default=0.0) if result.node_results else 0.0
    log.info(
        "control_completed", experiment_id=experiment_id, strategy=strategy, iterations=params.get("control_iterations")
    )
    typer.echo(
        ctx.formatter.render(
            {
                "experiment_id": experiment_id,
                "strategy": strategy,
                "iterations": params.get("control_iterations"),
                "settled": params.get("control_settled"),
                "final_kvar": params.get("control_kvar_PV"),
                "vmax": vmax,
                "result_path": str(path),
            }
        )
    )


@app.command("results")
def results_command(
    experiment_id: str = _RESULTS_ID_ARG,
    fmt: str = _RESULTS_FMT_OPT,
) -> None:
    """Print a previously saved experiment result."""
    ctx = _build_context(fmt=OutputFormat(fmt))
    result = _load_result(ctx, experiment_id)
    typer.echo(ctx.formatter.render(result.to_dict()))


@app.command("benchmark")
def benchmark_command(
    baseline: list[str] = _BENCH_BASE_OPT,
    candidate: list[str] = _BENCH_CAND_OPT,
    output: Path | None = _BENCH_OUTPUT_OPT,
    fmt: str = _BENCH_FMT_OPT,
    alpha: float = _BENCH_ALPHA_OPT,
    correction: str = _BENCH_CORRECTION_OPT,
    bootstrap_n: int = _BENCH_BOOTSTRAP_N_OPT,
    seed: int = _BENCH_SEED_OPT,
) -> None:
    """Compare saved experiments via the benchmark harness.

    One ``--baseline`` and one ``--candidate`` → the legacy mean-delta report.
    Repeat either flag (replicates) → a statistical comparison with effect
    size, permutation p-values (corrected for multiple metrics), bootstrap CIs
    and a ``significant`` verdict that a mean delta alone can no longer earn
    (issue #18).
    """
    ctx = _build_context(fmt=OutputFormat(fmt))

    if len(baseline) > 1 or len(candidate) > 1:
        base_group = [_load_result(ctx, b) for b in baseline]
        cand_group = [_load_result(ctx, c) for c in candidate]
        try:
            stat_report = ctx.harness.compare_groups(
                base_group,
                cand_group,
                alpha=alpha,
                correction=correction,
                bootstrap_n=bootstrap_n,
                seed=seed,
            )
        except (BenchmarkError, ValueError) as exc:
            typer.echo(str(exc))
            raise typer.Exit(code=2) from exc
        if output is not None:
            ctx.report_gen.write_comparison(stat_report, output)
        if ctx.formatter.format is OutputFormat.PLAIN:
            typer.echo(ctx.report_gen.render_statistical_text(stat_report))
        else:
            typer.echo(ctx.formatter.render(stat_report.to_dict()))
        return

    base = _load_result(ctx, baseline[0])
    cand = _load_result(ctx, candidate[0])
    report = ctx.harness.compare(base, cand)
    if output is not None:
        ctx.report_gen.write_comparison(report, output)
    if ctx.formatter.format is OutputFormat.PLAIN:
        typer.echo(ctx.report_gen.render_comparison_text(report))
    else:
        typer.echo(ctx.formatter.render(report.to_dict()))


_EXPORT_INPUT_ARG = typer.Argument(
    ...,
    exists=True,
    readable=True,
    help="Comparison JSON: canonical table or `gridflow benchmark --output` report",
)
_EXPORT_OUTPUT_OPT = typer.Option(
    Path("paper_export"),
    "--output",
    "-o",
    help="Directory to write the artifacts into",
)


@export_app.command("paper")
def export_paper_command(
    input_json: Path = _EXPORT_INPUT_ARG,
    output: Path = _EXPORT_OUTPUT_OPT,
) -> None:
    """Export a comparison result into paper-ready artifacts (AS-5).

    Writes ``table.tex`` (booktabs comparison table, best values bold),
    ``data.csv``, ``plot_comparison.py`` (matplotlib, reads data.csv)
    and ``caption.txt`` (caption template with experiment conditions).
    """
    try:
        table = load_comparison_table_json(input_json)
        written = PaperExporter().export(table, output)
    except ExportError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc
    for path in written:
        typer.echo(str(path))


@app.command("sweep")
def sweep_command(
    plan: Path = _SWEEP_PLAN_OPT,
    connector: str = _SWEEP_CONNECTOR_OPT,
    output: Path | None = _SWEEP_OUTPUT_OPT,
    fmt: str = _SWEEP_FMT_OPT,
    metric_plugins: list[str] | None = _SWEEP_METRIC_PLUGIN_OPT,
    resume: bool = _SWEEP_RESUME_OPT,
) -> None:
    """Run a parameter sweep defined by a sweep_plan.yaml file.

    The plan describes a base ``ScenarioPack`` plus one or more parameter
    axes (range / choice / random_uniform / random_choice). The sweep
    expands the axes into N child experiments, drives each through the
    same ``Orchestrator`` the ``run`` command uses, and aggregates the
    per-experiment metrics into sweep-level statistics via the registered
    aggregator.

    Custom metrics can be loaded via ``--metric-plugin module:Class``
    (repeatable). Each plugin is added to the BenchmarkHarness driving
    the sweep so its per-experiment values flow into the aggregator
    alongside the built-in voltage_deviation / runtime metrics.

    The result is a ``SweepResult`` JSON containing every child
    experiment ID, the plan content hash, and the aggregated metrics.
    """
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.sweep")

    bundle = load_sweep_plan_bundle_from_yaml(plan)
    sweep_plan = bundle.plan

    # Build a metric registry: built-ins + any --metric-plugin specs.
    metric_registry = build_default_metric_registry()
    for spec in metric_plugins or []:
        try:
            metric = load_metric_plugin(spec)
        except GridflowError as exc:
            log.error(
                "metric_plugin_load_failed",
                error_code=exc.error_code,
                message=exc.message,
                spec=spec,
            )
            typer.echo(str(exc))
            raise typer.Exit(code=1) from exc
        metric_registry.register(metric)

    harness = BenchmarkHarness(metrics=tuple(metric_registry.get(name) for name in metric_registry.names()))

    try:
        runner = build_runner_from_env(
            connector=connector,
            connector_factory=ctx.connector_factory,
        )
    except GridflowError as exc:
        log.error("runner_selection_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    orchestrator = Orchestrator(registry=ctx.registry, runner=runner)
    sweep_orchestrator = SweepOrchestrator(
        registry=ctx.registry,
        orchestrator=orchestrator,
        aggregator_registry=build_default_aggregator_registry(),
        connector_id=connector,
        harness=harness,
        # Metric specs declared in the sweep YAML ('metrics:' section)
        # feed the per-child re-instantiation path used when an axis
        # targets 'metric:<name>' (§5.1.1 Option A).
        metric_specs=bundle.metric_specs,
        results_dir=ctx.results_dir,
        result_loader=FilesystemResultLoader(),
    )
    # Count cache hits so a --resume run reports what it skipped (never
    # silently — a skipped cell must not read as "recomputed", issue #21).
    cache_hits = 0

    def _on_child(progress: ChildProgress) -> None:
        nonlocal cache_hits
        if progress.cached:
            cache_hits += 1

    try:
        result = sweep_orchestrator.run(sweep_plan, resume=resume, on_child=_on_child)
    except GridflowError as exc:
        log.error(
            "sweep_failed",
            sweep_id=sweep_plan.sweep_id,
            error_code=exc.error_code,
            message=exc.message,
        )
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    payload = result.to_dict()
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(
            json.dumps(payload, indent=2, sort_keys=True),
            encoding="utf-8",
        )

    log.info(
        "sweep_completed",
        sweep_id=result.sweep_id,
        n_experiments=len(result.experiment_ids),
        cache_hits=cache_hits,
        computed=len(result.experiment_ids) - cache_hits,
        resume=resume,
        elapsed_s=result.elapsed_s,
    )

    if ctx.formatter.format is OutputFormat.PLAIN:
        typer.echo(
            ctx.formatter.render(
                {
                    "sweep_id": result.sweep_id,
                    "base_pack_id": result.base_pack_id,
                    "n_experiments": len(result.experiment_ids),
                    "elapsed_s": result.elapsed_s,
                    "plan_hash": result.plan_hash,
                }
            )
        )
    else:
        typer.echo(ctx.formatter.render(payload))


@app.command("evaluate")
def evaluate_command(
    plan: Path | None = _EVAL_PLAN_OPT,
    results: Path | None = _EVAL_RESULTS_OPT,
    metrics: list[str] | None = _EVAL_METRIC_OPT,
    parameter_sweep: str | None = _EVAL_PARAMETER_SWEEP_OPT,
    feeder_id: str = _EVAL_FEEDER_ID_OPT,
    bootstrap_n: int = _EVAL_BOOTSTRAP_N_OPT,
    bootstrap_seed: int = _EVAL_BOOTSTRAP_SEED_OPT,
    output: Path | None = _EVAL_OUTPUT_OPT,
    fmt: str = _EVAL_FMT_OPT,
) -> None:
    """Re-apply metrics to already-simulated experiment results.

    Two surface forms (M4 — phase2_result.md §C):

    **Case B — ``--plan eval.yaml``**: full multi-metric evaluation with
    declarative YAML. Any ``--results``/``--metric`` flags are forbidden
    in this mode (mutual exclusion).

    **Case A — inline DSL**: ``--results <path>`` plus one or more
    ``--metric`` flags. Optional ``--parameter-sweep "kw:start:stop:n"``
    triggers :class:`SensitivityAnalyzer` to vary a metric kwarg across
    the grid (requires exactly one ``--metric`` with a plugin).

    Unlike ``gridflow sweep`` this command runs **no simulation** — it
    is a pure post-processing step so researchers can re-compute
    metrics with different kwargs (e.g. an 11-point voltage-threshold
    sweep) without re-running the underlying N simulations. See
    ``docs/phase1_result.md`` §5.1.1.
    """
    ctx = _build_context(fmt=OutputFormat(fmt))
    configure_logging(level="INFO")
    log = get_logger("gridflow.cli.evaluate")

    plan_mode = plan is not None
    inline_mode = results is not None or bool(metrics)
    if plan_mode and inline_mode:
        typer.echo("--plan is mutually exclusive with --results / --metric (M4 case A vs B).")
        raise typer.Exit(code=2)
    if not plan_mode and not inline_mode:
        typer.echo("Provide either --plan <eval.yaml> or --results + --metric.")
        raise typer.Exit(code=2)

    if plan_mode:
        assert plan is not None  # for type-narrowing
        _evaluate_plan_path(ctx, log, plan, output)
        return

    # Inline DSL path.
    if not metrics:
        typer.echo("--results requires at least one --metric.")
        raise typer.Exit(code=2)
    assert results is not None
    if parameter_sweep is not None:
        _evaluate_parameter_sweep(
            ctx,
            log,
            results=results,
            metric_strs=metrics,
            sweep_spec=parameter_sweep,
            feeder_id=feeder_id,
            bootstrap_n=bootstrap_n,
            bootstrap_seed=bootstrap_seed,
            output=output,
        )
    else:
        if bootstrap_n:
            typer.echo("--bootstrap-n / --bootstrap-seed only apply with --parameter-sweep.")
            raise typer.Exit(code=2)
        _evaluate_inline(ctx, log, results=results, metric_strs=metrics, output=output)


def _evaluate_plan_path(ctx: CLIContext, log: Any, plan: Path, output: Path | None) -> None:
    """Case-B path: drive Evaluator from a YAML plan."""
    try:
        eval_plan = load_evaluation_plan_from_yaml(plan)
    except EvaluationPlanLoadError as exc:
        log.error("evaluation_plan_load_failed", plan=str(plan), message=str(exc))
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    evaluator = Evaluator(result_loader=FilesystemResultLoader())
    try:
        result = evaluator.run(eval_plan)
    except GridflowError as exc:
        log.error(
            "evaluation_failed",
            evaluation_id=eval_plan.evaluation_id,
            error_code=exc.error_code,
            message=exc.message,
        )
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    _write_payload(ctx, output, result.to_dict(), summary=_summary_for_eval_result(result))


def _evaluate_inline(
    ctx: CLIContext,
    log: Any,
    *,
    results: Path,
    metric_strs: list[str],
    output: Path | None,
) -> None:
    """Case-A path: build an EvaluationPlan in-memory from inline DSL flags."""
    try:
        metric_specs = tuple(parse_metric_spec(s) for s in metric_strs)
    except EvaluateDSLError as exc:
        log.error("evaluate_dsl_parse_failed", message=str(exc))
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc

    result_paths = _resolve_inline_result_paths(results)
    eval_plan = EvaluationPlan(
        evaluation_id=f"inline:{results.stem}",
        results=result_paths,
        metrics=metric_specs,
    )
    evaluator = Evaluator(result_loader=FilesystemResultLoader())
    try:
        result = evaluator.run(eval_plan)
    except GridflowError as exc:
        log.error("evaluation_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    _write_payload(ctx, output, result.to_dict(), summary=_summary_for_eval_result(result))


def _evaluate_parameter_sweep(
    ctx: CLIContext,
    log: Any,
    *,
    results: Path,
    metric_strs: list[str],
    sweep_spec: str,
    feeder_id: str,
    bootstrap_n: int,
    bootstrap_seed: int,
    output: Path | None,
) -> None:
    """Case-A + parameter-sweep path: drive SensitivityAnalyzer."""
    if len(metric_strs) != 1:
        typer.echo("--parameter-sweep requires exactly one --metric.")
        raise typer.Exit(code=2)
    try:
        metric_spec = parse_metric_spec(metric_strs[0])
        sweep = parse_parameter_sweep(sweep_spec)
    except EvaluateDSLError as exc:
        typer.echo(str(exc))
        raise typer.Exit(code=2) from exc
    if metric_spec.plugin is None:
        typer.echo("--parameter-sweep requires a metric plugin (built-in metrics take no kwargs).")
        raise typer.Exit(code=2)

    # Load experiments via the same FilesystemResultLoader used elsewhere.
    result_paths = _resolve_inline_result_paths(results)
    loader = FilesystemResultLoader()
    experiments = [loader.load(p) for p in result_paths]

    analyzer = SensitivityAnalyzer()
    try:
        sensitivity = analyzer.analyze(
            experiments=experiments,
            parameter_name=sweep.kwarg_name,
            parameter_grid=sweep.grid(),
            metric_plugin=metric_spec.plugin,
            metric_kwargs_base=dict(metric_spec.kwargs),
            feeder_id=feeder_id,
            bootstrap_n=bootstrap_n,
            bootstrap_seed=bootstrap_seed,
        )
    except GridflowError as exc:
        log.error("sensitivity_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    # Guard against a subtle misjudgment (issue #18/#23): a zero-width CI
    # means every bootstrap resample produced the same mean — the input
    # is effectively a single point or fully deterministic across seeds.
    # Reporting that CI as if it were a real interval invites treating a
    # non-result as a tight, confident one. Warn loudly.
    if bootstrap_n > 0:
        n_experiments = len(experiments)
        degenerate = n_experiments < 2 or any(
            lo == hi for lo, hi in zip(sensitivity.confidence_lower, sensitivity.confidence_upper, strict=True)
        )
        if degenerate:
            warning = (
                f"WARNING: bootstrap CI is zero-width at one or more grid points "
                f"(n_experiments={n_experiments}). This indicates no run-to-run "
                f"variation to resample — the CI is not a meaningful interval. "
                f"Add replicates or vary the seed before reading it as significance."
            )
            log.warning(
                "bootstrap_ci_zero_width",
                feeder_id=sensitivity.feeder_id,
                n_experiments=n_experiments,
            )
            typer.echo(warning, err=True)

    _write_payload(
        ctx,
        output,
        sensitivity.to_dict(),
        summary={
            "feeder_id": sensitivity.feeder_id,
            "parameter_name": sensitivity.parameter_name,
            "n_grid_points": len(sensitivity.parameter_values),
            "metric_name": sensitivity.metric_name,
            "bootstrap_n": bootstrap_n,
        },
    )


def _resolve_inline_result_paths(results: Path) -> tuple[Path, ...]:
    """``--results`` accepts a single JSON, a directory of JSONs, or a SweepResult.

    Mirrors evaluation_yaml_loader semantics so case-A and case-B
    behave identically once the plan is built.
    """
    if results.is_dir():
        return tuple(sorted(results.glob("*.json")))
    if results.suffix == ".json":
        # Could be a SweepResult (has experiment_ids list) or a single
        # ExperimentResult. Discriminate by content.
        data = json.loads(results.read_text(encoding="utf-8"))
        if isinstance(data, dict) and "experiment_ids" in data:
            ids = data["experiment_ids"]
            if not isinstance(ids, list):
                raise typer.BadParameter("SweepResult has malformed experiment_ids")
            paths: list[Path] = []
            for exp_id in ids:
                candidate = results.parent / f"{exp_id}.json"
                if not candidate.exists():
                    raise typer.BadParameter(f"experiment_id '{exp_id}' has no JSON next to {results}")
                paths.append(candidate)
            return tuple(paths)
        return (results,)
    raise typer.BadParameter(f"--results must be a JSON file or a directory, got {results}")


def _summary_for_eval_result(result: Any) -> dict[str, object]:
    """Plain-format summary common to plan-based and inline evaluation."""
    return {
        "evaluation_id": result.evaluation_id,
        "n_experiments": len(result.experiment_ids),
        "elapsed_s": result.elapsed_s,
        "plan_hash": result.plan_hash,
    }


def _write_payload(
    ctx: CLIContext,
    output: Path | None,
    payload: dict[str, object],
    *,
    summary: dict[str, object],
) -> None:
    """Write JSON payload to disk (if --output) and emit summary to stdout."""
    if output is not None:
        output.parent.mkdir(parents=True, exist_ok=True)
        output.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    if ctx.formatter.format is OutputFormat.PLAIN:
        typer.echo(ctx.formatter.render(summary))
    else:
        typer.echo(ctx.formatter.render(payload))


# ---------------------------------------------------------------------- main


def main() -> None:
    """Console-script entry point."""
    app()


if __name__ == "__main__":
    main()
