"""Tests for Phase 1-3 conservative unsupported-claim validator."""

from __future__ import annotations

import ast
import inspect

from src.schemas.claim import ClaimStrength, ClaimTargetKind
from src.schemas.evidence import EvidenceCertainty
from src.schemas.validation import ValidationSeverity, ValidationTargetKind
from src.validators.unsupported_claims import (
    UNSUPPORTED_CLAIM_VALIDATOR_NAME,
    validate_phase1_unsupported_claims,
)
from tests.test_provenance_checker import build_valid_envelope


def test_validate_phase1_unsupported_claims_valid_envelope_returns_valid_report() -> None:
    envelope = build_valid_envelope()

    report = validate_phase1_unsupported_claims(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()
    assert report.validator_name == UNSUPPORTED_CLAIM_VALIDATOR_NAME


def test_validate_phase1_unsupported_claims_reports_missing_evidence_reference() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].evidence_ids = ("evd-999",)

    report = validate_phase1_unsupported_claims(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "unsupported_claim.missing_evidence_reference"
        and issue.blocking
        and issue.target_kind is ValidationTargetKind.CLAIM_REFERENCE
        for issue in report.issues
    )


def test_validate_phase1_unsupported_claims_reports_invalid_target_binding() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].target_kind = ClaimTargetKind.HYPOTHESIS
    envelope.claim_references[0].target_id = "hyp-999"

    report = validate_phase1_unsupported_claims(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "unsupported_claim.invalid_target_binding"
        and issue.blocking
        and issue.target_kind is ValidationTargetKind.CLAIM_REFERENCE
        for issue in report.issues
    )


def test_validate_phase1_unsupported_claims_reports_unusable_evidence_reference() -> None:
    envelope = build_valid_envelope()
    envelope.evidence_atoms[0].stage_id = "stage-999"

    report = validate_phase1_unsupported_claims(envelope)

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "unsupported_claim.unusable_evidence_reference"
        and issue.blocking
        and issue.related_ids == ("evd-001",)
        for issue in report.issues
    )


def test_validate_phase1_unsupported_claims_reports_overstated_strength_as_warning() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].strength = ClaimStrength.STRONG
    envelope.evidence_atoms[0].certainty = EvidenceCertainty.REPORTED

    report = validate_phase1_unsupported_claims(envelope)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert any(
        issue.issue_code == "unsupported_claim.overstated_strength"
        and issue.blocking is False
        and issue.severity is ValidationSeverity.WARNING
        for issue in report.issues
    )


def test_validate_phase1_unsupported_claims_does_not_mutate_envelope() -> None:
    envelope = build_valid_envelope()
    before = envelope.model_dump(mode="python")

    _ = validate_phase1_unsupported_claims(envelope)

    after = envelope.model_dump(mode="python")
    assert after == before


def test_validate_phase1_unsupported_claims_has_no_pipeline_or_llm_dependencies() -> None:
    import src.validators.unsupported_claims as unsupported_claims_module

    source_code = inspect.getsource(unsupported_claims_module)
    module_ast = ast.parse(source_code)
    import_targets: list[str] = []

    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            import_targets.extend(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module_name = node.module or ""
            import_targets.append(f"{prefix}{module_name}")

    forbidden_prefixes = (
        "src.llm",
        "src.storage",
        "src.pipeline",
        "src.state.write",
        "..llm",
        "..storage",
        "..pipeline",
        "..state.write",
    )

    for forbidden_prefix in forbidden_prefixes:
        assert all(
            not target.startswith(forbidden_prefix) for target in import_targets
        )
