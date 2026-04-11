"""OpenDSS connector REST daemon — container entry point.

Spec:
    * docs/detailed_design/11_build_deploy.md §11.1.2
      ENTRYPOINT ``python -m gridflow.connectors.opendss`` starts a
      long-running HTTP server that the ``opendss-connector`` container
      HEALTHCHECK probes on port 8000.
    * docs/detailed_design/03b_usecase_classes.md §3.5.6
      REST API contract — implemented by :mod:`gridflow.connectors._daemon_base`.

This module is a thin shim:
    * declares the OpenDSS-specific port + health string,
    * provides a default factory that builds an
      :class:`OpenDSSConnector`,
    * exposes :func:`build_daemon` / :func:`run_daemon` for tests and
      the container ``__main__`` block.

All REST contract logic (state machine, error mapping, JSON schema)
lives in :mod:`gridflow.connectors._daemon_base` and is shared with the
sibling :mod:`gridflow.connectors.pandapower` daemon so the two are
structurally identical.
"""

from __future__ import annotations

from collections.abc import Callable
from http.server import ThreadingHTTPServer

from gridflow.connectors._daemon_base import (
    DEFAULT_HOST,
    build_daemon_base,
    run_daemon_loop,
)
from gridflow.domain.scenario.registry import ScenarioRegistry
from gridflow.usecase.interfaces import ConnectorInterface

DEFAULT_PORT = 8000  # detailed design §11.1.2 / §11.2
HEALTH_MESSAGE = "opendss-connector ready"


def _default_connector_factory() -> ConnectorInterface:
    from gridflow.adapter.connector import OpenDSSConnector

    return OpenDSSConnector()


def build_daemon(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    registry: ScenarioRegistry | None = None,
    connector_factory: Callable[[], ConnectorInterface] | None = None,
) -> ThreadingHTTPServer:
    """Build (but do not start) the opendss-connector REST daemon."""
    return build_daemon_base(
        host,
        port,
        health_message=HEALTH_MESSAGE,
        connector_factory=connector_factory or _default_connector_factory,
        registry=registry,
    )


def run_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the opendss-connector daemon until interrupted.

    Blocks the calling thread — intended to be invoked from
    ``python -m gridflow.connectors.opendss``.
    """
    daemon = build_daemon(host, port)
    run_daemon_loop(daemon, log_name="gridflow.connectors.opendss", host=host, port=port)


if __name__ == "__main__":
    from gridflow.infra.logging import configure_logging

    configure_logging(level="INFO")
    run_daemon()
