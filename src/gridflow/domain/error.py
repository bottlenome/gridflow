"""GridflowError base exception hierarchy.

Error code scheme (per DD-ERR-001, section 8.2):
    E-10xxx: Domain layer errors
    E-20xxx: Use Case layer errors
    E-30xxx: Adapter layer errors
    E-40xxx: Infrastructure layer errors
"""

from __future__ import annotations


class GridflowError(Exception):
    """Base exception for all gridflow errors.

    Attributes:
        error_code: Error code string (e.g. "E-10001").
        message: Human-readable error message.
        context: Additional context information.
        cause: Original exception for chaining (traceback preservation).
    """

    error_code: str = "E-00000"

    def __init__(
        self,
        message: str,
        *,
        context: dict[str, object] | None = None,
        cause: Exception | None = None,
    ) -> None:
        self.message = message
        self.context: dict[str, object] = context or {}
        self.cause = cause
        super().__init__(message)
        if cause is not None:
            self.__cause__ = cause

    def to_dict(self) -> dict[str, object]:
        """Serialize to dict for logging / API responses."""
        return {
            "error_code": self.error_code,
            "message": self.message,
            "context": self.context,
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
