# ==============================================================
# gridflow-core Dockerfile
# Multi-stage build: builder -> runtime
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY . .
RUN uv sync --frozen --no-dev

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

RUN groupadd -g 1000 gridflow && \
    useradd -u 1000 -g gridflow -m -s /bin/bash gridflow

RUN apt-get purge -y --auto-remove && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

WORKDIR /app

COPY --from=builder /build/.venv /app/.venv
COPY --from=builder /build/src /app/src

ENV PATH="/app/.venv/bin:$PATH"

USER gridflow

HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import gridflow" || exit 1

ENTRYPOINT ["python", "-m", "gridflow"]
