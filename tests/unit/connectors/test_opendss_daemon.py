"""Tests for the OpenDSS connector REST daemon.

Spec:
    * docs/detailed_design/11_build_deploy.md §11.1.2 — the
      ``opendss-connector`` container runs ``python -m gridflow.connectors.opendss``
      as a long-running daemon that exposes HEALTHCHECK on port 8000 via
      ``GET /health``.
    * docs/detailed_design/03b_usecase_classes.md §3.5.6 — REST API
      endpoints for inter-connector communication:
      ``GET /health`` returns ``HealthStatus`` JSON.

This file drives Unit 1 (minimum viable daemon). Business endpoints
(``/initialize``, ``/execute``, ``/teardown``) are added in Unit 2.
"""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http import HTTPStatus

import pytest

from gridflow.connectors.opendss import build_daemon


@pytest.fixture
def running_daemon() -> Iterator[tuple[str, int]]:
    """Yield the ``(host, port)`` of an opendss-connector daemon on an ephemeral port."""
    daemon = build_daemon(host="127.0.0.1", port=0)
    thread = threading.Thread(target=daemon.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = daemon.server_address[0], daemon.server_address[1]
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port
    finally:
        daemon.shutdown()
        daemon.server_close()
        thread.join(timeout=2)


class TestOpenDSSConnectorDaemonHealth:
    """Unit 1: minimum viable daemon — ``/health`` contract only."""

    def test_health_endpoint_returns_200_healthy_true(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        """Spec 03b §3.5.6: ``GET /health`` returns ``HealthStatus`` JSON.

        HealthStatus schema (03b §3.5.5): ``{"healthy": bool, "message": str}``.
        """
        host, port = running_daemon
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
            assert resp.status == HTTPStatus.OK
            assert resp.headers.get("Content-Type") == "application/json"
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload == {"healthy": True, "message": "opendss-connector ready"}

    def test_unknown_path_returns_404(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        host, port = running_daemon
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/unknown", timeout=2)
        assert exc_info.value.code == HTTPStatus.NOT_FOUND

    def test_health_endpoint_satisfies_dockerfile_healthcheck(
        self,
        running_daemon: tuple[str, int],
    ) -> None:
        """Regression: detailed design 11.1.2 specifies::

            HEALTHCHECK ... CMD python -c "import urllib.request; \\
                urllib.request.urlopen('http://localhost:8000/health')" || exit 1
        """
        host, port = running_daemon
        urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)
