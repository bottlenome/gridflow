"""Tests for GridflowError hierarchy."""

from gridflow.domain.error import (
    AdapterError,
    CDLValidationError,
    ConfigError,
    ConnectorError,
    DomainError,
    GridflowError,
    InfraError,
    PackNotFoundError,
    RegistryError,
    UseCaseError,
)


class TestErrorHierarchy:
    def test_gridflow_error_base(self) -> None:
        err = GridflowError("test error", context={"key": "value"})
        assert err.message == "test error"
        assert err.context == {"key": "value"}
        assert err.error_code == "E-00000"
        assert str(err) == "test error"

    def test_domain_error(self) -> None:
        err = CDLValidationError("invalid field")
        assert isinstance(err, DomainError)
        assert isinstance(err, GridflowError)
        assert err.error_code == "E-10001"

    def test_usecase_error(self) -> None:
        err = UseCaseError("orchestrator failed")
        assert err.error_code == "E-20000"

    def test_adapter_error(self) -> None:
        err = ConnectorError("connection refused")
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30001"

    def test_infra_error(self) -> None:
        err = PackNotFoundError("pack-001 not found")
        assert isinstance(err, RegistryError)
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40002"

    def test_config_error(self) -> None:
        err = ConfigError("missing key")
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40003"

    def test_empty_context_by_default(self) -> None:
        err = GridflowError("test")
        assert err.context == {}
