"""Tests for Phase 1-1 ActionCandidate schema."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.schemas.action import (
    ActionCandidate,
    ActionStatus,
    ActionType,
    ActionUrgency,
)
from src.schemas.hypothesis import HypothesisStatus
from src.schemas.state import ActionCandidate as ExportedActionCandidate


def _base_payload() -> dict[str, object]:
    return {
        "action_candidate_id": "action_candidate-001",
        "action_key": "  Order Repeat PFT / DLCO  ",
        "stage_id": "stage-001",
        "action_type": ActionType.ORDER_DIAGNOSTIC_TEST,
        "action_text": "Order repeat PFT with DLCO in 2 weeks.",
        "status": ActionStatus.PRIORITIZED,
        "urgency": ActionUrgency.EXPEDITED,
        "linked_hypothesis_ids": ["hyp-001", "hypothesis-002"],
        "supporting_claim_ref_ids": ["claim_ref-001", "claim_ref-002"],
        "refuting_claim_ref_ids": ["claim_ref-003"],
        "missing_information_claim_ref_ids": ["claim_ref-004"],
        "safety_concern_claim_ref_ids": ["claim_ref-005"],
        "rank_index": 1,
        "non_authoritative_note": "for board readability only",
    }


def test_action_candidate_valid_construction() -> None:
    candidate = ActionCandidate(**_base_payload())

    assert candidate.action_candidate_id == "action_candidate-001"
    assert candidate.action_key == "order_repeat_pft_dlco"
    assert candidate.stage_id == "stage-001"
    assert candidate.action_type is ActionType.ORDER_DIAGNOSTIC_TEST
    assert candidate.status is ActionStatus.PRIORITIZED
    assert candidate.urgency is ActionUrgency.EXPEDITED
    assert candidate.linked_hypothesis_ids == ("hyp-001", "hypothesis-002")


def test_action_candidate_kind_defaults_and_rejects_invalid_value() -> None:
    candidate = ActionCandidate(**_base_payload())
    assert candidate.kind == "action_candidate"

    payload = _base_payload()
    payload["kind"] = "action"

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_candidate_is_stage_aware() -> None:
    payload = _base_payload()
    payload["stage_id"] = "doc-001"

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_candidate_id_must_match_stable_pattern() -> None:
    payload = _base_payload()
    payload["action_candidate_id"] = "candidate-001"

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_linked_hypothesis_ids_must_not_contain_duplicates() -> None:
    payload = _base_payload()
    payload["linked_hypothesis_ids"] = ["hyp-001", "hyp-001"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_linked_hypothesis_ids_must_match_hypothesis_pattern() -> None:
    payload = _base_payload()
    payload["linked_hypothesis_ids"] = ["claim_ref-001"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_claim_ref_ids_must_not_contain_duplicates() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = ["claim_ref-001", "claim_ref-001"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_claim_ref_ids_must_not_overlap_across_buckets() -> None:
    payload = _base_payload()
    payload["safety_concern_claim_ref_ids"] = ["claim_ref-002"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_candidate_requires_at_least_one_claim_ref_id() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = []
    payload["refuting_claim_ref_ids"] = []
    payload["missing_information_claim_ref_ids"] = []
    payload["safety_concern_claim_ref_ids"] = []

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_candidate_rejects_direct_evidence_id_in_claim_bucket() -> None:
    payload = _base_payload()
    payload["supporting_claim_ref_ids"] = ["evd-001"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_candidate_forbids_direct_evidence_ids_field() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = ["evd-001"]

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_blocked_status_requires_refuting_or_safety_claim_ref_id() -> None:
    payload = _base_payload()
    payload["status"] = ActionStatus.BLOCKED
    payload["refuting_claim_ref_ids"] = []
    payload["safety_concern_claim_ref_ids"] = []

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_blocked_status_allows_safety_concern_only() -> None:
    payload = _base_payload()
    payload["status"] = ActionStatus.BLOCKED
    payload["refuting_claim_ref_ids"] = []
    payload["supporting_claim_ref_ids"] = []
    payload["missing_information_claim_ref_ids"] = []
    payload["safety_concern_claim_ref_ids"] = ["claim_ref-900"]

    candidate = ActionCandidate(**payload)

    assert candidate.status is ActionStatus.BLOCKED
    assert candidate.safety_concern_claim_ref_ids == ("claim_ref-900",)


def test_action_key_blank_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["action_key"] = "   "

    candidate = ActionCandidate(**payload)

    assert candidate.action_key is None


def test_blank_non_authoritative_note_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["non_authoritative_note"] = "   "

    candidate = ActionCandidate(**payload)

    assert candidate.non_authoritative_note is None


def test_rank_index_is_optional_but_must_be_positive_if_present() -> None:
    payload = _base_payload()
    payload["rank_index"] = 0

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_invalid_status_or_urgency_enum_rejected() -> None:
    payload = _base_payload()
    payload["status"] = "active"

    with pytest.raises(ValidationError):
        ActionCandidate(**payload)


def test_action_status_taxonomy_aligns_with_hypothesis_priority_axis() -> None:
    action_statuses = {item.value for item in ActionStatus}
    hypothesis_statuses = {item.value for item in HypothesisStatus}

    assert action_statuses == {
        "under_consideration",
        "prioritized",
        "deprioritized",
        "blocked",
    }
    assert "candidate" not in action_statuses
    assert "deferred" not in action_statuses
    assert action_statuses - {"blocked"} == hypothesis_statuses - {"ruled_out"}


def test_action_type_taxonomy_avoids_status_semantic_overlap() -> None:
    action_types = {item.value for item in ActionType}

    assert "start_or_adjust_treatment" in action_types
    assert "start_or_adjust_treatment_trial" not in action_types
    assert "defer_pending_information" not in action_types


def test_action_candidate_serialization_roundtrip() -> None:
    candidate = ActionCandidate(**_base_payload())

    serialized = candidate.model_dump_json()
    restored = ActionCandidate.model_validate_json(serialized)

    assert restored == candidate


def test_state_module_exports_action_candidate() -> None:
    assert ExportedActionCandidate is ActionCandidate
