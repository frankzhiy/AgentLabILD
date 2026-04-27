"""Smoke tests for Phase 1-4 raw intake to adapter validation bridge flow."""

from __future__ import annotations

import ast
import inspect
import sys
from datetime import datetime

from src.adapters.case_structuring import CaseStructuringDraft
from src.adapters.validation_bridge import (
    AdapterValidationBridgeStatus,
    validate_adapter_drafts_against_sources,
)
from src.agents.case_structurer import (
    CaseStructurerInput,
    CaseStructurerStatus,
    parse_case_structurer_payload,
)
from src.agents.evidence_atomizer import (
    EvidenceAtomizerInput,
    EvidenceAtomizerStatus,
    parse_evidence_atomizer_payload,
)
from src.intake.intake_gate import attempt_raw_intake
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.intake import RawInputMode, RawIntakeStatus, SourceDocument, SourceDocumentType
from src.schemas.stage import InfoModality, StageType, TriggerType

CASE_ID = "case-smoke-001"
STAGE_ID = "stage-smoke-001"
RAW_CASE_NOTE = (
    "Patient reports chronic cough for 8 years. "
    "HRCT text notes basal reticulation."
)
INTAKE_RECEIVED_AT = datetime(2026, 4, 27, 8, 0, 0)
STAGE_CREATED_AT = datetime(2026, 4, 27, 8, 30, 0)
EXTRACTION_OCCURRED_AT = datetime(2026, 4, 27, 8, 35, 0)


def _accepted_source_documents_from_raw_intake() -> tuple[SourceDocument, ...]:
    decision = attempt_raw_intake(
        case_id=CASE_ID,
        raw_text=RAW_CASE_NOTE,
        input_mode=RawInputMode.INITIAL_SUBMISSION,
        arrival_index=0,
        received_at=INTAKE_RECEIVED_AT,
        document_type=SourceDocumentType.FREE_TEXT_CASE_NOTE,
    )

    assert decision.status is RawIntakeStatus.ACCEPTED
    assert decision.source_document is not None

    source_documents = (decision.source_document,)
    assert len(source_documents) == 1
    return source_documents


def _build_case_structurer_input(
    source_documents: tuple[SourceDocument, ...],
) -> CaseStructurerInput:
    return CaseStructurerInput(
        case_id=CASE_ID,
        source_documents=source_documents,
        stage_id=STAGE_ID,
        stage_index=0,
        stage_type=StageType.INITIAL_REVIEW,
        trigger_type=TriggerType.INITIAL_PRESENTATION,
        created_at=STAGE_CREATED_AT,
    )


def _build_case_structurer_payload(source_document: SourceDocument) -> dict[str, object]:
    timeline_excerpt = "chronic cough for 8 years"
    finding_excerpt = "basal reticulation"

    timeline_start = source_document.raw_text.index(timeline_excerpt)
    timeline_end = timeline_start + len(timeline_excerpt)
    finding_start = source_document.raw_text.index(finding_excerpt)
    finding_end = finding_start + len(finding_excerpt)

    return {
        "draft_id": "case_struct_draft-smoke-001",
        "case_id": CASE_ID,
        "source_doc_ids": (source_document.source_doc_id,),
        "proposed_stage_context": {
            "stage_id": STAGE_ID,
            "case_id": CASE_ID,
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": STAGE_CREATED_AT,
            "available_modalities": (
                InfoModality.HISTORY,
                InfoModality.HRCT_TEXT,
            ),
            "source_doc_ids": (source_document.source_doc_id,),
        },
        "timeline_items": (
            {
                "timeline_item_id": "timeline_item-smoke-001",
                "stage_id": STAGE_ID,
                "source_doc_id": source_document.source_doc_id,
                "event_type": "symptom_onset",
                "event_time_text": "8 years ago",
                "description": "Chronic cough began years earlier.",
                "source_span_start": timeline_start,
                "source_span_end": timeline_end,
            },
        ),
        "normalized_findings": (
            {
                "finding_id": "finding-smoke-001",
                "stage_id": STAGE_ID,
                "source_doc_id": source_document.source_doc_id,
                "finding_key": "basal reticulation",
                "finding_text": "Basal reticulation is present on HRCT text.",
                "modality": InfoModality.HRCT_TEXT,
                "source_span_start": finding_start,
                "source_span_end": finding_end,
            },
        ),
        "candidate_clue_groups": (
            {
                "clue_group_id": "clue_group-smoke-001",
                "stage_id": STAGE_ID,
                "group_key": "disease_course_clues",
                "finding_ids": ("finding-smoke-001",),
                "summary": "Timeline and imaging support chronic disease course clues.",
            },
        ),
    }


def _accepted_case_structuring_draft(
    source_documents: tuple[SourceDocument, ...],
) -> CaseStructuringDraft:
    case_input = _build_case_structurer_input(source_documents)
    case_payload = _build_case_structurer_payload(source_documents[0])
    case_result = parse_case_structurer_payload(case_payload, case_input)

    assert case_result.status is CaseStructurerStatus.ACCEPTED
    assert case_result.draft is not None
    return case_result.draft


def _build_evidence_atomizer_input(
    source_documents: tuple[SourceDocument, ...],
    case_structuring_draft: CaseStructuringDraft,
) -> EvidenceAtomizerInput:
    return EvidenceAtomizerInput(
        case_id=CASE_ID,
        stage_id=STAGE_ID,
        source_documents=source_documents,
        stage_context=case_structuring_draft.proposed_stage_context,
        case_structuring_draft=case_structuring_draft,
        extraction_activity_id="activity-smoke-001",
        occurred_at=EXTRACTION_OCCURRED_AT,
    )


def _build_evidence_atomizer_payload(
    source_document: SourceDocument,
    *,
    raw_excerpt: str,
    include_source_span: bool,
) -> dict[str, object]:
    source_span_start: int | None = None
    source_span_end: int | None = None
    if include_source_span:
        source_span_start = source_document.raw_text.index(raw_excerpt)
        source_span_end = source_span_start + len(raw_excerpt)

    return {
        "draft_id": "atomization_draft-smoke-001",
        "case_id": CASE_ID,
        "stage_id": STAGE_ID,
        "source_doc_ids": (source_document.source_doc_id,),
        "evidence_atoms": (
            {
                "evidence_id": "evd-smoke-001",
                "stage_id": STAGE_ID,
                "source_doc_id": source_document.source_doc_id,
                "atom_index": 0,
                "category": EvidenceCategory.SYMPTOM,
                "modality": InfoModality.HISTORY,
                "statement": "Chronic cough is present.",
                "raw_excerpt": raw_excerpt,
                "polarity": EvidencePolarity.PRESENT,
                "certainty": EvidenceCertainty.REPORTED,
                "temporality": EvidenceTemporality.CURRENT,
                "subject": EvidenceSubject.PATIENT,
                "source_span_start": source_span_start,
                "source_span_end": source_span_end,
            },
        ),
        "extraction_activity": {
            "activity_id": "activity-smoke-001",
            "stage_id": STAGE_ID,
            "extraction_method": ExtractionMethod.RULE_BASED,
            "extractor_name": "evidence_atomizer_adapter",
            "extractor_version": "0.1.0",
            "occurred_at": EXTRACTION_OCCURRED_AT,
            "input_source_doc_ids": (source_document.source_doc_id,),
        },
    }


def test_phase1_4_smoke_flow_raw_intake_to_adapter_validation_bridge() -> None:
    source_documents = _accepted_source_documents_from_raw_intake()
    assert len(source_documents) == 1

    case_input = _build_case_structurer_input(source_documents)
    case_payload = _build_case_structurer_payload(source_documents[0])
    case_result = parse_case_structurer_payload(case_payload, case_input)

    assert case_result.status is CaseStructurerStatus.ACCEPTED
    assert case_result.draft is not None

    evidence_input = _build_evidence_atomizer_input(
        source_documents,
        case_result.draft,
    )
    evidence_payload = _build_evidence_atomizer_payload(
        source_documents[0],
        raw_excerpt="chronic cough for 8 years",
        include_source_span=True,
    )
    evidence_result = parse_evidence_atomizer_payload(evidence_payload, evidence_input)

    assert evidence_result.status is EvidenceAtomizerStatus.ACCEPTED
    assert evidence_result.draft is not None

    bridge_result = validate_adapter_drafts_against_sources(
        case_structuring_draft=case_result.draft,
        evidence_atomization_draft=evidence_result.draft,
        source_documents=source_documents,
    )

    assert bridge_result.status is AdapterValidationBridgeStatus.PASSED
    assert bridge_result.has_blocking_issue is False
    assert bridge_result.case_structuring_report is not None
    assert bridge_result.evidence_atomization_report is not None


def test_phase1_4_smoke_flow_rejects_case_payload_with_final_diagnosis_before_bridge() -> None:
    source_documents = _accepted_source_documents_from_raw_intake()
    case_input = _build_case_structurer_input(source_documents)
    case_payload = _build_case_structurer_payload(source_documents[0])
    case_payload["final_diagnosis"] = "IPF"

    case_result = parse_case_structurer_payload(case_payload, case_input)

    assert case_result.status is CaseStructurerStatus.REJECTED
    assert case_result.draft is None
    assert any("final_diagnosis" in error for error in case_result.errors)


def test_phase1_4_smoke_flow_rejects_evidence_payload_with_hypotheses_or_action_candidates_before_bridge() -> None:
    source_documents = _accepted_source_documents_from_raw_intake()
    case_structuring_draft = _accepted_case_structuring_draft(source_documents)
    evidence_input = _build_evidence_atomizer_input(
        source_documents,
        case_structuring_draft,
    )
    evidence_payload = _build_evidence_atomizer_payload(
        source_documents[0],
        raw_excerpt="chronic cough for 8 years",
        include_source_span=True,
    )
    evidence_payload["hypotheses"] = ("hyp-001",)
    evidence_payload["action_candidates"] = ("action-001",)

    evidence_result = parse_evidence_atomizer_payload(evidence_payload, evidence_input)

    assert evidence_result.status is EvidenceAtomizerStatus.REJECTED
    assert evidence_result.draft is None
    assert any("hypotheses" in error for error in evidence_result.errors)
    assert any("action_candidates" in error for error in evidence_result.errors)


def test_phase1_4_smoke_flow_bridge_blocks_raw_excerpt_not_found() -> None:
    source_documents = _accepted_source_documents_from_raw_intake()
    case_structuring_draft = _accepted_case_structuring_draft(source_documents)
    evidence_input = _build_evidence_atomizer_input(
        source_documents,
        case_structuring_draft,
    )
    evidence_payload = _build_evidence_atomizer_payload(
        source_documents[0],
        raw_excerpt="excerpt_not_present_in_source_document",
        include_source_span=False,
    )

    evidence_result = parse_evidence_atomizer_payload(evidence_payload, evidence_input)

    assert evidence_result.status is EvidenceAtomizerStatus.ACCEPTED
    assert evidence_result.draft is not None

    bridge_result = validate_adapter_drafts_against_sources(
        evidence_atomization_draft=evidence_result.draft,
        source_documents=source_documents,
    )

    assert bridge_result.status is AdapterValidationBridgeStatus.FAILED
    assert bridge_result.has_blocking_issue is True
    assert bridge_result.evidence_atomization_report is not None
    assert any(
        issue.issue_code == "provenance.raw_excerpt_not_found" and issue.blocking
        for issue in bridge_result.evidence_atomization_report.issues
    )


def test_phase1_4_smoke_flow_module_does_not_import_or_call_state_writer_or_sink() -> None:
    source_code = inspect.getsource(sys.modules[__name__])
    module_ast = ast.parse(source_code)
    import_targets: list[str] = []
    called_symbol_names: set[str] = set()

    for node in ast.walk(module_ast):
        if isinstance(node, ast.Import):
            import_targets.extend(alias.name for alias in node.names)
            continue

        if isinstance(node, ast.ImportFrom):
            prefix = "." * node.level
            module_name = node.module or ""
            import_targets.append(f"{prefix}{module_name}")

        if isinstance(node, ast.Call):
            if isinstance(node.func, ast.Name):
                called_symbol_names.add(node.func.id)
                continue

            if isinstance(node.func, ast.Attribute):
                called_symbol_names.add(node.func.attr)

    forbidden_prefixes = (
        "src.state",
        "src.storage",
    )

    for forbidden_prefix in forbidden_prefixes:
        assert all(not target.startswith(forbidden_prefix) for target in import_targets)

    assert "attempt_phase1_write" not in called_symbol_names
    assert "StateWriter" not in called_symbol_names
