# gridflow

Grid simulation and power flow analysis framework. Phase 1 MVP: register a
Scenario Pack, run an OpenDSS experiment, benchmark the result.

## Runtime environment

gridflow の**エンドユーザー向け配布標準は Docker Compose** です
（アーキテクチャ ADR-002、制約 CON-2）。再現性 (QA-3) と移植性 (QA-7) を
保証できるのは Docker 経由の実行のみです。ネイティブ（ローカル）インストール
は OS 差分で再現性が崩れるため、エンドユーザー向け実行環境としては
採用していません。

ローカル環境は **gridflow 自身の開発・テスト用** に限り許容されます
（アーキテクチャ M-3 の例外条項）。研究成果の再現性を保証したい場面では
必ず Docker を使ってください。

## Requirements

- Docker Desktop 4.x+ / Docker Engine 24+ + Docker Compose v2 以降

## Quick start (Docker)

```bash
# 1. Build and start both containers
docker compose up --build -d

# 2. Register a sample Scenario Pack
docker compose exec gridflow-core gridflow scenario register /app/examples/ieee13/pack.yaml

# 3. Run a 2-step power flow
docker compose exec gridflow-core gridflow run ieee13@1.0.0 --steps 2 --format json

# 4. Inspect the saved result
docker compose exec gridflow-core gridflow results <experiment_id> --format json
```

結果は `gridflow-home` ボリューム上の `~/.gridflow/results/<experiment_id>.json`
に保存されます。`GRIDFLOW_HOME` 環境変数でルートディレクトリを上書きできます。

### 開発者向けオーバーレイ

ソースをホットマウントして開発する場合:

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

## For contributors (local development)

**This section is for gridflow maintainers only.** End users should use
Docker (above). Local execution is permitted only for developing / testing
gridflow itself, and does not guarantee bit-level reproducibility with the
Docker runtime.

Requirements for local development:

- Python 3.11+
- [uv](https://docs.astral.sh/uv/)

```bash
# Install dependencies (dev + OpenDSS extras)
uv sync --frozen --dev --extra opendss

# Run the test suite
uv run pytest -m "not spike"   # unit + e2e (no OpenDSS interaction)
uv run pytest                   # include OpenDSS smoke + integration

# Static analysis
uv run ruff check src/ tests/
uv run ruff format --check src/ tests/
uv run mypy --strict src/
```

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
