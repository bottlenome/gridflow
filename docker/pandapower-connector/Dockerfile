# ==============================================================
# pandapower-connector Dockerfile
# Multi-stage build mirroring docker/opendss-connector/Dockerfile.
# pandapower installed via the [pandapower] extra so the lockfile
# stays the single source of truth.
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Resolve and install dependencies (including the pandapower extra) BEFORE
# copying source so layer caching survives source-only edits.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --extra pandapower

# Now bring in the source and install the project non-editable so the
# resulting .venv is fully self-contained when copied into the runtime image.
COPY . .
RUN uv sync --frozen --no-dev --no-editable --extra pandapower

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

# pandapower needs scipy/numpy compiled libs that link against libgomp.
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

# Health check hits the minimal /health endpoint served by the daemon.
# Detailed design 03b §3.5.6 (REST API contract) — same JSON shape as
# opendss-connector but a different port (8001).
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8001/health')" || exit 1

EXPOSE 8001

# Long-running REST daemon entry point. The daemon wraps the in-process
# PandaPowerConnector and exposes the REST contract from 03b §3.5.6.
ENTRYPOINT ["python", "-m", "gridflow.connectors.pandapower"]
