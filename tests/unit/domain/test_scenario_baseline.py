"""Tests for baseline Scenario Pack support — AS-5 (1).

Architecture 02 §2.3 AS-5: packs carry a ``baseline`` flag and a
``citation`` field, and researchers clone a baseline pack to swap in
their own method (`gridflow scenario clone`). A clone is a derivative:
it keeps the citation (provenance) but is never itself the official
baseline, and records ``cloned_from``.
"""

from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

import pytest

from gridflow.domain.error import PackValidationError
from gridflow.domain.scenario.scenario_pack import (
    PackMetadata,
    PackStatus,
    ScenarioPack,
)


def _baseline_pack() -> ScenarioPack:
    metadata = PackMetadata(
        name="ieee13-volt-var",
        version="1.0.0",
        description="IEEE 13-bus Volt-VAR baseline",
        author="gridflow",
        created_at=datetime(2026, 1, 1, tzinfo=UTC),
        connector="opendss",
        seed=42,
        baseline=True,
        citation="Doe et al., Volt-VAR baseline study, IEEE PES GM 2025",
    )
    return ScenarioPack(
        pack_id="ieee13-volt-var@1.0.0",
        name="ieee13-volt-var",
        version="1.0.0",
        metadata=metadata,
        network_dir=Path("/packs/ieee13"),
        timeseries_dir=Path("/packs/ieee13"),
        config_dir=Path("/packs/ieee13"),
        status=PackStatus.REGISTERED,
    )


class TestBaselineMetadata:
    def test_defaults_are_not_baseline(self) -> None:
        metadata = PackMetadata(
            name="x",
            version="1",
            description="d",
            author="a",
            created_at=datetime(2026, 1, 1, tzinfo=UTC),
            connector="opendss",
        )
        assert metadata.baseline is False
        assert metadata.citation == ""

    def test_to_dict_round_trips_baseline_and_citation(self) -> None:
        pack = _baseline_pack()
        data = pack.metadata.to_dict()
        assert data["baseline"] is True
        assert "IEEE PES GM 2025" in str(data["citation"])

    def test_pack_to_dict_includes_cloned_from(self) -> None:
        pack = _baseline_pack()
        assert pack.to_dict()["cloned_from"] == ""


class TestClone:
    def test_clone_gets_new_id_and_provenance(self) -> None:
        clone = _baseline_pack().clone("my-method@0.1.0")
        assert clone.pack_id == "my-method@0.1.0"
        assert clone.cloned_from == "ieee13-volt-var@1.0.0"

    def test_clone_is_draft_and_not_baseline(self) -> None:
        clone = _baseline_pack().clone("my-method@0.1.0")
        assert clone.status is PackStatus.DRAFT
        assert clone.metadata.baseline is False

    def test_clone_preserves_citation_and_content(self) -> None:
        original = _baseline_pack()
        clone = original.clone("my-method@0.1.0")
        assert clone.metadata.citation == original.metadata.citation
        assert clone.metadata.seed == original.metadata.seed
        assert clone.network_dir == original.network_dir
        assert clone.name == original.name

    def test_clone_with_same_id_rejected(self) -> None:
        with pytest.raises(PackValidationError):
            _baseline_pack().clone("ieee13-volt-var@1.0.0")

    def test_clone_with_empty_id_rejected(self) -> None:
        with pytest.raises(PackValidationError):
            _baseline_pack().clone("")

    def test_clone_validates(self) -> None:
        clone = _baseline_pack().clone("my-method@0.1.0")
        clone.validate()
