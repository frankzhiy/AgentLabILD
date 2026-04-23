"""Tests for Phase 1-1 HypothesisState schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.hypothesis import (
    HypothesisConfidenceLevel,
    HypothesisState,
    HypothesisStatus,
)
from src.schemas.state import HypothesisState as ExportedHypothesisState


def _base_payload() -> dict[str, object]:
    return {
        "hypothesis_id": "hyp-001",
        "hypothesis_key": "  Fibrotic HP / Differential  ",
        "stage_id": "stage-001",
        "hypothesis_label": "Fibrotic hypersensitivity pneumonitis",
        "status": HypothesisStatus.PRIORITIZED,
        "confidence_level": HypothesisConfidenceLevel.MODERATE,
        "supporting_claim_ref_ids": ["claim_ref-001", "claim_ref-002"],
        "refuting_claim_ref_ids": ["claim_ref-003"],
        "missing_information_claim_ref_ids": ["claim_ref-004"],
        "rank_index": 1,
        "next_best_test": "Repeat antigen exposure interview",
        "non_authoritative_note": "for board readability only",
    }


def test_hypothesis_state_valid_construction() -> None:
    state = HypothesisState(**_base_payload())

    assert state.hypothesis_id == "hyp-001"
    assert state.hypothesis_key == "fibrotic_hp_differential"
    assert state.stage_id == "stage-001"
    assert state.status is HypothesisStatus.PRIORITIZED
    assert state.confidence_level is HypothesisConfidenceLevel.MODERATE
    assert state.supporting_claim_ref_ids == ("claim_ref-001", "claim_ref-002")
    assert state.refuting_claim_ref_ids == ("claim_ref-003",)
    assert state.missing_information_claim_ref_ids == ("claim_ref-004",)


def test_hypothesis_state_is_stage_aware() -> None:
    payload = _base_payload()
    payload["stage_id"] = "doc-001"

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_id_must_match_stable_pattern() -> None:
    payload = _base_payload()
    payload["hypothesis_id"] = "candidate-001"

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_claim_ref_ids_must_not_contain_duplicates() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = ["claim_ref-001", "claim_ref-001"]

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_claim_ref_ids_must_not_overlap_across_buckets() -> None:
    payload = _base_payload()
    payload["refuting_claim_ref_ids"] = ["claim_ref-002"]

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_requires_at_least_one_claim_ref_id() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = []
    payload["refuting_claim_ref_ids"] = []
    payload["missing_information_claim_ref_ids"] = []

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_rejects_direct_evidence_id_in_claim_bucket() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = ["evd-001"]

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_forbids_direct_evidence_ids_field() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = ["evd-001"]

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_kind_defaults_and_rejects_invalid_value() -> None:
    state = HypothesisState(**_base_payload())
    assert state.kind == "hypothesis_state"

    payload = _base_payload()
    payload["kind"] = "hypothesis"

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_hypothesis_key_blank_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["hypothesis_key"] = "   "

    state = HypothesisState(**payload)

    assert state.hypothesis_key is None


def test_rank_index_is_optional_but_must_be_positive_if_present() -> None:
    payload = _base_payload()
    payload["rank_index"] = 0

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_blank_next_best_test_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["next_best_test"] = "   "

    state = HypothesisState(**payload)

    assert state.next_best_test is None


def test_invalid_status_or_confidence_enum_rejected() -> None:
    payload = _base_payload()
    payload["status"] = "active"

    with pytest.raises(ValidationError):
        HypothesisState(**payload)


def test_status_taxonomy_avoids_clinical_activity_ambiguity() -> None:
    expected = {
        "under_consideration",
        "prioritized",
        "deprioritized",
        "ruled_out",
    }
    actual = {item.value for item in HypothesisStatus}

    assert actual == expected
    assert "active" not in actual


def test_hypothesis_state_serialization_roundtrip() -> None:
    state = HypothesisState(**_base_payload())

    serialized = state.model_dump_json()
    restored = HypothesisState.model_validate_json(serialized)

    assert restored == state


def test_state_module_exports_hypothesis_state() -> None:
    assert ExportedHypothesisState is HypothesisState
