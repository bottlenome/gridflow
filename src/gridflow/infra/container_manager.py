"""Docker Compose container manager (spec 03d §3.8.3).

``ContainerManager`` is the low-level Docker operation layer used by
:class:`ContainerOrchestratorRunner`. It is responsible for:

    * Starting a set of connector services via ``docker compose up``.
    * Stopping them via ``docker compose stop`` / ``down``.
    * Probing individual service health.

Being a Protocol makes it trivial to swap for a fake in unit tests
(the tests in ``tests/unit/infra/test_container_runner.py`` use a
no-op fake because real Docker is unavailable in CI).

The concrete :class:`DockerComposeContainerManager` shells out to
``docker compose``. The subprocess runner is injected so tests can
exercise the logic without actually touching Docker.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from dataclasses import dataclass
from pathlib import Path
from typing import Protocol, runtime_checkable

from gridflow.domain.error import (
    ContainerStartError,
    ContainerStopError,
    ServiceNotFoundError,
)
from gridflow.usecase.interfaces import HealthStatus


@dataclass(frozen=True)
class ContainerEndpoint:
    """Connector addressing metadata for :class:`ContainerOrchestratorRunner`.

    Attributes:
        connector_id: UseCase-level connector identifier
            (e.g. ``"opendss"``). Matches ``ExecutionPlan.connectors``.
        service_name: Docker Compose service name (e.g. ``"opendss-connector"``)
            passed to :class:`ContainerManager`.
        base_url: REST root URL that speaks the 03b §3.5.6 contract
            (e.g. ``"http://opendss-connector:8000"``).
    """

    connector_id: str
    service_name: str
    base_url: str


@runtime_checkable
class ContainerManager(Protocol):
    """Low-level Docker-service lifecycle operations (spec 03d §3.8.3).

    Error contract:
        * ``start()`` raises ``ContainerStartError`` on failure.
        * ``stop()`` raises ``ContainerStopError`` on failure.
        * ``health_check()`` raises ``ServiceNotFoundError`` when the
          service is unknown to the backend (vs. returning an unhealthy
          ``HealthStatus`` which means "known but not healthy").
    """

    def start(self, services: tuple[str, ...]) -> None:
        """Bring up the named services and wait until they are running."""
        ...

    def stop(self, services: tuple[str, ...]) -> None:
        """Stop the named services (best-effort at the caller level)."""
        ...

    def health_check(self, service: str) -> HealthStatus:
        """Report the current health of a single service."""
        ...


# ----------------------------------------------------------------- concrete


SubprocessRunner = Callable[..., "subprocess.CompletedProcess[str]"]


def _default_subprocess_runner(
    *args: object,
    **kwargs: object,
) -> subprocess.CompletedProcess[str]:
    return subprocess.run(*args, **kwargs)  # type: ignore[call-overload,no-any-return]


class DockerComposeContainerManager:
    """Real ``ContainerManager`` shelling out to ``docker compose``.

    The subprocess runner is injected so unit tests can simulate docker
    without a real engine. In production the default ``subprocess.run``
    is used.

    Attributes:
        compose_file: Path to the ``docker-compose.yml`` file.
        project_name: Optional ``docker compose -p <name>`` project name.
        run_subprocess: Injected subprocess runner (defaults to
            :func:`subprocess.run`).
    """

    def __init__(
        self,
        compose_file: Path,
        *,
        project_name: str | None = None,
        run_subprocess: SubprocessRunner | None = None,
    ) -> None:
        self._compose_file = compose_file
        self._project_name = project_name
        self._run = run_subprocess or _default_subprocess_runner

    def _base_cmd(self) -> list[str]:
        cmd = ["docker", "compose", "-f", str(self._compose_file)]
        if self._project_name is not None:
            cmd.extend(["-p", self._project_name])
        return cmd

    def start(self, services: tuple[str, ...]) -> None:
        cmd = [*self._base_cmd(), "up", "-d", *services]
        try:
            result = self._run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:  # docker binary not found, etc.
            raise ContainerStartError(
                f"failed to invoke docker compose: {exc}",
                context={"services": services},
                cause=exc,
            ) from exc
        if result.returncode != 0:
            raise ContainerStartError(
                f"docker compose up failed (exit={result.returncode})",
                context={
                    "services": services,
                    "stderr": (result.stderr or "").strip(),
                },
            )

    def stop(self, services: tuple[str, ...]) -> None:
        cmd = [*self._base_cmd(), "stop", *services]
        try:
            result = self._run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise ContainerStopError(
                f"failed to invoke docker compose: {exc}",
                context={"services": services},
                cause=exc,
            ) from exc
        if result.returncode != 0:
            raise ContainerStopError(
                f"docker compose stop failed (exit={result.returncode})",
                context={
                    "services": services,
                    "stderr": (result.stderr or "").strip(),
                },
            )

    def health_check(self, service: str) -> HealthStatus:
        cmd = [
            *self._base_cmd(),
            "ps",
            "--format",
            "json",
            service,
        ]
        try:
            result = self._run(cmd, capture_output=True, text=True, check=False)
        except OSError as exc:
            raise ServiceNotFoundError(
                f"failed to invoke docker compose: {exc}",
                context={"service": service},
                cause=exc,
            ) from exc
        if result.returncode != 0:
            raise ServiceNotFoundError(
                f"service '{service}' not found (exit={result.returncode})",
                context={
                    "service": service,
                    "stderr": (result.stderr or "").strip(),
                },
            )
        stdout = (result.stdout or "").strip()
        if not stdout:
            return HealthStatus(healthy=False, message=f"service '{service}' is not running")
        # docker compose ps --format json returns per-service JSON; we
        # only need a coarse "running vs not" signal here. A missing
        # health state means the container lacks a HEALTHCHECK directive,
        # in which case "running" is good enough for MVP.
        return HealthStatus(
            healthy="running" in stdout.lower() or "healthy" in stdout.lower(),
            message=stdout.splitlines()[0] if stdout else "",
        )
