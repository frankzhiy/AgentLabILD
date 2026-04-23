"""Tests for Phase 1-1 ClaimReference schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.claim import (
    ClaimReference,
    ClaimRelation,
    ClaimStrength,
    ClaimTargetKind,
)
from src.schemas.state import ClaimReference as ExportedClaimReference


def _base_payload() -> dict[str, object]:
    return {
        "claim_ref_id": "claim_ref-001",
        "stage_id": "stage-001",
        "target_kind": ClaimTargetKind.HYPOTHESIS,
        "target_id": "hyp-001",
        "claim_text": "Subpleural reticulation supports fibrotic pattern hypothesis.",
        "relation": ClaimRelation.SUPPORTS,
        "evidence_ids": ["evd-001", "evd-002"],
        "claim_key": "  Fibrotic Pattern / Reticulation  ",
        "strength": ClaimStrength.MODERATE,
        "non_authoritative_note": "for audit readability only",
    }


def test_claim_reference_valid_construction() -> None:
    claim_ref = ClaimReference(**_base_payload())

    assert claim_ref.claim_ref_id == "claim_ref-001"
    assert claim_ref.target_kind is ClaimTargetKind.HYPOTHESIS
    assert claim_ref.evidence_ids == ("evd-001", "evd-002")


def test_claim_reference_kind_defaults_and_rejects_invalid_value() -> None:
    claim_ref = ClaimReference(**_base_payload())
    assert claim_ref.kind == "claim_reference"

    payload = _base_payload()
    payload["kind"] = "claim"

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_duplicate_evidence_ids_rejected() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = ["evd-001", "evd-001"]

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_empty_evidence_ids_rejected() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = []

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_claim_key_is_normalized_to_snake_case() -> None:
    payload = _base_payload()
    payload["claim_key"] = "  Missing-Data Need? High Priority!  "

    claim_ref = ClaimReference(**payload)

    assert claim_ref.claim_key == "missing_data_need_high_priority"


def test_claim_text_rejects_over_max_length() -> None:
    payload = _base_payload()
    payload["claim_text"] = "a" * 301

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_strength_semantics_are_relation_not_confidence() -> None:
    field_info = ClaimReference.model_fields["strength"]
    description = field_info.description

    assert description is not None
    assert "relation" in description
    assert "not diagnostic confidence" in description


def test_target_id_must_not_equal_claim_ref_id() -> None:
    payload = _base_payload()
    payload["target_id"] = "claim_ref-001"

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_invalid_id_patterns_rejected() -> None:
    payload = _base_payload()
    payload["claim_ref_id"] = "claim-001"

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_target_id_pattern_must_match_target_kind() -> None:
    payload = _base_payload()
    payload["target_kind"] = ClaimTargetKind.ACTION
    payload["target_id"] = "hyp-001"

    with pytest.raises(ValidationError):
        ClaimReference(**payload)


def test_legacy_action_candidate_target_kind_is_normalized() -> None:
    payload = _base_payload()
    payload["target_kind"] = "action_candidate"
    payload["target_id"] = "action-001"

    claim_ref = ClaimReference(**payload)

    assert claim_ref.target_kind is ClaimTargetKind.ACTION


def test_state_module_exports_claim_reference() -> None:
    assert ExportedClaimReference is ClaimReference
