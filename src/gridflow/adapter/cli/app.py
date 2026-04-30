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
from gridflow.domain.error import (
    ConfigError,
    ExperimentNotFoundError,
    GridflowError,
    PackNotFoundError,
)
from gridflow.domain.scenario.registry import ScenarioRegistry
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
    SweepOrchestrator,
    build_default_aggregator_registry,
)
from gridflow.usecase.sweep_yaml_loader import load_sweep_plan_bundle_from_yaml

app = typer.Typer(
    name="gridflow",
    add_completion=False,
    help="Grid simulation and benchmarking CLI.",
    no_args_is_help=True,
)

scenario_app = typer.Typer(help="Manage Scenario Packs.", no_args_is_help=True)
app.add_typer(scenario_app, name="scenario")


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
_BENCH_BASE_OPT = typer.Option(..., "--baseline", help="Baseline experiment_id")
_BENCH_CAND_OPT = typer.Option(..., "--candidate", help="Candidate experiment_id")
_BENCH_OUTPUT_OPT = typer.Option(None, "--output", help="Write JSON report to path")
_BENCH_FMT_OPT = typer.Option("plain", "--format", help="plain|json|table")
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
        steps.append(
            StepResult(
                step_id=int(s["step_id"]),
                timestamp=datetime.fromisoformat(s["timestamp"]),
                status=StepStatus(s["status"]),
                elapsed_ms=float(s.get("elapsed_ms", 0.0)),
                node_result=nr,
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
    baseline: str = _BENCH_BASE_OPT,
    candidate: str = _BENCH_CAND_OPT,
    output: Path | None = _BENCH_OUTPUT_OPT,
    fmt: str = _BENCH_FMT_OPT,
) -> None:
    """Compare two saved experiments via the benchmark harness."""
    ctx = _build_context(fmt=OutputFormat(fmt))
    base = _load_result(ctx, baseline)
    cand = _load_result(ctx, candidate)
    report = ctx.harness.compare(base, cand)
    if output is not None:
        ctx.report_gen.write_comparison(report, output)
    if ctx.formatter.format is OutputFormat.PLAIN:
        typer.echo(ctx.report_gen.render_comparison_text(report))
    else:
        typer.echo(ctx.formatter.render(report.to_dict()))


@app.command("sweep")
def sweep_command(
    plan: Path = _SWEEP_PLAN_OPT,
    connector: str = _SWEEP_CONNECTOR_OPT,
    output: Path | None = _SWEEP_OUTPUT_OPT,
    fmt: str = _SWEEP_FMT_OPT,
    metric_plugins: list[str] | None = _SWEEP_METRIC_PLUGIN_OPT,
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
    )
    try:
        result = sweep_orchestrator.run(sweep_plan)
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
            output=output,
        )
    else:
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
        )
    except GridflowError as exc:
        log.error("sensitivity_failed", error_code=exc.error_code, message=exc.message)
        typer.echo(str(exc))
        raise typer.Exit(code=1) from exc

    _write_payload(
        ctx,
        output,
        sensitivity.to_dict(),
        summary={
            "feeder_id": sensitivity.feeder_id,
            "parameter_name": sensitivity.parameter_name,
            "n_grid_points": len(sensitivity.parameter_values),
            "metric_name": sensitivity.metric_name,
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
