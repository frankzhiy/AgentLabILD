"""Tests for Phase 1-1 StateValidationReport and Phase1StateEnvelope schemas."""

from __future__ import annotations

from copy import deepcopy
from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.action import ActionStatus, ActionType, ActionUrgency
from src.schemas.board import BoardInitSource, BoardStatus
from src.schemas.claim import ClaimRelation, ClaimTargetKind
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.hypothesis import HypothesisConfidenceLevel, HypothesisStatus
from src.schemas.stage import InfoModality, StageType, TriggerType
from src.schemas.state import (
    Phase1StateEnvelope,
    StateValidationReport as ExportedStateValidationReport,
    ValidationIssue as ExportedValidationIssue,
    ValidationSeverity as ExportedValidationSeverity,
    ValidationTargetKind as ExportedValidationTargetKind,
)
from src.schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)


def _base_payload() -> dict[str, object]:
    created_at = datetime(2026, 4, 23, 14, 0, 0)

    return {
        "case_id": "case-abc",
        "stage_context": {
            "stage_id": "stage-001",
            "case_id": "case-abc",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": created_at,
            "parent_stage_id": None,
            "available_modalities": [InfoModality.HRCT_TEXT],
            "source_doc_ids": ["doc-001"],
        },
        "board_init": {
            "board_id": "board-001",
            "case_id": "case-abc",
            "stage_id": "stage-001",
            "board_status": BoardStatus.INITIALIZED,
            "init_source": BoardInitSource.STAGE_BOOTSTRAP,
            "initialized_at": created_at,
            "evidence_ids": ["evd-001"],
            "hypothesis_ids": ["hyp-001"],
            "action_candidate_ids": ["action-001"],
            "ranked_hypothesis_ids": ["hyp-001"],
            "parent_board_id": None,
        },
        "evidence_atoms": [
            {
                "evidence_id": "evd-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "atom_index": 0,
                "category": EvidenceCategory.IMAGING_FINDING,
                "modality": InfoModality.HRCT_TEXT,
                "statement": "Subpleural reticulation is present.",
                "raw_excerpt": "HRCT: Subpleural reticulation is present.",
                "polarity": EvidencePolarity.PRESENT,
                "certainty": EvidenceCertainty.CONFIRMED,
                "temporality": EvidenceTemporality.CURRENT,
                "subject": EvidenceSubject.PATIENT,
            }
        ],
        "claim_references": [
            {
                "claim_ref_id": "claim_ref-001",
                "stage_id": "stage-001",
                "target_kind": ClaimTargetKind.HYPOTHESIS,
                "target_id": "hyp-001",
                "claim_text": "Imaging pattern supports fibrotic ILD hypothesis.",
                "relation": ClaimRelation.SUPPORTS,
                "evidence_ids": ["evd-001"],
            }
        ],
        "hypotheses": [
            {
                "hypothesis_id": "hyp-001",
                "stage_id": "stage-001",
                "hypothesis_label": "Fibrotic ILD pattern",
                "status": HypothesisStatus.UNDER_CONSIDERATION,
                "confidence_level": HypothesisConfidenceLevel.LOW,
                "supporting_claim_ref_ids": ["claim_ref-001"],
                "refuting_claim_ref_ids": [],
                "missing_information_claim_ref_ids": [],
            }
        ],
        "action_candidates": [
            {
                "action_candidate_id": "action-001",
                "stage_id": "stage-001",
                "action_type": ActionType.ORDER_DIAGNOSTIC_TEST,
                "action_text": "Order repeat PFT with DLCO.",
                "status": ActionStatus.PRIORITIZED,
                "urgency": ActionUrgency.EXPEDITED,
                "linked_hypothesis_ids": ["hyp-001"],
                "supporting_claim_ref_ids": ["claim_ref-001"],
                "refuting_claim_ref_ids": [],
                "missing_information_claim_ref_ids": [],
                "safety_concern_claim_ref_ids": [],
            }
        ],
        "validation_report": {
            "report_id": "report-001",
            "case_id": "case-abc",
            "stage_id": "stage-001",
            "board_id": "board-001",
            "generated_at": created_at,
            "is_valid": True,
            "has_blocking_issue": False,
            "issues": [],
            "validator_name": "phase1_external_validator",
            "validator_version": "1.0.0",
            "summary": "No blocking issue found.",
        },
        "state_version": 1,
        "parent_state_id": None,
        "created_at": created_at,
    }


def test_state_validation_report_valid_construction() -> None:
    report = StateValidationReport(
        report_id="report-002",
        case_id="case-abc",
        stage_id="stage-001",
        board_id="board-001",
        generated_at=datetime(2026, 4, 23, 14, 0, 0),
        is_valid=False,
        has_blocking_issue=True,
        issues=(
            ValidationIssue(
                issue_id="issue-001",
                issue_code="stage_id_alignment",
                severity=ValidationSeverity.ERROR,
                message="stage_id mismatch",
                target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                target_id="evd-001",
                field_path="evidence_atoms[0].stage_id",
                related_ids=("evd-001",),
                blocking=True,
                suggested_fix="align evidence_atoms[0].stage_id with stage_context.stage_id",
            ),
        ),
        validator_name="phase1_external_validator",
        validator_version="1.0.0",
        summary="Blocking mismatch detected.",
    )

    assert report.is_valid is False
    assert report.has_blocking_issue is True
    assert report.issues[0].severity is ValidationSeverity.ERROR
    assert report.issues[0].target_kind is ValidationTargetKind.EVIDENCE_ATOM


def test_state_validation_report_rejects_valid_flag_with_error_issue() -> None:
    with pytest.raises(ValidationError):
        StateValidationReport(
            report_id="report-003",
            case_id="case-abc",
            stage_id="stage-001",
            board_id="board-001",
            generated_at=datetime(2026, 4, 23, 14, 0, 0),
            is_valid=True,
            has_blocking_issue=True,
            issues=(
                ValidationIssue(
                    issue_id="issue-002",
                    issue_code="missing_claim_reference",
                    severity=ValidationSeverity.ERROR,
                    message="claim_ref-999 was not found",
                    target_kind=ValidationTargetKind.HYPOTHESIS_STATE,
                    target_id="hyp-001",
                    blocking=True,
                ),
            ),
            validator_name="phase1_external_validator",
            validator_version="1.0.0",
        )


def test_state_validation_report_rejects_invalid_without_issues() -> None:
    with pytest.raises(ValidationError):
        StateValidationReport(
            report_id="report-004",
            case_id="case-abc",
            stage_id="stage-001",
            board_id="board-001",
            generated_at=datetime(2026, 4, 23, 14, 0, 0),
            is_valid=False,
            has_blocking_issue=False,
            issues=(),
            validator_name="phase1_external_validator",
            validator_version="1.0.0",
        )


def test_validation_issue_rejects_duplicate_related_ids() -> None:
    with pytest.raises(ValidationError):
        ValidationIssue(
            issue_id="issue-010",
            issue_code="duplicate_related_ids",
            severity=ValidationSeverity.WARNING,
            message="related_ids duplicates are not allowed",
            target_kind=ValidationTargetKind.CLAIM_REFERENCE,
            target_id="claim_ref-001",
            related_ids=("claim_ref-001", "claim_ref-001"),
            blocking=False,
        )


def test_validation_issue_rejects_malformed_issue_code() -> None:
    with pytest.raises(ValidationError):
        ValidationIssue(
            issue_id="issue-011",
            issue_code="Invalid Issue Code",
            severity=ValidationSeverity.INFO,
            message="bad issue code format",
            target_kind=ValidationTargetKind.OTHER,
            target_id="obj-001",
            blocking=False,
        )


def test_state_validation_report_rejects_duplicate_issue_ids() -> None:
    issue_a = ValidationIssue(
        issue_id="issue-020",
        issue_code="minor_alignment_notice",
        severity=ValidationSeverity.WARNING,
        message="alignment warning A",
        target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
        target_id="state-001",
        blocking=False,
    )
    issue_b = ValidationIssue(
        issue_id="issue-020",
        issue_code="minor_alignment_notice_b",
        severity=ValidationSeverity.WARNING,
        message="alignment warning B",
        target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
        target_id="state-001",
        blocking=False,
    )

    with pytest.raises(ValidationError):
        StateValidationReport(
            report_id="report-005",
            case_id="case-abc",
            stage_id="stage-001",
            board_id="board-001",
            generated_at=datetime(2026, 4, 23, 14, 0, 0),
            is_valid=False,
            has_blocking_issue=False,
            issues=(issue_a, issue_b),
            validator_name="phase1_external_validator",
            validator_version="1.0.0",
        )


def test_phase1_state_envelope_valid_construction() -> None:
    envelope = Phase1StateEnvelope(**_base_payload())

    assert envelope.case_id == "case-abc"
    assert envelope.stage_context.stage_id == "stage-001"
    assert envelope.validation_report is not None
    assert envelope.validation_report.is_valid is True
    assert envelope.state_version == 1


def test_phase1_state_envelope_allows_validation_report_none() -> None:
    payload = _base_payload()
    payload["validation_report"] = None

    envelope = Phase1StateEnvelope(**payload)

    assert envelope.validation_report is None


def test_phase1_state_envelope_rejects_stage_id_misalignment() -> None:
    payload = _base_payload()
    payload["evidence_atoms"][0]["stage_id"] = "stage-002"

    with pytest.raises(ValidationError) as exc:
        Phase1StateEnvelope(**payload)

    assert "stage_id alignment failed" in str(exc.value)


def test_phase1_state_envelope_rejects_duplicate_ids() -> None:
    payload = _base_payload()
    duplicate_atom = deepcopy(payload["evidence_atoms"][0])
    duplicate_atom["atom_index"] = 1
    payload["evidence_atoms"].append(duplicate_atom)

    with pytest.raises(ValidationError) as exc:
        Phase1StateEnvelope(**payload)

    assert "duplicate ids in evidence_atoms" in str(exc.value)


def test_phase1_state_envelope_rejects_missing_claim_references() -> None:
    payload = _base_payload()
    payload["hypotheses"][0]["supporting_claim_ref_ids"] = ["claim_ref-999"]

    with pytest.raises(ValidationError) as exc:
        Phase1StateEnvelope(**payload)

    assert "missing claim references" in str(exc.value)


def test_phase1_state_envelope_rejects_missing_evidence_references() -> None:
    payload = _base_payload()
    payload["claim_references"][0]["evidence_ids"] = ["evd-999"]

    with pytest.raises(ValidationError) as exc:
        Phase1StateEnvelope(**payload)

    assert "missing evidence references" in str(exc.value)


def test_phase1_state_envelope_rejects_ranked_hypothesis_not_in_hypotheses() -> None:
    payload = _base_payload()
    payload["board_init"]["hypothesis_ids"] = ["hyp-001", "hyp-999"]
    payload["board_init"]["ranked_hypothesis_ids"] = ["hyp-999"]

    with pytest.raises(ValidationError) as exc:
        Phase1StateEnvelope(**payload)

    assert "ranked hypothesis ids not found in hypotheses" in str(exc.value)


def test_state_module_exports_validation_types() -> None:
    assert ExportedValidationSeverity is ValidationSeverity
    assert ExportedValidationIssue is ValidationIssue
    assert ExportedStateValidationReport is StateValidationReport
    assert ExportedValidationTargetKind is ValidationTargetKind
