# ==============================================================
# gridflow-core Dockerfile
# Multi-stage build: builder -> runtime
# ==============================================================

# ---- builder stage ----
FROM python:3.11-slim AS builder

WORKDIR /build

COPY --from=ghcr.io/astral-sh/uv:latest /uv /usr/local/bin/uv

# Install dependency closure first so dependency layers cache independently
# of source-only changes.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project --no-editable

# Now copy the source tree and install the project itself non-editable so
# the .venv stays self-contained when copied into the runtime image (the
# default editable install would leave a .pth file pointing at /build/src,
# which doesn't exist in the runtime stage).
COPY . .
RUN uv sync --frozen --no-dev --no-editable

# ---- runtime stage ----
FROM python:3.11-slim AS runtime

RUN groupadd -g 1000 gridflow && \
    useradd -u 1000 -g gridflow -m -s /bin/bash gridflow

RUN apt-get purge -y --auto-remove && \
    rm -rf /var/lib/apt/lists/* /tmp/* /root/.cache

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
