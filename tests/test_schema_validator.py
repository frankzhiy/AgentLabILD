"""Tests for Phase 1-3 schema validator."""

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.validation import ValidationTargetKind
from src.validators.schema_validator import (
    SCHEMA_VALIDATOR_NAME,
    validate_phase1_schema,
)
from tests.test_provenance_checker import build_valid_envelope


def test_validate_phase1_schema_valid_raw_payload_returns_valid_report() -> None:
    envelope = build_valid_envelope()
    payload = envelope.model_dump(mode="python")

    report = validate_phase1_schema(payload)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()
    assert report.validator_name == SCHEMA_VALIDATOR_NAME


def test_validate_phase1_schema_rejects_non_dict_payload_as_blocking() -> None:
    report = validate_phase1_schema("invalid-payload")  # type: ignore[arg-type]

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert len(report.issues) == 1
    assert report.issues[0].issue_code == "schema.invalid_payload"
    assert report.issues[0].target_kind is ValidationTargetKind.PHASE1_STATE_ENVELOPE
    assert report.issues[0].blocking is True


def test_validate_phase1_schema_reports_missing_required_fields() -> None:
    payload = build_valid_envelope().model_dump(mode="python")
    del payload["stage_context"]

    report = validate_phase1_schema(payload)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.field_error" for issue in report.issues)
    assert any(issue.field_path == "stage_context" for issue in report.issues)
    assert any(
        issue.target_kind is ValidationTargetKind.STAGE_CONTEXT for issue in report.issues
    )


def test_validate_phase1_schema_reports_invalid_nested_object() -> None:
    payload = build_valid_envelope().model_dump(mode="python")
    payload["stage_context"]["stage_index"] = -1

    report = validate_phase1_schema(payload)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.field_error" for issue in report.issues)
    assert any(issue.field_path == "stage_context.stage_index" for issue in report.issues)
    assert any(
        issue.target_kind is ValidationTargetKind.STAGE_CONTEXT for issue in report.issues
    )


def test_validate_phase1_schema_reports_model_error_for_envelope_consistency() -> None:
    payload = build_valid_envelope().model_dump(mode="python")
    payload["evidence_atoms"][0]["stage_id"] = "stage-999"

    report = validate_phase1_schema(payload)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in report.issues)
    assert any(
        issue.target_kind is ValidationTargetKind.EVIDENCE_ATOM
        for issue in report.issues
    )


def test_validate_phase1_schema_reports_model_error_for_root_object_consistency() -> None:
    payload = build_valid_envelope().model_dump(mode="python")
    payload["board_init"]["ranked_hypothesis_ids"] = ["hyp-999"]

    report = validate_phase1_schema(payload)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in report.issues)
    assert any(issue.field_path == "board_init" for issue in report.issues)
    assert any(
        issue.target_kind is ValidationTargetKind.HYPOTHESIS_BOARD_INIT
        for issue in report.issues
    )


def test_validate_phase1_schema_accepts_preconstructed_envelope() -> None:
    envelope = build_valid_envelope()

    report = validate_phase1_schema(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()
    assert report.case_id == envelope.case_id
    assert report.stage_id == envelope.stage_context.stage_id


def test_validate_phase1_schema_revalidates_mutated_envelope_board_closure() -> None:
    envelope = build_valid_envelope()
    envelope.board_init.hypothesis_ids = ("hyp-999",)
    envelope.board_init.ranked_hypothesis_ids = ("hyp-999",)

    report = validate_phase1_schema(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in report.issues)
    assert any(issue.blocking for issue in report.issues)
    assert any(
        "board_init.hypothesis_ids must exactly match envelope ids" in issue.message
        for issue in report.issues
    )


def test_validate_phase1_schema_revalidates_mutated_envelope_hypothesis_closure() -> None:
    envelope = build_valid_envelope()
    envelope.action_candidates[0].linked_hypothesis_ids = ("hyp-999",)

    report = validate_phase1_schema(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in report.issues)
    assert any(issue.blocking for issue in report.issues)
    assert any(
        "action linked_hypothesis_ids not found in hypotheses" in issue.message
        for issue in report.issues
    )


def test_validate_phase1_schema_revalidates_mutated_envelope_claim_closure() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].target_id = "hyp-999"

    report = validate_phase1_schema(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(issue.issue_code == "schema.model_error" for issue in report.issues)
    assert any(issue.blocking for issue in report.issues)
    assert any(
        "claim_ref target mismatch for hypotheses" in issue.message
        for issue in report.issues
    )


def test_validate_phase1_schema_uses_utc_now_helper(monkeypatch: object) -> None:
    expected = datetime(2026, 4, 27, 9, 30, 0, tzinfo=timezone.utc)
    monkeypatch.setattr("src.validators.schema_validator.utc_now", lambda: expected)

    report = validate_phase1_schema(build_valid_envelope())

    assert report.generated_at == expected