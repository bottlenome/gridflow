# ==============================================================
# opendss-connector Dockerfile
# Multi-stage build: builder -> runtime
# OpenDSSDirect.py included
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

RUN uv pip install OpenDSSDirect.py

COPY . .
RUN uv sync --frozen --no-dev

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
COPY --from=builder /build/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

USER gridflow

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import opendssdirect" || exit 1

ENTRYPOINT ["python", "-m", "gridflow.connectors.opendss"]
