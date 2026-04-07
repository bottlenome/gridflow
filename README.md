# gridflow

Grid simulation and power flow analysis framework. Phase 1 MVP: register a
Scenario Pack, run an OpenDSS experiment, benchmark the result.

## Requirements

- Python 3.11+
- [uv](https://docs.astral.sh/uv/) for dependency management
- Docker (optional, for containerised runs)

## Quick start (local, no Docker)

```bash
# 1. Install dependencies (dev + OpenDSS extras)
uv sync --frozen --dev --extra opendss

# 2. Register a sample Scenario Pack
uv run gridflow scenario register examples/ieee13/pack.yaml

# 3. Run a 2-step power flow
uv run gridflow run ieee13@1.0.0 --steps 2 --format json

# 4. Inspect the saved result
uv run gridflow results <experiment_id> --format json
```

The result goes to `~/.gridflow/results/<experiment_id>.json`. Set
`GRIDFLOW_HOME` to override the root directory.

## Quick start (Docker)

```bash
docker compose up --build
```

The `gridflow-core` container exposes port `8888`. Use the developer overlay
for live-mounted source:

```bash
docker compose -f docker-compose.yml -f docker-compose.dev.yml up
```

## CLI commands (MVP)

| Command | Purpose |
|---|---|
| `gridflow scenario register <pack.yaml>` | Register a Scenario Pack |
| `gridflow scenario list` | List registered packs |
| `gridflow scenario get <pack_id>` | Show a single pack |
| `gridflow run <pack_id> [--steps N]` | Execute an experiment |
| `gridflow results <experiment_id>` | Print a saved experiment result |
| `gridflow benchmark --baseline <id> --candidate <id>` | Compare two runs |

All commands accept `--format plain|json|table`.

## Repository layout

```
src/gridflow/
  domain/      # Pure, dependency-free entities and Protocols
    cdl/       # Common Data Language value objects
    scenario/  # ScenarioPack + ScenarioRegistry Protocol
    result/    # Time-series result value objects
    util/      # Shared helpers (params tuple convention)
    error.py   # Full GridflowError hierarchy (E-10xxx..E-40xxx)
  usecase/     # Application workflows (Orchestrator, StepResult…)
  adapter/     # CLI, connectors, benchmark harness
  infra/       # FileScenarioRegistry, ConfigManager, structured logging
tests/
  unit/        # Layer-scoped unit tests (121 cases)
  e2e/         # CLI-level end-to-end pipeline + reproducibility
  spike/       # OpenDSS smoke tests (gated behind the `spike` marker)
examples/
  ieee13/      # IEEE 13-node feeder pack + DSS network
  minimal_feeder/  # Tiny 2-bus pack used by the repro E2E test
docs/          # Architecture, basic design, detailed design, review records
```

## Design principles

See `CLAUDE.md` §0 — in short: frozen dataclasses, hashable value objects,
no exceptions to the immutability rule. Every ``parameters``-style attribute
uses the sorted ``tuple[tuple[str, object], ...]`` convention from
``gridflow.domain.util.params``.

## Testing

```bash
# Unit + e2e (no OpenDSS required)
uv run pytest -m "not spike"

# Include OpenDSS smoke + integration tests
uv run pytest
```

Static analysis:

```bash
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy --strict src/
```
