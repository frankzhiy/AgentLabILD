"""Tests for centralized and consistently reused id patterns."""

from __future__ import annotations

import pytest

from src.schemas import action, board, claim, common, evidence, hypothesis, stage, state


@pytest.mark.parametrize(
    ("pattern", "valid_value"),
    [
        (common.CASE_ID_PATTERN, "case-001"),
        (common.STAGE_ID_PATTERN, "stage_001"),
        (common.EVIDENCE_ID_PATTERN, "evd-001"),
        (common.CLAIM_REF_ID_PATTERN, "claim_ref-001"),
        (common.HYPOTHESIS_ID_PATTERN, "hypothesis-001"),
        (common.ACTION_CANDIDATE_ID_PATTERN, "action_candidate-001"),
        (common.BOARD_ID_PATTERN, "board-001"),
        (common.STATE_ID_PATTERN, "state_001"),
    ],
)
def test_shared_id_patterns_accept_expected_values(pattern: object, valid_value: str) -> None:
    assert pattern.fullmatch(valid_value)


@pytest.mark.parametrize(
    ("pattern", "invalid_value"),
    [
        (common.CASE_ID_PATTERN, "patient-001"),
        (common.STAGE_ID_PATTERN, "doc-001"),
        (common.EVIDENCE_ID_PATTERN, "claim_ref-001"),
        (common.CLAIM_REF_ID_PATTERN, "evd-001"),
        (common.HYPOTHESIS_ID_PATTERN, "action-001"),
        (common.ACTION_CANDIDATE_ID_PATTERN, "hyp-001"),
        (common.BOARD_ID_PATTERN, "state-001"),
        (common.STATE_ID_PATTERN, "board-001"),
    ],
)
def test_shared_id_patterns_reject_wrong_prefix_values(
    pattern: object, invalid_value: str
) -> None:
    assert pattern.fullmatch(invalid_value) is None


def test_schema_modules_reuse_centralized_id_pattern_objects() -> None:
    assert stage.CASE_ID_PATTERN is common.CASE_ID_PATTERN
    assert stage.STAGE_ID_PATTERN is common.STAGE_ID_PATTERN

    assert evidence.EVIDENCE_ID_PATTERN is common.EVIDENCE_ID_PATTERN
    assert evidence.STAGE_ID_PATTERN is common.STAGE_ID_PATTERN

    assert claim.CLAIM_REF_ID_PATTERN is common.CLAIM_REF_ID_PATTERN
    assert claim.HYPOTHESIS_ID_PATTERN is common.HYPOTHESIS_ID_PATTERN
    assert claim.ACTION_CANDIDATE_ID_PATTERN is common.ACTION_CANDIDATE_ID_PATTERN

    assert hypothesis.HYPOTHESIS_ID_PATTERN is common.HYPOTHESIS_ID_PATTERN
    assert hypothesis.CLAIM_REF_ID_PATTERN is common.CLAIM_REF_ID_PATTERN

    assert action.ACTION_CANDIDATE_ID_PATTERN is common.ACTION_CANDIDATE_ID_PATTERN
    assert action.HYPOTHESIS_ID_PATTERN is common.HYPOTHESIS_ID_PATTERN

    assert board.CASE_ID_PATTERN is common.CASE_ID_PATTERN
    assert board.BOARD_ID_PATTERN is common.BOARD_ID_PATTERN
    assert board.EVIDENCE_ID_PATTERN is common.EVIDENCE_ID_PATTERN

    assert state.CASE_ID_PATTERN is common.CASE_ID_PATTERN
    assert state.STATE_ID_PATTERN is common.STATE_ID_PATTERN
