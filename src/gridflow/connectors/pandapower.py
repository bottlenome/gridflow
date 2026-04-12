"""pandapower connector REST daemon — container entry point.

Spec:
    * docs/phase1_result.md §7.13.1 (機能 B) — pandapower as second
      connector for cross-solver MVP scenarios.
    * docs/detailed_design/03b_usecase_classes.md §3.5.6 — REST API
      contract (implemented by :mod:`gridflow.connectors._daemon_base`).

Structurally identical to :mod:`gridflow.connectors.opendss`: the only
difference is which underlying ``ConnectorInterface`` adapter is built.
The shared base in :mod:`_daemon_base` owns the entire REST contract.

Default port is 8001 (one above OpenDSS) so both daemons can coexist
inside a single ``docker-compose`` stack without port collisions.
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

DEFAULT_PORT = 8001  # +1 vs opendss-connector to coexist in compose
HEALTH_MESSAGE = "pandapower-connector ready"


def _default_connector_factory() -> ConnectorInterface:
    from gridflow.adapter.connector.pandapower import PandaPowerConnector

    return PandaPowerConnector()


def build_daemon(
    host: str = DEFAULT_HOST,
    port: int = DEFAULT_PORT,
    *,
    registry: ScenarioRegistry | None = None,
    connector_factory: Callable[[], ConnectorInterface] | None = None,
) -> ThreadingHTTPServer:
    """Build (but do not start) the pandapower-connector REST daemon."""
    return build_daemon_base(
        host,
        port,
        health_message=HEALTH_MESSAGE,
        connector_factory=connector_factory or _default_connector_factory,
        registry=registry,
    )


def run_daemon(host: str = DEFAULT_HOST, port: int = DEFAULT_PORT) -> None:
    """Run the pandapower-connector daemon until interrupted.

    Blocks the calling thread — intended to be invoked from
    ``python -m gridflow.connectors.pandapower``.
    """
    daemon = build_daemon(host, port)
    run_daemon_loop(daemon, log_name="gridflow.connectors.pandapower", host=host, port=port)


if __name__ == "__main__":
    from gridflow.infra.logging import configure_logging

    configure_logging(level="INFO")
    run_daemon()
