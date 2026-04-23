"""Tests for Phase 1-2 provenance checker."""

from __future__ import annotations

from datetime import datetime

from src.provenance.checker import check_phase1_provenance
from src.provenance.model import SourceAnchor
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
from src.schemas.state import Phase1StateEnvelope


def build_valid_envelope() -> Phase1StateEnvelope:
    """Build one fully aligned envelope with complete provenance payloads."""

    created_at = datetime(2026, 4, 23, 16, 0, 0)

    payload: dict[str, object] = {
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
                "provenance": {
                    "evidence_provenance_id": "eprov-001",
                    "stage_id": "stage-001",
                    "evidence_id": "evd-001",
                    "source_anchors": [
                        {
                            "anchor_id": "anchor-001",
                            "stage_id": "stage-001",
                            "source_doc_id": "doc-001",
                            "modality": InfoModality.HRCT_TEXT,
                            "raw_excerpt": "Subpleural reticulation",
                            "span_start": 0,
                            "span_end": 22,
                        }
                    ],
                    "extraction_activity": {
                        "activity_id": "activity-001",
                        "stage_id": "stage-001",
                        "extraction_method": "llm_structured",
                        "extractor_name": "evidence_atomizer",
                        "extractor_version": "v1",
                        "occurred_at": created_at,
                        "input_source_doc_ids": ["doc-001"],
                    },
                },
            }
        ],
        "claim_references": [
            {
                "claim_ref_id": "claim_ref-001",
                "stage_id": "stage-001",
                "target_kind": ClaimTargetKind.HYPOTHESIS,
                "target_id": "hyp-001",
                "claim_text": "Imaging supports fibrotic ILD hypothesis.",
                "relation": ClaimRelation.SUPPORTS,
                "evidence_ids": ["evd-001"],
                "provenance": {
                    "claim_provenance_id": "cprov-001",
                    "stage_id": "stage-001",
                    "claim_ref_id": "claim_ref-001",
                    "evidence_ids": ["evd-001"],
                    "evidence_provenance_ids": ["eprov-001"],
                    "derivation_activity": {
                        "activity_id": "activity-002",
                        "stage_id": "stage-001",
                        "extraction_method": "llm_structured",
                        "extractor_name": "claim_builder",
                        "extractor_version": "v1",
                        "occurred_at": created_at,
                        "input_source_doc_ids": ["doc-001"],
                    },
                },
            },
            {
                "claim_ref_id": "claim_ref-002",
                "stage_id": "stage-001",
                "target_kind": ClaimTargetKind.ACTION,
                "target_id": "action-001",
                "claim_text": "Current evidence supports ordering PFT.",
                "relation": ClaimRelation.SUPPORTS,
                "evidence_ids": ["evd-001"],
                "provenance": {
                    "claim_provenance_id": "cprov-002",
                    "stage_id": "stage-001",
                    "claim_ref_id": "claim_ref-002",
                    "evidence_ids": ["evd-001"],
                    "evidence_provenance_ids": ["eprov-001"],
                    "derivation_activity": {
                        "activity_id": "activity-003",
                        "stage_id": "stage-001",
                        "extraction_method": "llm_structured",
                        "extractor_name": "claim_builder",
                        "extractor_version": "v1",
                        "occurred_at": created_at,
                        "input_source_doc_ids": ["doc-001"],
                    },
                },
            },
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
                "supporting_claim_ref_ids": ["claim_ref-002"],
                "refuting_claim_ref_ids": [],
                "missing_information_claim_ref_ids": [],
                "safety_concern_claim_ref_ids": [],
            }
        ],
        "validation_report": None,
        "state_id": "state-001",
        "state_version": 1,
        "parent_state_id": None,
        "created_at": created_at,
    }

    return Phase1StateEnvelope(**payload)


def test_checker_returns_no_issue_for_fully_aligned_provenance() -> None:
    envelope = build_valid_envelope()

    issues = check_phase1_provenance(envelope, require_provenance=True)

    assert issues == ()


def test_checker_reports_missing_provenance_as_warning_by_default() -> None:
    envelope = build_valid_envelope()
    envelope.evidence_atoms[0].provenance = None
    envelope.claim_references[0].provenance = None

    issues = check_phase1_provenance(envelope)

    missing_issues = [
        issue for issue in issues if issue.issue_code == "provenance.missing_provenance"
    ]
    assert len(missing_issues) == 2
    assert all(issue.blocking is False for issue in missing_issues)


def test_checker_reports_missing_provenance_as_blocking_when_required() -> None:
    envelope = build_valid_envelope()
    envelope.evidence_atoms[0].provenance = None

    issues = check_phase1_provenance(envelope, require_provenance=True)

    missing_issues = [
        issue for issue in issues if issue.issue_code == "provenance.missing_provenance"
    ]
    assert len(missing_issues) == 1
    assert missing_issues[0].blocking is True


def test_checker_reports_source_span_completeness_and_ordering() -> None:
    envelope = build_valid_envelope()

    incomplete_anchor = SourceAnchor.model_construct(
        kind="source_anchor",
        anchor_id="anchor-001",
        stage_id="stage-001",
        source_doc_id="doc-001",
        modality=InfoModality.HRCT_TEXT,
        raw_excerpt="span incomplete",
        section_label=None,
        span_start=3,
        span_end=None,
    )
    reversed_anchor = SourceAnchor.model_construct(
        kind="source_anchor",
        anchor_id="anchor-002",
        stage_id="stage-001",
        source_doc_id="doc-001",
        modality=InfoModality.HRCT_TEXT,
        raw_excerpt="span reversed",
        section_label=None,
        span_start=9,
        span_end=2,
    )
    envelope.evidence_atoms[0].provenance.source_anchors = (
        incomplete_anchor,
        reversed_anchor,
    )

    issues = check_phase1_provenance(envelope, require_provenance=True)
    issue_codes = {issue.issue_code for issue in issues}

    assert "provenance.source_span_incomplete" in issue_codes
    assert "provenance.source_span_order_invalid" in issue_codes


def test_checker_reports_stage_alignment_case_alignment_and_doc_visibility() -> None:
    envelope = build_valid_envelope()
    envelope.stage_context.case_id = "case-other"
    envelope.evidence_atoms[0].provenance.stage_id = "stage-002"
    envelope.evidence_atoms[0].provenance.extraction_activity.input_source_doc_ids = (
        "doc-999",
    )

    issues = check_phase1_provenance(envelope, require_provenance=True)
    issue_codes = {issue.issue_code for issue in issues}

    assert "provenance.case_alignment_mismatch" in issue_codes
    assert "provenance.stage_alignment_mismatch" in issue_codes
    assert "provenance.source_doc_not_visible" in issue_codes


def test_checker_reports_claim_consistency_and_orphan_references() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance.evidence_ids = ("evd-001", "evd-999")
    envelope.claim_references[0].provenance.evidence_provenance_ids = ("eprov-999",)

    issues = check_phase1_provenance(envelope, require_provenance=True)
    issue_codes = {issue.issue_code for issue in issues}

    assert "provenance.claim_evidence_mismatch" in issue_codes
    assert "provenance.orphan_evidence_reference" in issue_codes
    assert "provenance.orphan_evidence_provenance_reference" in issue_codes


def test_checker_reports_orphan_provenance_when_unreferenced() -> None:
    envelope = build_valid_envelope()
    envelope.claim_references[0].provenance.evidence_provenance_ids = ()
    envelope.claim_references[1].provenance.evidence_provenance_ids = ()

    issues = check_phase1_provenance(envelope, require_provenance=True)
    orphan_issues = [
        issue for issue in issues if issue.issue_code == "provenance.orphan_provenance"
    ]

    assert len(orphan_issues) == 1
    assert orphan_issues[0].blocking is False
