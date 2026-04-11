"""Connector container daemons.

This package hosts the long-running REST daemon entry points that wrap
individual simulators (OpenDSS, pandapower, HELICS, …). They are launched
by the dedicated connector Docker images (detailed design §11.1.2) via
``python -m gridflow.connectors.<name>`` and expose the REST contract
defined in 03b §3.5.6.

Relationship to ``gridflow.adapter.connector``:
    * ``adapter/connector/opendss.py`` — in-process ``ConnectorInterface``
      implementation (business logic that calls OpenDSSDirect.py).
    * ``connectors/opendss.py`` — REST daemon that wraps the above and
      exposes it over HTTP for the ``ContainerOrchestratorRunner``.

Splitting them lets the same business logic run in two execution modes
(in-process for local dev / tests, REST for Docker Compose production)
without duplication.
"""
