"""Tests for Phase 1-2 provenance validator."""

from __future__ import annotations

from datetime import datetime

from src.provenance.checker import check_phase1_provenance
from src.validators.provenance_validator import (
    DEFAULT_VALIDATOR_NAME,
    build_provenance_validation_issues,
    convert_provenance_issues_to_validation_issues,
    validate_phase1_provenance,
)
from tests.test_provenance_checker import build_valid_envelope


def test_validate_phase1_provenance_returns_valid_report_when_clean() -> None:
    envelope = build_valid_envelope()

    report = validate_phase1_provenance(
        envelope,
        require_provenance=True,
        generated_at=datetime(2026, 4, 23, 17, 0, 0),
    )

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()
    assert report.validator_name == DEFAULT_VALIDATOR_NAME


def test_build_provenance_validation_issues_converts_checker_output() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance = None

    issues = build_provenance_validation_issues(envelope)

    assert len(issues) >= 1
    assert issues[0].issue_id == "issue-provenance-0001"
    assert issues[0].issue_code.startswith("provenance.")


def test_convert_provenance_issues_to_validation_issues_keeps_order() -> None:
    envelope = build_valid_envelope()
    envelope.evidence_atoms[0].provenance = None
    raw_issues = check_phase1_provenance(envelope)

    validation_issues = convert_provenance_issues_to_validation_issues(raw_issues)

    assert len(validation_issues) == len(raw_issues)
    assert validation_issues[-1].issue_id == (
        f"issue-provenance-{len(validation_issues):04d}"
    )


def test_validate_phase1_provenance_missing_provenance_is_non_blocking_by_default() -> None:
    envelope = build_valid_envelope()
    envelope.evidence_atoms[0].provenance = None
    envelope.claim_references[0].provenance.evidence_provenance_ids = ()
    envelope.claim_references[1].provenance.evidence_provenance_ids = ()

    report = validate_phase1_provenance(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert any(
        issue.issue_code == "provenance.missing_provenance" for issue in report.issues
    )


def test_validate_phase1_provenance_missing_provenance_blocks_when_required() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance = None

    report = validate_phase1_provenance(envelope, require_provenance=True)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.missing_provenance" and issue.blocking
        for issue in report.issues
    )


def test_validate_phase1_provenance_blocks_orphan_provenance_reference() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance.evidence_provenance_ids = ("eprov-999",)

    report = validate_phase1_provenance(envelope, require_provenance=True)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.orphan_evidence_provenance_reference"
        for issue in report.issues
    )
