"""Tests for ``DockerComposeContainerManager`` (spec 03d §3.8.3).

Docker itself is not available in CI so we inject a fake subprocess
runner and assert on the command lines that would be executed. This
covers the construction of ``docker compose`` invocations, error
translation, and the ``start`` / ``stop`` / ``health_check`` contract.
"""

from __future__ import annotations

import subprocess
from collections.abc import Callable
from pathlib import Path
from typing import Any

import pytest

from gridflow.domain.error import (
    ContainerStartError,
    ContainerStopError,
    ServiceNotFoundError,
)
from gridflow.infra.container_manager import (
    DockerComposeContainerManager,
    NoOpContainerManager,
)


def _fake_runner(
    *,
    returncode: int = 0,
    stdout: str = "",
    stderr: str = "",
    capture: list[list[str]] | None = None,
    raise_os_error: OSError | None = None,
) -> Callable[..., subprocess.CompletedProcess[str]]:
    def _run(*args: Any, **kwargs: Any) -> subprocess.CompletedProcess[str]:
        if raise_os_error is not None:
            raise raise_os_error
        cmd = args[0] if args else kwargs.get("args")
        if capture is not None:
            capture.append(list(cmd))
        return subprocess.CompletedProcess(args=cmd, returncode=returncode, stdout=stdout, stderr=stderr)

    return _run


class TestDockerComposeContainerManagerStart:
    def test_start_invokes_docker_compose_up(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        calls: list[list[str]] = []
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(capture=calls),
        )
        manager.start(("opendss-connector",))
        assert calls == [
            [
                "docker",
                "compose",
                "-f",
                str(compose),
                "up",
                "-d",
                "opendss-connector",
            ]
        ]

    def test_start_with_project_name(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        calls: list[list[str]] = []
        manager = DockerComposeContainerManager(
            compose,
            project_name="gridflow-test",
            run_subprocess=_fake_runner(capture=calls),
        )
        manager.start(("a", "b"))
        assert calls[0] == [
            "docker",
            "compose",
            "-f",
            str(compose),
            "-p",
            "gridflow-test",
            "up",
            "-d",
            "a",
            "b",
        ]

    def test_start_nonzero_exit_raises_container_start_error(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(returncode=1, stderr="boom"),
        )
        with pytest.raises(ContainerStartError) as exc_info:
            manager.start(("opendss-connector",))
        assert exc_info.value.error_code == "E-40008"

    def test_start_missing_docker_binary_raises(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(raise_os_error=FileNotFoundError("docker not found")),
        )
        with pytest.raises(ContainerStartError):
            manager.start(("opendss-connector",))


class TestDockerComposeContainerManagerStop:
    def test_stop_invokes_docker_compose_stop(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        calls: list[list[str]] = []
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(capture=calls),
        )
        manager.stop(("opendss-connector",))
        assert calls[0][-2:] == ["stop", "opendss-connector"]

    def test_stop_nonzero_exit_raises(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(returncode=2, stderr="nope"),
        )
        with pytest.raises(ContainerStopError) as exc_info:
            manager.stop(("x",))
        assert exc_info.value.error_code == "E-40009"


class TestDockerComposeContainerManagerHealth:
    def test_health_check_running_service_returns_healthy(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(
                returncode=0,
                stdout='{"State":"running","Name":"opendss-connector"}',
            ),
        )
        status = manager.health_check("opendss-connector")
        assert status.healthy is True

    def test_health_check_empty_stdout_means_not_running(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(returncode=0, stdout=""),
        )
        status = manager.health_check("x")
        assert status.healthy is False

    def test_health_check_nonzero_exit_raises_service_not_found(self, tmp_path: Path) -> None:
        compose = tmp_path / "docker-compose.yml"
        compose.write_text("services: {}", encoding="utf-8")
        manager = DockerComposeContainerManager(
            compose,
            run_subprocess=_fake_runner(returncode=1, stderr="no such service"),
        )
        with pytest.raises(ServiceNotFoundError) as exc_info:
            manager.health_check("ghost")
        assert exc_info.value.error_code == "E-40010"


class TestNoOpContainerManager:
    """Smoke tests for the no-op manager used by the in-container CLI."""

    def test_start_and_stop_are_noops(self) -> None:
        manager = NoOpContainerManager()
        # Must not raise and must not depend on Docker.
        manager.start(("opendss-connector",))
        manager.stop(("opendss-connector",))

    def test_health_check_always_healthy(self) -> None:
        manager = NoOpContainerManager()
        status = manager.health_check("any-service")
        assert status.healthy is True
        assert "any-service" in status.message
