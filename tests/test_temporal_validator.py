"""Tests for Phase 1-3 temporal validator."""

from __future__ import annotations

from datetime import timedelta

from src.schemas.validation import ValidationTargetKind
from src.validators.temporal_validator import (
    TEMPORAL_VALIDATOR_NAME,
    validate_phase1_temporal,
)
from tests.test_provenance_checker import build_valid_envelope


def test_validate_phase1_temporal_valid_baseline_state() -> None:
    envelope = build_valid_envelope()

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()
    assert report.validator_name == TEMPORAL_VALIDATOR_NAME


def test_validate_phase1_temporal_rejects_stage_created_after_envelope() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.created_at = envelope.created_at + timedelta(seconds=1)

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "temporal.stage_after_envelope" for issue in report.issues
    )
    assert any(
        issue.target_kind is ValidationTargetKind.STAGE_CONTEXT for issue in report.issues
    )


def test_validate_phase1_temporal_rejects_board_initialized_after_envelope() -> None:
    envelope = build_valid_envelope()
    envelope.board_init.initialized_at = envelope.created_at + timedelta(seconds=1)

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "temporal.board_after_envelope" for issue in report.issues
    )
    assert any(
        issue.target_kind is ValidationTargetKind.HYPOTHESIS_BOARD_INIT
        for issue in report.issues
    )


def test_validate_phase1_temporal_rejects_root_with_parent_state() -> None:
    envelope = build_valid_envelope()
    envelope.parent_state_id = "state-000"

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "temporal.invalid_root_parent" for issue in report.issues
    )
    assert any(
        issue.target_kind is ValidationTargetKind.PHASE1_STATE_ENVELOPE
        for issue in report.issues
    )


def test_validate_phase1_temporal_rejects_parent_with_state_version_lt_2() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.stage_index = 1
    envelope.parent_state_id = "state-000"
    envelope.state_version = 1

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "temporal.invalid_state_version" for issue in report.issues
    )
    assert all(
        issue.issue_code != "temporal.invalid_root_parent" for issue in report.issues
    )


def test_validate_phase1_temporal_allows_earlier_clinical_time() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.clinical_time = envelope.created_at - timedelta(days=7)

    report = validate_phase1_temporal(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False