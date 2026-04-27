"""Tests for Phase 1-3 unified validation pipeline."""

from __future__ import annotations

from datetime import timedelta

from src.validators.pipeline import (
    FULL_VALIDATOR_EXECUTION_ORDER,
    SCHEMA_ONLY_EXECUTION_ORDER,
    validate_phase1_candidate_pipeline,
)
from src.validators.provenance_validator import DEFAULT_VALIDATOR_NAME
from src.validators.schema_validator import SCHEMA_VALIDATOR_NAME
from src.validators.temporal_validator import TEMPORAL_VALIDATOR_NAME
from src.validators.unsupported_claims import UNSUPPORTED_CLAIM_VALIDATOR_NAME
from tests.test_provenance_checker import build_valid_envelope


def _get_report_by_validator_name(result: object, validator_name: str) -> object:
    reports = [
        report
        for report in result.reports
        if report.validator_name == validator_name
    ]
    assert len(reports) == 1
    return reports[0]


def test_pipeline_raw_payload_schema_failure_returns_schema_only_report() -> None:
    payload = build_valid_envelope().model_dump(mode="python")
    payload["evidence_atoms"][0]["stage_id"] = "stage-999"

    result = validate_phase1_candidate_pipeline(payload)

    assert result.candidate_envelope is None
    assert result.has_blocking_issue is True
    assert result.validator_execution_order == SCHEMA_ONLY_EXECUTION_ORDER
    assert len(result.reports) == 1
    assert result.reports[0].validator_name == SCHEMA_VALIDATOR_NAME
    assert any(issue.issue_code.startswith("schema.") for issue in result.reports[0].issues)


def test_pipeline_valid_envelope_with_provenance_issue_includes_downstream_reports() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance = None

    result = validate_phase1_candidate_pipeline(envelope, require_provenance=True)

    provenance_report = _get_report_by_validator_name(result, DEFAULT_VALIDATOR_NAME)

    assert result.candidate_envelope is envelope
    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert len(result.reports) == 4
    assert any(
        issue.issue_code == "provenance.missing_provenance"
        for issue in provenance_report.issues
    )


def test_pipeline_valid_envelope_with_temporal_issue_includes_downstream_reports() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.created_at = envelope.created_at + timedelta(seconds=1)

    result = validate_phase1_candidate_pipeline(envelope)

    temporal_report = _get_report_by_validator_name(result, TEMPORAL_VALIDATOR_NAME)

    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert any(
        issue.issue_code == "temporal.stage_after_envelope"
        for issue in temporal_report.issues
    )


def test_pipeline_valid_envelope_with_unsupported_claim_issue_includes_downstream_reports() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].evidence_ids = ("evd-999",)

    result = validate_phase1_candidate_pipeline(envelope)

    unsupported_report = _get_report_by_validator_name(
        result,
        UNSUPPORTED_CLAIM_VALIDATOR_NAME,
    )

    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert any(
        issue.issue_code == "unsupported_claim.missing_evidence_reference"
        for issue in unsupported_report.issues
    )


def test_pipeline_fully_valid_envelope_returns_all_valid_reports() -> None:
    envelope = build_valid_envelope()

    result = validate_phase1_candidate_pipeline(envelope, require_provenance=True)

    assert result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert len(result.reports) == 4
    assert result.has_blocking_issue is False
    assert all(report.is_valid for report in result.reports)


def test_pipeline_validator_order_is_stable_for_raw_and_envelope_inputs() -> None:
    envelope = build_valid_envelope()
    valid_payload = envelope.model_dump(mode="python")

    payload_result = validate_phase1_candidate_pipeline(valid_payload)
    envelope_result = validate_phase1_candidate_pipeline(envelope)

    assert payload_result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER
    assert envelope_result.validator_execution_order == FULL_VALIDATOR_EXECUTION_ORDER


def test_pipeline_preserves_report_granularity_and_issue_namespaces() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance = None
    envelope.stage_context.created_at = envelope.created_at + timedelta(seconds=1)
    envelope.claim_references[0].evidence_ids = ("evd-999",)

    result = validate_phase1_candidate_pipeline(envelope, require_provenance=True)

    schema_report = _get_report_by_validator_name(result, SCHEMA_VALIDATOR_NAME)
    provenance_report = _get_report_by_validator_name(result, DEFAULT_VALIDATOR_NAME)
    temporal_report = _get_report_by_validator_name(result, TEMPORAL_VALIDATOR_NAME)
    unsupported_report = _get_report_by_validator_name(
        result,
        UNSUPPORTED_CLAIM_VALIDATOR_NAME,
    )

    assert schema_report.issues == ()
    assert provenance_report.report_id.startswith("report-provenance-")
    assert temporal_report.report_id.startswith("report-temporal-")
    assert unsupported_report.report_id.startswith("report-unsupported-claim-")
    assert all(issue.issue_code.startswith("provenance.") for issue in provenance_report.issues)
    assert all(issue.issue_code.startswith("temporal.") for issue in temporal_report.issues)
    assert all(
        issue.issue_code.startswith("unsupported_claim.")
        for issue in unsupported_report.issues
    )
