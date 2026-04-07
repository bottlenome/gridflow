"""Tests for Asset, TimeSeries, Event, Metric, ExperimentMetadata CDL models."""

from datetime import UTC, datetime

import pytest

from gridflow.domain.cdl import Asset, Event, ExperimentMetadata, Metric, TimeSeries
from gridflow.domain.error import CDLValidationError
from gridflow.domain.util.params import as_params, get_param


class TestAsset:
    def test_create_asset(self) -> None:
        asset = Asset(asset_id="pv-001", name="PV Panel 1", asset_type="pv", node_id="632", rated_power_kw=100.0)
        assert asset.asset_id == "pv-001"
        assert asset.parameters == ()

    def test_asset_to_dict(self) -> None:
        asset = Asset(
            asset_id="pv-001",
            name="PV Panel 1",
            asset_type="pv",
            node_id="632",
            rated_power_kw=100.0,
            parameters=as_params({"efficiency": 0.2}),
        )
        d = asset.to_dict()
        assert d["rated_power_kw"] == 100.0
        assert d["parameters"] == {"efficiency": 0.2}
        assert get_param(asset.parameters, "efficiency") == 0.2

    def test_asset_is_hashable(self) -> None:
        asset = Asset(asset_id="pv-001", name="pv", asset_type="pv", node_id="632", rated_power_kw=100.0)
        assert hash(asset) == hash(asset)
        assert len({asset, asset}) == 1

    def test_asset_validate_negative_power(self) -> None:
        asset = Asset(asset_id="pv-001", name="PV", asset_type="pv", node_id="632", rated_power_kw=-10.0)
        with pytest.raises(CDLValidationError, match="rated_power_kw"):
            asset.validate()


class TestTimeSeries:
    def test_create_time_series(self) -> None:
        ts = TimeSeries(
            series_id="ts-001",
            name="Load",
            timestamps=(datetime(2026, 1, 1, tzinfo=UTC),),
            values=(100.0,),
            unit="kW",
            resolution_s=3600.0,
        )
        assert ts.series_id == "ts-001"

    def test_time_series_validate_length_mismatch(self) -> None:
        ts = TimeSeries(
            series_id="ts-001",
            name="Load",
            timestamps=(datetime(2026, 1, 1, tzinfo=UTC),),
            values=(100.0, 200.0),
            unit="kW",
            resolution_s=3600.0,
        )
        with pytest.raises(CDLValidationError, match="same length"):
            ts.validate()

    def test_time_series_validate_negative_resolution(self) -> None:
        ts = TimeSeries(
            series_id="ts-001",
            name="Load",
            timestamps=(),
            values=(),
            unit="kW",
            resolution_s=-1.0,
        )
        with pytest.raises(CDLValidationError, match="resolution_s"):
            ts.validate()


class TestEvent:
    def test_create_event(self) -> None:
        event = Event(
            event_id="evt-001",
            event_type="fault",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            target_id="650",
            target_type="node",
        )
        assert event.event_type == "fault"

    def test_event_validate_invalid_target_type(self) -> None:
        event = Event(
            event_id="evt-001",
            event_type="fault",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            target_id="650",
            target_type="invalid",
        )
        with pytest.raises(CDLValidationError, match="target_type"):
            event.validate()

    def test_event_to_dict(self) -> None:
        event = Event(
            event_id="evt-001",
            event_type="fault",
            timestamp=datetime(2026, 1, 1, tzinfo=UTC),
            target_id="650",
            target_type="node",
            parameters=as_params({"impedance": 0.001}),
        )
        d = event.to_dict()
        assert d["timestamp"] == "2026-01-01T00:00:00+00:00"
        assert d["parameters"] == {"impedance": 0.001}


class TestMetric:
    def test_create_metric(self) -> None:
        m = Metric(name="voltage_deviation", value=0.05, unit="pu")
        assert m.step is None
        assert m.threshold is None

    def test_metric_validate_empty_name(self) -> None:
        m = Metric(name="", value=0.0, unit="pu")
        with pytest.raises(CDLValidationError, match="name"):
            m.validate()


class TestExperimentMetadata:
    def test_create_metadata(self) -> None:
        meta = ExperimentMetadata(
            experiment_id="exp-001",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            scenario_pack_id="pack-001",
            connector="opendss",
        )
        assert meta.seed is None

    def test_metadata_validate_empty_connector(self) -> None:
        meta = ExperimentMetadata(
            experiment_id="exp-001",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            scenario_pack_id="pack-001",
            connector="",
        )
        with pytest.raises(CDLValidationError, match="connector"):
            meta.validate()

    def test_metadata_to_dict(self) -> None:
        meta = ExperimentMetadata(
            experiment_id="exp-001",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            scenario_pack_id="pack-001",
            connector="opendss",
            seed=42,
        )
        d = meta.to_dict()
        assert d["seed"] == 42
        assert d["created_at"] == "2026-01-01T00:00:00+00:00"
