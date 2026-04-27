"""Tests for Phase 1-4 adapter validation bridge."""

from __future__ import annotations

from datetime import datetime

from src.adapters.case_structuring import CaseStructuringDraft
from src.adapters.evidence_atomization import EvidenceAtomizationDraft
from src.adapters.validation_bridge import (
    AdapterValidationBridgeStatus,
    validate_adapter_drafts_against_sources,
    validate_case_structuring_draft_against_sources,
    validate_evidence_atomization_draft_against_sources,
)
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.intake import SourceDocument, SourceDocumentType
from src.schemas.stage import InfoModality, StageType, TriggerType


def _base_source_documents() -> tuple[SourceDocument, ...]:
    return (
        SourceDocument(
            source_doc_id="doc-001",
            case_id="case-001",
            input_event_id="input_event-001",
            document_type=SourceDocumentType.FREE_TEXT_CASE_NOTE,
            raw_text="Patient reports chronic cough for 8 years with exertional dyspnea.",
            created_at=datetime(2026, 4, 27, 9, 0, 0),
        ),
        SourceDocument(
            source_doc_id="doc-002",
            case_id="case-001",
            input_event_id="input_event-002",
            document_type=SourceDocumentType.HRCT_REPORT_TEXT,
            raw_text="HRCT shows reticulation and traction bronchiectasis in lower lobes.",
            created_at=datetime(2026, 4, 27, 9, 15, 0),
        ),
    )


def _build_case_structuring_draft(
    source_documents: tuple[SourceDocument, ...],
) -> CaseStructuringDraft:
    source_doc_by_id = {
        source_document.source_doc_id: source_document
        for source_document in source_documents
    }

    timeline_excerpt = "chronic cough"
    timeline_start = source_doc_by_id["doc-001"].raw_text.index(timeline_excerpt)
    timeline_end = timeline_start + len(timeline_excerpt)

    finding_excerpt = "reticulation and traction bronchiectasis"
    finding_start = source_doc_by_id["doc-002"].raw_text.index(finding_excerpt)
    finding_end = finding_start + len(finding_excerpt)

    return CaseStructuringDraft(
        draft_id="case_struct_draft-bridge-001",
        case_id="case-001",
        source_doc_ids=("doc-001", "doc-002"),
        proposed_stage_context={
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": datetime(2026, 4, 27, 10, 0, 0),
            "available_modalities": (InfoModality.HISTORY, InfoModality.HRCT_TEXT),
            "source_doc_ids": ("doc-001", "doc-002"),
        },
        timeline_items=(
            {
                "timeline_item_id": "timeline_item-bridge-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "event_type": "symptom_onset",
                "event_time_text": "8 years ago",
                "description": "Cough started years earlier.",
                "source_span_start": timeline_start,
                "source_span_end": timeline_end,
            },
        ),
        normalized_findings=(
            {
                "finding_id": "finding-bridge-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-002",
                "finding_key": "reticulation pattern",
                "finding_text": "Reticulation and traction bronchiectasis are noted.",
                "modality": InfoModality.HRCT_TEXT,
                "source_span_start": finding_start,
                "source_span_end": finding_end,
            },
        ),
        candidate_clue_groups=(
            {
                "clue_group_id": "clue_group-bridge-001",
                "stage_id": "stage-001",
                "group_key": "disease_course_clues",
                "finding_ids": ("finding-bridge-001",),
                "summary": "Imaging clues suggest chronic progression.",
            },
        ),
    )


def _build_evidence_atomization_draft(
    source_documents: tuple[SourceDocument, ...],
) -> EvidenceAtomizationDraft:
    source_doc_by_id = {
        source_document.source_doc_id: source_document
        for source_document in source_documents
    }

    evidence_excerpt = "chronic cough for 8 years"
    evidence_start = source_doc_by_id["doc-001"].raw_text.index(evidence_excerpt)
    evidence_end = evidence_start + len(evidence_excerpt)

    return EvidenceAtomizationDraft(
        draft_id="atomization_draft-bridge-001",
        case_id="case-001",
        stage_id="stage-001",
        source_doc_ids=("doc-001", "doc-002"),
        evidence_atoms=(
            {
                "evidence_id": "evd-bridge-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "atom_index": 0,
                "category": EvidenceCategory.SYMPTOM,
                "modality": InfoModality.HISTORY,
                "statement": "Chronic cough is present.",
                "raw_excerpt": evidence_excerpt,
                "polarity": EvidencePolarity.PRESENT,
                "certainty": EvidenceCertainty.REPORTED,
                "temporality": EvidenceTemporality.CURRENT,
                "subject": EvidenceSubject.PATIENT,
                "source_span_start": evidence_start,
                "source_span_end": evidence_end,
            },
        ),
        extraction_activity={
            "activity_id": "activity-bridge-001",
            "stage_id": "stage-001",
            "extraction_method": ExtractionMethod.RULE_BASED,
            "extractor_name": "evidence_atomizer_adapter",
            "extractor_version": "0.1.0",
            "occurred_at": datetime(2026, 4, 27, 10, 5, 0),
            "input_source_doc_ids": ("doc-001", "doc-002"),
        },
    )


def test_valid_case_structuring_draft_passes_source_alignment() -> None:
    source_documents = _base_source_documents()
    draft = _build_case_structuring_draft(source_documents)

    report = validate_case_structuring_draft_against_sources(draft, source_documents)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()


def test_duplicate_source_documents_produce_blocking_issue() -> None:
    source_documents = _base_source_documents()
    duplicate_source_documents = (
        source_documents[0],
        source_documents[1].model_copy(update={"source_doc_id": "doc-001"}),
    )
    draft = _build_case_structuring_draft(source_documents)

    report = validate_case_structuring_draft_against_sources(
        draft,
        duplicate_source_documents,
    )

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "adapter_bridge.duplicate_source_document_id"
        for issue in report.issues
    )


def test_case_draft_source_doc_id_outside_registry_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_case_structuring_draft(source_documents)
    draft.source_doc_ids = ("doc-001", "doc-999")

    report = validate_case_structuring_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "adapter_bridge.case_draft_source_doc_not_registered"
        for issue in report.issues
    )


def test_timeline_span_outside_source_raw_text_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_case_structuring_draft(source_documents)
    draft.timeline_items[0].source_span_end = len(source_documents[0].raw_text) + 100

    report = validate_case_structuring_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "adapter_bridge.timeline_span_out_of_bounds"
        for issue in report.issues
    )


def test_normalized_finding_span_outside_source_raw_text_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_case_structuring_draft(source_documents)
    draft.normalized_findings[0].source_span_end = len(source_documents[1].raw_text) + 100

    report = validate_case_structuring_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "adapter_bridge.finding_span_out_of_bounds"
        for issue in report.issues
    )


def test_valid_evidence_atomization_draft_passes_raw_excerpt_source_alignment() -> None:
    source_documents = _base_source_documents()
    draft = _build_evidence_atomization_draft(source_documents)

    report = validate_evidence_atomization_draft_against_sources(draft, source_documents)

    assert report.is_valid is True
    assert report.has_blocking_issue is False
    assert report.issues == ()


def test_evidence_raw_excerpt_not_found_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_evidence_atomization_draft(source_documents)
    draft.evidence_atoms[0].source_span_start = None
    draft.evidence_atoms[0].source_span_end = None
    draft.evidence_atoms[0].raw_excerpt = "new symptom not in source"

    report = validate_evidence_atomization_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.raw_excerpt_not_found" for issue in report.issues
    )


def test_evidence_span_excerpt_mismatch_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_evidence_atomization_draft(source_documents)
    draft.evidence_atoms[0].raw_excerpt = "chronic cough"

    report = validate_evidence_atomization_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.source_span_excerpt_mismatch"
        for issue in report.issues
    )


def test_evidence_source_doc_id_outside_registry_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_evidence_atomization_draft(source_documents)
    draft.evidence_atoms[0].source_doc_id = "doc-999"

    report = validate_evidence_atomization_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code == "provenance.source_doc_not_registered"
        for issue in report.issues
    )


def test_extraction_activity_coverage_gap_produces_blocking_issue() -> None:
    source_documents = _base_source_documents()
    draft = _build_evidence_atomization_draft(source_documents)
    draft.extraction_activity.input_source_doc_ids = ("doc-001",)

    report = validate_evidence_atomization_draft_against_sources(draft, source_documents)

    assert report.has_blocking_issue is True
    assert any(
        issue.issue_code
        == "adapter_bridge.evidence_extraction_activity_source_doc_coverage_gap"
        for issue in report.issues
    )


def test_combined_bridge_passed_when_both_reports_pass() -> None:
    source_documents = _base_source_documents()
    case_draft = _build_case_structuring_draft(source_documents)
    evidence_draft = _build_evidence_atomization_draft(source_documents)

    result = validate_adapter_drafts_against_sources(
        case_structuring_draft=case_draft,
        evidence_atomization_draft=evidence_draft,
        source_documents=source_documents,
    )

    assert result.status is AdapterValidationBridgeStatus.PASSED
    assert result.has_blocking_issue is False
    assert result.case_structuring_report is not None
    assert result.evidence_atomization_report is not None
    assert result.case_structuring_report.has_blocking_issue is False
    assert result.evidence_atomization_report.has_blocking_issue is False


def test_combined_bridge_failed_when_either_report_has_blocking_issue() -> None:
    source_documents = _base_source_documents()
    case_draft = _build_case_structuring_draft(source_documents)
    evidence_draft = _build_evidence_atomization_draft(source_documents)
    evidence_draft.evidence_atoms[0].source_span_start = None
    evidence_draft.evidence_atoms[0].source_span_end = None
    evidence_draft.evidence_atoms[0].raw_excerpt = "text outside source"

    result = validate_adapter_drafts_against_sources(
        case_structuring_draft=case_draft,
        evidence_atomization_draft=evidence_draft,
        source_documents=source_documents,
    )

    assert result.status is AdapterValidationBridgeStatus.FAILED
    assert result.has_blocking_issue is True
    assert result.case_structuring_report is not None
    assert result.evidence_atomization_report is not None
    assert result.evidence_atomization_report.has_blocking_issue is True


def test_combined_bridge_failed_when_no_drafts_are_provided() -> None:
    source_documents = _base_source_documents()

    result = validate_adapter_drafts_against_sources(
        source_documents=source_documents,
    )

    assert result.status is AdapterValidationBridgeStatus.FAILED
    assert result.has_blocking_issue is True
    assert result.case_structuring_report is None
    assert result.evidence_atomization_report is None
    assert "No adapter draft provided" in result.summary