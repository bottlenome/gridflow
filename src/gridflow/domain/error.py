"""GridflowError base exception hierarchy.

Error code scheme:
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
    """

    error_code: str = "E-00000"

    def __init__(self, message: str, *, context: dict[str, object] | None = None) -> None:
        self.message = message
        self.context: dict[str, object] = context or {}
        super().__init__(message)


# --- Domain layer errors (E-10xxx) ---


class DomainError(GridflowError):
    """Base for domain layer errors."""

    error_code = "E-10000"


class CDLValidationError(DomainError):
    """CDL entity validation failure."""

    error_code = "E-10001"


class PackValidationError(DomainError):
    """Scenario Pack validation failure."""

    error_code = "E-10002"


# --- Use Case layer errors (E-20xxx) ---


class UseCaseError(GridflowError):
    """Base for use case layer errors."""

    error_code = "E-20000"


class OrchestratorError(UseCaseError):
    """Orchestrator execution failure."""

    error_code = "E-20001"


class ExperimentNotFoundError(OrchestratorError):
    """Experiment not found."""

    error_code = "E-20002"


# --- Adapter layer errors (E-30xxx) ---


class AdapterError(GridflowError):
    """Base for adapter layer errors."""

    error_code = "E-30000"


class ConnectorError(AdapterError):
    """Connector operation failure."""

    error_code = "E-30001"


class UnsupportedFormatError(AdapterError):
    """Unsupported export format."""

    error_code = "E-30002"


# --- Infrastructure layer errors (E-40xxx) ---


class InfraError(GridflowError):
    """Base for infrastructure layer errors."""

    error_code = "E-40000"


class RegistryError(InfraError):
    """Registry operation failure."""

    error_code = "E-40001"


class PackNotFoundError(RegistryError):
    """Scenario Pack not found in registry."""

    error_code = "E-40002"


class ConfigError(InfraError):
    """Configuration error."""

    error_code = "E-40003"
