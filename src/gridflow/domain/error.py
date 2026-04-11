"""GridflowError base exception hierarchy.

Error code scheme (per DD-ERR-001, section 8.2):
    E-10xxx: Domain layer errors
    E-20xxx: Use Case layer errors
    E-30xxx: Adapter layer errors
    E-40xxx: Infrastructure layer errors
"""

from __future__ import annotations

from collections.abc import Iterable, Mapping

from gridflow.domain.util.params import Params, as_params, params_to_dict


class GridflowError(Exception):
    """Base exception for all gridflow errors.

    The ``context`` attribute follows the project-wide immutable params
    convention (CLAUDE.md §0.3): internally stored as a sorted
    ``tuple[tuple[str, object], ...]``. Callers may pass a mapping or an
    iterable of pairs for convenience and the tuple is constructed via
    :func:`gridflow.domain.util.params.as_params`.

    Attributes:
        error_code: Error code string (e.g. "E-10001").
        message: Human-readable error message.
        context: Additional context information as an immutable params tuple.
        cause: Original exception for chaining (traceback preservation).
    """

    error_code: str = "E-00000"

    def __init__(
        self,
        message: str,
        *,
        context: Mapping[str, object] | Iterable[tuple[str, object]] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.context: Params = as_params(context)
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> dict[str, object]:
        """Serialize to dict for logging / API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": params_to_dict(self.context),
        }

    def __str__(self) -> str:
        return f"[{self.error_code}] {self.message}"


# === Domain layer errors (E-10xxx) ===


class DomainError(GridflowError):
    """Base for domain layer errors."""

    error_code = "E-10000"


class ScenarioPackError(DomainError):
    """Scenario Pack schema / hash / version errors."""

    error_code = "E-10001"


class PackNotFoundError(ScenarioPackError):
    """Specified pack_id does not exist in the registry."""

    error_code = "E-10002"


class PackValidationError(ScenarioPackError):
    """Scenario Pack validation failure."""

    error_code = "E-10003"


class CDLValidationError(DomainError):
    """CDL entity validation failure."""

    error_code = "E-10004"


class MetricCalculationError(DomainError):
    """Metric calculation anomaly."""

    error_code = "E-10005"


# === Use Case layer errors (E-20xxx) ===


class UseCaseError(GridflowError):
    """Base for use case layer errors."""

    error_code = "E-20000"


class SimulationError(UseCaseError):
    """Simulation execution failure."""

    error_code = "E-20001"


class BenchmarkError(UseCaseError):
    """Benchmark comparison failure."""

    error_code = "E-20002"


class ExperimentNotFoundError(UseCaseError):
    """Experiment not found."""

    error_code = "E-20003"


# === Adapter layer errors (E-30xxx) ===


class AdapterError(GridflowError):
    """Base for adapter layer errors."""

    error_code = "E-30000"


class ConnectorError(AdapterError):
    """Connector operation failure."""

    error_code = "E-30001"


class OpenDSSError(ConnectorError):
    """OpenDSS-specific execution error."""

    error_code = "E-30002"


class CLIError(AdapterError):
    """CLI parse / execution error."""

    error_code = "E-30003"


class PluginError(AdapterError):
    """Plugin load / execution error."""

    error_code = "E-30004"


class UnsupportedFormatError(AdapterError):
    """Unsupported export format."""

    error_code = "E-30005"


class ConnectorStateError(ConnectorError):
    """REST API call is invalid for the current connector session state.

    Raised when the caller violates the session lifecycle defined in
    detailed design 03b §3.5.6, e.g. ``/execute`` before ``/initialize``
    (``UNINITIALIZED`` state) or ``/initialize`` while a session is
    already ``READY`` (session collision).
    """

    error_code = "E-30006"


class ConnectorRequestError(ConnectorError):
    """REST API request body is malformed.

    Covers JSON parse failure, missing required fields, wrong types, and
    other client-side schema violations per detailed design 03b §3.5.6.
    """

    error_code = "E-30007"


# === Infrastructure layer errors (E-40xxx) ===


class InfraError(GridflowError):
    """Base for infrastructure layer errors."""

    error_code = "E-40000"


class OrchestratorError(InfraError):
    """Orchestrator workflow failure."""

    error_code = "E-40001"


class ContainerError(InfraError):
    """Docker container operation failure."""

    error_code = "E-40002"


class RegistryError(InfraError):
    """Registry operation failure."""

    error_code = "E-40003"


class ConfigError(InfraError):
    """Configuration error."""

    error_code = "E-40004"


class RunnerStartError(InfraError):
    """``OrchestratorRunner.prepare()`` failure (spec 03d §3.8.2).

    Raised when the runner cannot bring up its execution backend — e.g.
    a required Docker service fails to become healthy within the
    configured timeout, or an in-process connector factory raises during
    instantiation.
    """

    error_code = "E-40005"


class ConnectorCommunicationError(InfraError):
    """Runner ↔ Connector communication failure (spec 03d §3.8.2).

    Raised by ``ContainerOrchestratorRunner.run_connector()`` when a REST
    call to the connector daemon fails (timeout, connection refused,
    unexpected HTTP status not already represented by a more specific
    error).
    """

    error_code = "E-40006"


class ConnectorNotFoundError(InfraError):
    """Runner received a ``connector_id`` that is not registered (spec 03d §3.8.2).

    Distinct from ``ServiceNotFoundError`` (which is about Docker services
    unknown to ``ContainerManager``). Used at the runner boundary so the
    caller always sees an Infra-layer error regardless of backend.
    """

    error_code = "E-40007"


class ContainerStartError(InfraError):
    """``ContainerManager.start()`` failure (spec 03d §3.8.3)."""

    error_code = "E-40008"


class ContainerStopError(InfraError):
    """``ContainerManager.stop()`` failure (spec 03d §3.8.3)."""

    error_code = "E-40009"


class ServiceNotFoundError(InfraError):
    """``ContainerManager`` cannot find the named Docker service (spec 03d §3.8.3)."""

    error_code = "E-40010"
