# ==============================================================
# gridflow-core Dockerfile
# Multi-stage build: builder -> runtime
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

# pandapower (and its scipy / numpy transitive deps) need build-essential to
# compile native wheels when no manylinux wheel is available for the target
# architecture (notably ARM64).
RUN apt-get update && \
    apt-get install -y --no-install-recommends build-essential && \
    rm -rf /var/lib/apt/lists/*

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependency closure first so dependency layers cache independently
# of source-only changes. The pandapower extra is installed at this layer
# so the gridflow-core container can drive the in-process pandapower
# connector path (Phase 2 §5.1.3 cross-solver support).
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable --extra pandapower

# Now copy the source tree and install the project itself non-editable so
# the .venv stays self-contained when copied into the runtime image (the
# default editable install would leave a .pth file pointing at /build/src,
# which doesn't exist in the runtime stage).
COPY . .
RUN uv sync --frozen --no-dev --no-editable --extra pandapower

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

# pandapower needs scipy / numpy compiled libs that link against libgomp.
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

# Health check hitting the minimal /health endpoint served by
# ``gridflow.main``. Detailed design §11.1.1 specifies this exact form.
HEALTHCHECK --interval=30s --timeout=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8888/health')" || exit 1

EXPOSE 8888

# Long-running container entry point (detailed design §11.1.1). Starts the
# /health HTTP server and blocks. CLI subcommands are invoked separately via
# ``docker compose exec gridflow-core gridflow ...`` which goes through the
# ``gridflow`` console script (see pyproject.toml [project.scripts]).
ENTRYPOINT ["python", "-m", "gridflow.main"]
