"""Long-running container entry point for the ``gridflow-core`` image.

Targeted by the detailed-design ENTRYPOINT directive
(docs/detailed_design/11_build_deploy.md §11.1.1):

    ENTRYPOINT ["python", "-m", "gridflow.main"]

This module is distinct from :mod:`gridflow.__main__` (``python -m
gridflow``) which launches the one-shot CLI. Separating them lets the
container hold a long-running health endpoint while operators still invoke
CLI subcommands via ``docker compose exec`` in independent processes.

Phase 1 MVP responsibility: start the minimal ``/health`` HTTP server on
port 8888 (per §11.1.1 HEALTHCHECK contract) and keep the container alive.
When Notebook Bridge (IF-07) is implemented it will replace or extend this
entry point.
"""

from __future__ import annotations

from gridflow.infra.health_server import run_health_server
from gridflow.infra.logging import configure_logging


def main() -> None:
    """Container daemon entry point."""
    configure_logging(level="INFO")
    run_health_server()


if __name__ == "__main__":
    main()
