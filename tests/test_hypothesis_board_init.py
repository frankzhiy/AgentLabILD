"""Tests for Phase 1-1 HypothesisBoardInit schema."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.board import BoardInitSource, BoardStatus, HypothesisBoardInit
from src.schemas.state import HypothesisBoardInit as ExportedHypothesisBoardInit


def _base_payload() -> dict[str, object]:
    return {
        "board_id": "board-001",
        "case_id": "case-abc",
        "stage_id": "stage-001",
        "board_status": BoardStatus.INITIALIZED,
        "init_source": BoardInitSource.STAGE_BOOTSTRAP,
        "initialized_at": datetime(2026, 4, 23, 12, 0, 0),
        "evidence_ids": ["evd-001", "ev-002"],
        "hypothesis_ids": ["hyp-001", "hypothesis-002"],
        "action_candidate_ids": ["action-001", "action_candidate-002"],
        "ranked_hypothesis_ids": ["hypothesis-002"],
        "parent_board_id": None,
        "non_authoritative_note": "for board readability only",
    }


def test_hypothesis_board_init_valid_construction() -> None:
    board = HypothesisBoardInit(**_base_payload())

    assert board.board_id == "board-001"
    assert board.stage_id == "stage-001"
    assert board.board_status is BoardStatus.INITIALIZED
    assert board.init_source is BoardInitSource.STAGE_BOOTSTRAP
    assert board.hypothesis_ids == ("hyp-001", "hypothesis-002")
    assert board.ranked_hypothesis_ids == ("hypothesis-002",)


def test_hypothesis_board_init_kind_defaults_and_rejects_invalid_value() -> None:
    board = HypothesisBoardInit(**_base_payload())
    assert board.kind == "hypothesis_board_init"

    payload = _base_payload()
    payload["kind"] = "board_init"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_board_status_has_minimal_lifecycle_taxonomy() -> None:
    expected = {"draft", "initialized", "ready_for_review"}
    actual = {item.value for item in BoardStatus}

    assert actual == expected


def test_hypothesis_ids_must_be_non_empty() -> None:
    payload = _base_payload()
    payload["hypothesis_ids"] = []

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_case_id_pattern_rejected_when_using_patient_prefix() -> None:
    payload = _base_payload()
    payload["case_id"] = "patient_78"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_ranked_hypothesis_ids_must_be_subset_of_hypothesis_ids() -> None:
    payload = _base_payload()
    payload["ranked_hypothesis_ids"] = ["hyp-999"]

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_parent_board_id_must_not_equal_board_id() -> None:
    payload = _base_payload()
    payload["parent_board_id"] = "board-001"
    payload["init_source"] = BoardInitSource.PARENT_BOARD_PROPAGATION

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_parent_board_propagation_requires_parent_board_id() -> None:
    payload = _base_payload()
    payload["init_source"] = BoardInitSource.PARENT_BOARD_PROPAGATION
    payload["parent_board_id"] = None

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_parent_board_propagation_allows_parent_board_id() -> None:
    payload = _base_payload()
    payload["init_source"] = BoardInitSource.PARENT_BOARD_PROPAGATION
    payload["parent_board_id"] = "board-000"

    board = HypothesisBoardInit(**payload)

    assert board.parent_board_id == "board-000"


def test_stage_bootstrap_forbids_parent_board_id() -> None:
    payload = _base_payload()
    payload["init_source"] = BoardInitSource.STAGE_BOOTSTRAP
    payload["parent_board_id"] = "board-000"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_parent_board_id_blank_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["parent_board_id"] = "   "

    board = HypothesisBoardInit(**payload)

    assert board.parent_board_id is None


def test_non_authoritative_note_blank_is_normalized_to_none() -> None:
    payload = _base_payload()
    payload["non_authoritative_note"] = "\n  "

    board = HypothesisBoardInit(**payload)

    assert board.non_authoritative_note is None


def test_ranked_hypothesis_ids_can_be_empty() -> None:
    payload = _base_payload()
    payload["ranked_hypothesis_ids"] = []

    board = HypothesisBoardInit(**payload)

    assert board.ranked_hypothesis_ids == ()


def test_duplicate_evidence_ids_rejected() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = ["evd-001", "evd-001"]

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_duplicate_hypothesis_ids_rejected() -> None:
    payload = _base_payload()
    payload["hypothesis_ids"] = ["hyp-001", "hyp-001"]

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_duplicate_action_candidate_ids_rejected() -> None:
    payload = _base_payload()
    payload["action_candidate_ids"] = ["action-001", "action-001"]

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_invalid_id_patterns_rejected() -> None:
    payload = _base_payload()
    payload["board_id"] = "hyp-001"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_stage_id_pattern_rejected_when_using_doc_prefix() -> None:
    payload = _base_payload()
    payload["stage_id"] = "doc-001"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_reference_fields_accept_id_only_not_mixed_prefix() -> None:
    payload = _base_payload()
    payload["evidence_ids"] = ["claim_ref-001"]

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_extra_diagnosis_field_is_forbidden() -> None:
    payload = _base_payload()
    payload["final_diagnosis"] = "IPF"

    with pytest.raises(ValidationError):
        HypothesisBoardInit(**payload)


def test_serialization_roundtrip() -> None:
    board = HypothesisBoardInit(**_base_payload())

    serialized = board.model_dump_json()
    restored = HypothesisBoardInit.model_validate_json(serialized)

    assert restored == board


def test_state_module_exports_hypothesis_board_init() -> None:
    assert ExportedHypothesisBoardInit is HypothesisBoardInit
