"""Minimal HTTP health endpoint for the ``gridflow-core`` container.

Spec: docs/detailed_design/11_build_deploy.md §11.1.1. The container
HEALTHCHECK queries ``http://localhost:8888/health``; this module provides
the endpoint so the spec can be satisfied from Phase 1 MVP onward, even
though the full Notebook Bridge (IF-07) is not yet implemented.

The server is intentionally the smallest possible thing that satisfies the
detailed-design HEALTHCHECK contract — it is NOT the Notebook Bridge and
exposes no business endpoints. When Notebook Bridge is implemented it will
replace (or extend) this server.
"""

from __future__ import annotations

from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from gridflow.infra.logging import get_logger

HEALTH_BODY = b'{"status":"ok"}'

# 0.0.0.0 is required inside the container so the docker-compose port
# mapping (8888:8888) can reach the service from the host; 127.0.0.1 would
# only be reachable from inside the container itself.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8888


class _HealthHandler(BaseHTTPRequestHandler):
    """Tiny handler that serves only ``GET /health``."""

    def do_GET(self) -> None:  # BaseHTTPRequestHandler API name
        if self.path == "/health":
            self.send_response(200)
            self.send_header("Content-Type", "application/json")
            self.send_header("Content-Length", str(len(HEALTH_BODY)))
            self.end_headers()
            self.wfile.write(HEALTH_BODY)
            return
        self.send_response(404)
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Silence the default BaseHTTPServer stderr logging; structlog
        # handles all gridflow logging centrally. ``format`` is named to
        # match the BaseHTTPRequestHandler override signature.
        del format, args


def build_health_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Build (but do not start) the minimal ``/health`` HTTP server.

    Exposed separately from :func:`run_health_server` so tests can drive the
    lifecycle explicitly (ephemeral port, background thread, shutdown).
    """
    return ThreadingHTTPServer((host, port), _HealthHandler)


def run_health_server(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the ``/health`` server until interrupted.

    Blocks the calling thread — intended to be called from
    :mod:`gridflow.main` as the long-running container entry point.
    """
    log = get_logger("gridflow.infra.health_server")
    server = build_health_server(host, port)
    log.info("health_server_started", host=host, port=port)
    try:
        server.serve_forever()
    except KeyboardInterrupt:
        log.info("health_server_interrupted")
    finally:
        server.server_close()
        log.info("health_server_stopped")
