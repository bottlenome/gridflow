# ==============================================================
# opendss-connector Dockerfile
# Multi-stage build: builder -> runtime
# OpenDSSDirect.py installed via the [opendss] extra so the lockfile
# stays the single source of truth.
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Resolve and install dependencies (including the opendss extra) BEFORE
# copying source so layer caching survives source-only edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --extra opendss

# Now bring in the source and install the project non-editable so the
# resulting .venv is fully self-contained when copied into the runtime
# image. (The default editable install would leave a .pth file pointing
# at /build/src, which does not exist in the runtime stage.)
COPY . .
RUN uv sync --frozen --no-dev --no-editable --extra opendss

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

RUN apt-get update && \
    apt-get install -y --no-install-recommends libgomp1 && \
    apt-get purge -y --auto-remove && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

RUN groupadd -g 1000 gridflow && \
    useradd -u 1000 -g gridflow -m -s /bin/bash gridflow

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv

ENV PATH="/app/.venv/bin:$PATH"

USER gridflow

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import opendssdirect" || exit 1

# The opendss-connector image ships OpenDSS + the gridflow package so the
# same entrypoint works as the main CLI — Phase 1 MVP uses in-process
# execution (see infra.orchestrator.InProcessOrchestratorRunner).
ENTRYPOINT ["python", "-m", "gridflow"]
