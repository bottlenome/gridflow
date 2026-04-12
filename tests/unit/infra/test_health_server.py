"""Tests for the minimal ``/health`` HTTP server (spec: 11_build_deploy §11.1.1)."""

from __future__ import annotations

import json
import threading
import urllib.error
import urllib.request
from collections.abc import Iterator
from http import HTTPStatus

import pytest

from gridflow.infra.health_server import build_health_server


@pytest.fixture
def running_health_server() -> Iterator[tuple[str, int]]:
    """Yield the (host, port) of a health server running on an ephemeral port."""
    server = build_health_server(host="127.0.0.1", port=0)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        host, port = server.server_address[0], server.server_address[1]
        assert isinstance(host, str)
        assert isinstance(port, int)
        yield host, port
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=2)


class TestHealthServer:
    def test_health_endpoint_returns_ok_json(
        self,
        running_health_server: tuple[str, int],
    ) -> None:
        host, port = running_health_server
        with urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2) as resp:
            assert resp.status == HTTPStatus.OK
            assert resp.headers.get("Content-Type") == "application/json"
            payload = json.loads(resp.read().decode("utf-8"))
        assert payload == {"status": "ok"}

    def test_unknown_path_returns_404(
        self,
        running_health_server: tuple[str, int],
    ) -> None:
        host, port = running_health_server
        with pytest.raises(urllib.error.HTTPError) as exc_info:
            urllib.request.urlopen(f"http://{host}:{port}/unknown", timeout=2)
        assert exc_info.value.code == HTTPStatus.NOT_FOUND

    def test_health_endpoint_satisfies_dockerfile_healthcheck(
        self,
        running_health_server: tuple[str, int],
    ) -> None:
        """Regression: the Dockerfile HEALTHCHECK uses ``urlopen`` exactly.

        Detailed design 11.1.1 specifies::

            HEALTHCHECK ... CMD python -c "import urllib.request; \\
                urllib.request.urlopen('http://localhost:8888/health')" || exit 1

        This test runs the same call shape to guarantee the server is
        reachable via the exact form the spec mandates.
        """
        host, port = running_health_server
        # No exception == healthcheck success (exit 0 equivalent).
        urllib.request.urlopen(f"http://{host}:{port}/health", timeout=2)
