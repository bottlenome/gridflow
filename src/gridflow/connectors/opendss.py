"""OpenDSS connector REST daemon — container entry point.

Spec:
    * docs/detailed_design/11_build_deploy.md §11.1.2
      ENTRYPOINT ``python -m gridflow.connectors.opendss`` starts a
      long-running HTTP server that the ``opendss-connector`` container
      HEALTHCHECK probes on port 8000.
    * docs/detailed_design/03b_usecase_classes.md §3.5.6
      REST API contract — ``GET /health`` returns ``HealthStatus`` JSON.

This module is the thin HTTP shell around the in-process
:class:`gridflow.adapter.connector.opendss.OpenDSSConnector`. Unit 1
ships only the ``/health`` endpoint; the business endpoints
(``/initialize``, ``/execute``, ``/teardown``) are added incrementally.
"""

from __future__ import annotations

import json
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any

from gridflow.infra.logging import get_logger

# 0.0.0.0 is required inside the container so the Docker Compose internal
# network (gridflow-core → opendss-connector:8000) can reach it. 127.0.0.1
# would only be reachable from inside the container itself.
DEFAULT_HOST = "0.0.0.0"
DEFAULT_PORT = 8000  # detailed design §11.1.2 / §11.2

_HEALTH_BODY = json.dumps(
    {"healthy": True, "message": "opendss-connector ready"},
    separators=(",", ":"),
).encode("utf-8")


class _ConnectorHandler(BaseHTTPRequestHandler):
    """Handler covering the REST contract from 03b §3.5.6.

    Unit 1 scope: ``GET /health`` only. Additional endpoints
    (``POST /initialize``, ``POST /execute``, ``POST /teardown``) are
    added in subsequent units while keeping this handler as the single
    dispatch surface.
    """

    def do_GET(self) -> None:  # BaseHTTPRequestHandler API name
        if self.path == "/health":
            self._write_json(200, _HEALTH_BODY)
            return
        self._write_empty(404)

    def _write_json(self, status: int, body: bytes) -> None:
        self.send_response(status)
        self.send_header("Content-Type", "application/json")
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def _write_empty(self, status: int) -> None:
        self.send_response(status)
        self.send_header("Content-Length", "0")
        self.end_headers()

    def log_message(self, format: str, *args: Any) -> None:
        # Silence default BaseHTTPServer stderr logging; structlog
        # handles all gridflow logging centrally.
        del format, args


def build_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> ThreadingHTTPServer:
    """Build (but do not start) the opendss-connector REST daemon.

    Exposed separately from :func:`run_daemon` so tests can drive the
    lifecycle on an ephemeral port without forking a subprocess.
    """
    return ThreadingHTTPServer((host, port), _ConnectorHandler)


def run_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the opendss-connector daemon until interrupted.

    Blocks the calling thread — intended to be invoked from
    ``python -m gridflow.connectors.opendss``.
    """
    log = get_logger("gridflow.connectors.opendss")
    daemon = build_daemon(host, port)
    log.info("opendss_daemon_started", host=host, port=port)
    try:
        daemon.serve_forever()
    except KeyboardInterrupt:
        log.info("opendss_daemon_interrupted")
    finally:
        daemon.server_close()
        log.info("opendss_daemon_stopped")


if __name__ == "__main__":
    from gridflow.infra.logging import configure_logging

    configure_logging(level="INFO")
    run_daemon()
