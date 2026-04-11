"""Tests for GridflowError hierarchy (per design 8.1.1)."""

from gridflow.domain.error import (
    AdapterError,
    BenchmarkError,
    CDLValidationError,
    CLIError,
    ConfigError,
    ConnectorError,
    ConnectorRequestError,
    ConnectorStateError,
    ContainerError,
    DomainError,
    ExperimentNotFoundError,
    GridflowError,
    InfraError,
    MetricCalculationError,
    OpenDSSError,
    OrchestratorError,
    PackNotFoundError,
    PackValidationError,
    PluginError,
    RegistryError,
    ScenarioPackError,
    SimulationError,
    UnsupportedFormatError,
    UseCaseError,
)


class TestGridflowErrorBase:
    def test_attributes(self) -> None:
        err = GridflowError("test error", context={"key": "value"})
        assert err.message == "test error"
        # context is stored as an immutable params tuple (CLAUDE.md §0.3)
        assert err.context == (("key", "value"),)
        assert err.error_code == "E-00000"
        assert err.cause is None

    def test_str_format(self) -> None:
        err = GridflowError("test error")
        assert str(err) == "[E-00000] test error"

    def test_to_dict(self) -> None:
        err = GridflowError("test", context={"k": "v"})
        d = err.to_dict()
        # to_dict() rehydrates the tuple into a plain dict for serialisation
        assert d == {"error_code": "E-00000", "message": "test", "context": {"k": "v"}}

    def test_cause_chaining(self) -> None:
        original = ValueError("original")
        err = GridflowError("wrapped", cause=original)
        assert err.cause is original
        assert err.__cause__ is original

    def test_empty_context_by_default(self) -> None:
        err = GridflowError("test")
        assert err.context == ()

    def test_context_is_hashable_tuple(self) -> None:
        # Regression: CLAUDE.md §0.3 requires immutable params tuple, not dict
        err = GridflowError("test", context={"b": 2, "a": 1})
        assert isinstance(err.context, tuple)
        # as_params sorts by key for deterministic equality
        assert err.context == (("a", 1), ("b", 2))
        hash(err.context)  # must not raise

    def test_context_accepts_iterable_of_pairs(self) -> None:
        err = GridflowError("test", context=[("x", 1), ("y", 2)])
        assert err.context == (("x", 1), ("y", 2))


class TestDomainErrors:
    def test_scenario_pack_error(self) -> None:
        err = ScenarioPackError("invalid pack")
        assert isinstance(err, DomainError)
        assert isinstance(err, GridflowError)
        assert err.error_code == "E-10001"

    def test_pack_not_found_under_scenario_pack(self) -> None:
        err = PackNotFoundError("pack-001 not found")
        assert isinstance(err, ScenarioPackError)
        assert isinstance(err, DomainError)
        assert err.error_code == "E-10002"

    def test_pack_validation_error(self) -> None:
        err = PackValidationError("schema mismatch")
        assert isinstance(err, ScenarioPackError)
        assert err.error_code == "E-10003"

    def test_cdl_validation_error(self) -> None:
        err = CDLValidationError("invalid field")
        assert isinstance(err, DomainError)
        assert err.error_code == "E-10004"

    def test_metric_calculation_error(self) -> None:
        err = MetricCalculationError("division by zero")
        assert isinstance(err, DomainError)
        assert err.error_code == "E-10005"


class TestUseCaseErrors:
    def test_simulation_error(self) -> None:
        err = SimulationError("step failed")
        assert isinstance(err, UseCaseError)
        assert err.error_code == "E-20001"

    def test_benchmark_error(self) -> None:
        err = BenchmarkError("comparison failed")
        assert isinstance(err, UseCaseError)
        assert err.error_code == "E-20002"

    def test_experiment_not_found(self) -> None:
        err = ExperimentNotFoundError("exp-001")
        assert isinstance(err, UseCaseError)
        assert err.error_code == "E-20003"


class TestAdapterErrors:
    def test_connector_error(self) -> None:
        err = ConnectorError("connection refused")
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30001"

    def test_opendss_error_under_connector(self) -> None:
        err = OpenDSSError("convergence failure")
        assert isinstance(err, ConnectorError)
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30002"

    def test_cli_error(self) -> None:
        err = CLIError("unknown command")
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30003"

    def test_plugin_error(self) -> None:
        err = PluginError("load failed")
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30004"

    def test_unsupported_format_error(self) -> None:
        err = UnsupportedFormatError("parquet not supported")
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30005"

    def test_connector_state_error_under_connector(self) -> None:
        err = ConnectorStateError("session already active")
        assert isinstance(err, ConnectorError)
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30006"

    def test_connector_request_error_under_connector(self) -> None:
        err = ConnectorRequestError("missing field 'pack_id'")
        assert isinstance(err, ConnectorError)
        assert isinstance(err, AdapterError)
        assert err.error_code == "E-30007"


class TestInfraErrors:
    def test_orchestrator_error(self) -> None:
        err = OrchestratorError("workflow failed")
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40001"

    def test_container_error(self) -> None:
        err = ContainerError("docker start failed")
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40002"

    def test_registry_error(self) -> None:
        err = RegistryError("storage unavailable")
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40003"

    def test_config_error(self) -> None:
        err = ConfigError("missing key")
        assert isinstance(err, InfraError)
        assert err.error_code == "E-40004"
