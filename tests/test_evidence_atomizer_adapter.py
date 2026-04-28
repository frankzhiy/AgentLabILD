"""Tests for Phase 1-4 Evidence Atomizer adapter behavior."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.agents.evidence_atomizer import (
    EvidenceAtomizerInput,
    EvidenceAtomizerStatus,
    build_evidence_atomizer_prompt,
    parse_evidence_atomizer_payload,
)
from src.provenance.model import ExtractionMethod
from src.schemas.evidence import (
    EvidenceCategory,
    EvidenceCertainty,
    EvidencePolarity,
    EvidenceSubject,
    EvidenceTemporality,
)
from src.schemas.intake import SourceDocumentType
from src.schemas.stage import InfoModality, StageType, TriggerType


def _base_case_structuring_draft_payload() -> dict[str, object]:
    return {
        "draft_id": "case_struct_draft-001",
        "case_id": "case-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "proposed_stage_context": {
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": datetime(2026, 4, 27, 10, 0, 0),
            "available_modalities": (InfoModality.HISTORY, InfoModality.HRCT_TEXT),
            "source_doc_ids": ("doc-001", "doc-002"),
        },
        "timeline_items": (
            {
                "timeline_item_id": "timeline_item-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "event_type": "symptom_onset",
                "event_time_text": "8 years ago",
                "description": "Chronic cough began.",
                "source_span_start": 0,
                "source_span_end": 25,
            },
        ),
        "normalized_findings": (
            {
                "finding_id": "finding-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-002",
                "finding_key": "reticulation pattern",
                "finding_text": "Reticulation with traction bronchiectasis.",
                "modality": InfoModality.HRCT_TEXT,
                "source_span_start": 0,
                "source_span_end": 43,
            },
        ),
        "candidate_clue_groups": (
            {
                "clue_group_id": "clue_group-001",
                "stage_id": "stage-001",
                "group_key": "disease_course_clues",
                "finding_ids": ("finding-001",),
                "summary": "Findings suggest chronic progressive course clues.",
            },
        ),
    }


def _base_input(*, with_case_structuring_draft: bool = False) -> EvidenceAtomizerInput:
    payload: dict[str, object] = {
        "case_id": "case-001",
        "stage_id": "stage-001",
        "source_documents": (
            {
                "source_doc_id": "doc-001",
                "case_id": "case-001",
                "input_event_id": "input_event-001",
                "document_type": SourceDocumentType.FREE_TEXT_CASE_NOTE,
                "raw_text": "Patient has chronic cough for 8 years.",
                "created_at": datetime(2026, 4, 27, 9, 0, 0),
            },
            {
                "source_doc_id": "doc-002",
                "case_id": "case-001",
                "input_event_id": "input_event-002",
                "document_type": SourceDocumentType.HRCT_REPORT_TEXT,
                "raw_text": "HRCT text mentions reticulation and traction bronchiectasis.",
                "created_at": datetime(2026, 4, 27, 9, 30, 0),
            },
        ),
        "stage_context": {
            "stage_id": "stage-001",
            "case_id": "case-001",
            "stage_index": 0,
            "stage_type": StageType.INITIAL_REVIEW,
            "trigger_type": TriggerType.INITIAL_PRESENTATION,
            "created_at": datetime(2026, 4, 27, 10, 0, 0),
            "available_modalities": (InfoModality.HISTORY, InfoModality.HRCT_TEXT),
            "source_doc_ids": ("doc-001", "doc-002"),
        },
        "extraction_activity_id": "activity-001",
        "occurred_at": datetime(2026, 4, 27, 10, 5, 0),
    }

    if with_case_structuring_draft:
        payload["case_structuring_draft"] = _base_case_structuring_draft_payload()

    return EvidenceAtomizerInput(**payload)


def _base_evidence_atom_payload(
    *, evidence_id: str, source_doc_id: str, atom_index: int, stage_id: str = "stage-001"
) -> dict[str, object]:
    return {
        "evidence_id": evidence_id,
        "stage_id": stage_id,
        "source_doc_id": source_doc_id,
        "atom_index": atom_index,
        "category": EvidenceCategory.SYMPTOM,
        "modality": InfoModality.HISTORY,
        "statement": "Chronic cough is present.",
        "raw_excerpt": "Chronic cough for several years.",
        "polarity": EvidencePolarity.PRESENT,
        "certainty": EvidenceCertainty.REPORTED,
        "temporality": EvidenceTemporality.CURRENT,
        "subject": EvidenceSubject.PATIENT,
    }


def _base_payload() -> dict[str, object]:
    return {
        "draft_id": "atomization_draft-001",
        "case_id": "case-001",
        "stage_id": "stage-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "evidence_atoms": (
            _base_evidence_atom_payload(
                evidence_id="evd-001",
                source_doc_id="doc-001",
                atom_index=0,
            ),
            _base_evidence_atom_payload(
                evidence_id="evd-002",
                source_doc_id="doc-002",
                atom_index=1,
            ),
        ),
        "extraction_activity": {
            "activity_id": "activity-001",
            "stage_id": "stage-001",
            "extraction_method": ExtractionMethod.RULE_BASED,
            "extractor_name": "evidence_atomizer_adapter",
            "extractor_version": "0.1.0",
            "occurred_at": datetime(2026, 4, 27, 10, 5, 0),
            "input_source_doc_ids": ("doc-001", "doc-002"),
        },
    }


def _set_payload_stage_id(payload: dict[str, object], *, stage_id: str) -> None:
    payload["stage_id"] = stage_id
    payload["extraction_activity"]["stage_id"] = stage_id

    for evidence_atom in payload["evidence_atoms"]:
        evidence_atom["stage_id"] = stage_id


def test_valid_input_builds_prompt_with_source_documents_stage_context_and_optional_draft() -> None:
    input_model = _base_input(with_case_structuring_draft=True)

    prompt = build_evidence_atomizer_prompt(input_model)

    assert "### Input JSON" in prompt
    assert "### Output Schema JSON" in prompt
    assert '"stage_id": "stage-001"' in prompt
    assert '"source_doc_id": "doc-001"' in prompt
    assert "Patient has chronic cough for 8 years." in prompt
    assert '"title": "EvidenceAtomizationDraft"' in prompt
    assert '"case_structuring_draft_guidance"' in prompt
    assert '"timeline_item_id": "timeline_item-001"' in prompt
    assert '"finding_id": "finding-001"' in prompt
    assert '"clue_group_id": "clue_group-001"' in prompt


def test_evidence_atomizer_prompt_renders_template_without_unresolved_placeholders_or_duplicate_input() -> None:
    prompt = build_evidence_atomizer_prompt(_base_input(with_case_structuring_draft=True))

    assert "{{" not in prompt
    assert "}}" not in prompt
    assert prompt.count("### Input JSON") == 1
    assert prompt.count('"stage_metadata"') == 1
    assert '"source_documents": [' in prompt
    assert '"properties": {' in prompt


def test_prompt_excludes_hypothesis_diagnosis_action_conflict_arbitration_fields() -> None:
    input_model = _base_input(with_case_structuring_draft=True)

    prompt = build_evidence_atomizer_prompt(input_model)

    assert '"hypotheses"' not in prompt
    assert '"final_diagnosis"' not in prompt
    assert '"claim_references"' not in prompt
    assert '"action_candidates"' not in prompt
    assert '"arbitration_output"' not in prompt
    assert '"typed_conflicts"' not in prompt


def test_valid_payload_parses_into_accepted_result() -> None:
    result = parse_evidence_atomizer_payload(_base_payload(), _base_input())

    assert result.status is EvidenceAtomizerStatus.ACCEPTED
    assert result.draft is not None
    assert result.draft.case_id == "case-001"
    assert result.errors == ()


def test_payload_with_final_diagnosis_is_rejected() -> None:
    payload = _base_payload()
    payload["final_diagnosis"] = "IPF"

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("final_diagnosis" in error for error in result.errors)


def test_payload_with_hypotheses_is_rejected() -> None:
    payload = _base_payload()
    payload["hypotheses"] = ("hyp-001",)

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("hypotheses" in error for error in result.errors)


def test_payload_with_claim_references_is_rejected() -> None:
    payload = _base_payload()
    payload["claim_references"] = ("claim_ref-001",)

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("claim_references" in error for error in result.errors)


def test_payload_with_action_candidates_is_rejected() -> None:
    payload = _base_payload()
    payload["action_candidates"] = ("action-001",)

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("action_candidates" in error for error in result.errors)


def test_payload_with_stage_id_mismatch_is_rejected() -> None:
    payload = _base_payload()
    _set_payload_stage_id(payload, stage_id="stage-999")

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("stage_id" in error for error in result.errors)


def test_payload_with_source_doc_outside_input_is_rejected() -> None:
    payload = _base_payload()
    payload["source_doc_ids"] = ("doc-001", "doc-999")
    payload["evidence_atoms"][1]["source_doc_id"] = "doc-999"
    payload["extraction_activity"]["input_source_doc_ids"] = ("doc-001", "doc-999")

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("source_doc_ids" in error for error in result.errors)


def test_payload_with_extraction_activity_stage_mismatch_is_rejected() -> None:
    payload = _base_payload()
    payload["extraction_activity"]["stage_id"] = "stage-999"

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("stage_id" in error for error in result.errors)


def test_payload_with_extraction_activity_doc_coverage_gap_is_rejected() -> None:
    payload = _base_payload()
    payload["source_doc_ids"] = ("doc-001",)
    payload["evidence_atoms"] = (payload["evidence_atoms"][0],)
    payload["extraction_activity"]["input_source_doc_ids"] = ("doc-001",)

    result = parse_evidence_atomizer_payload(payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert any("input_source_doc_ids" in error for error in result.errors)


def test_evidence_atomizer_input_rejects_empty_source_documents_on_construction() -> None:
    with pytest.raises(ValidationError):
        EvidenceAtomizerInput(
            case_id="case-001",
            stage_id="stage-001",
            source_documents=(),
            stage_context={
                "stage_id": "stage-001",
                "case_id": "case-001",
                "stage_index": 0,
                "stage_type": StageType.INITIAL_REVIEW,
                "trigger_type": TriggerType.INITIAL_PRESENTATION,
                "created_at": datetime(2026, 4, 27, 10, 0, 0),
                "available_modalities": (InfoModality.HISTORY,),
                "source_doc_ids": (),
            },
            extraction_activity_id="activity-001",
            occurred_at=datetime(2026, 4, 27, 10, 5, 0),
        )


def test_evidence_atomizer_input_rejects_stage_context_case_id_mismatch() -> None:
    payload = _base_input().model_dump()
    payload["stage_context"]["case_id"] = "case-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizerInput(**payload)


def test_evidence_atomizer_input_rejects_stage_context_stage_id_mismatch() -> None:
    payload = _base_input().model_dump()
    payload["stage_context"]["stage_id"] = "stage-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizerInput(**payload)


def test_evidence_atomizer_input_rejects_case_structuring_draft_mismatch() -> None:
    payload = _base_input(with_case_structuring_draft=True).model_dump()
    payload["case_structuring_draft"]["proposed_stage_context"]["stage_id"] = "stage-999"

    with pytest.raises(ValidationError):
        EvidenceAtomizerInput(**payload)


def test_invalid_payload_returns_structured_errors_without_uncaught_exceptions() -> None:
    invalid_payload = {
        "kind": "evidence_atomization_draft",
        "unexpected": "value",
    }

    result = parse_evidence_atomizer_payload(invalid_payload, _base_input())

    assert result.status is EvidenceAtomizerStatus.REJECTED
    assert result.draft is None
    assert result.errors
    assert all(isinstance(error, str) for error in result.errors)
