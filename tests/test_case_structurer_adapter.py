"""Tests for Phase 1-4 Case Structurer adapter behavior."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.agents.case_structurer import (
    CaseStructurerInput,
    CaseStructurerStatus,
    build_case_structurer_prompt,
    parse_case_structurer_payload,
)
from src.schemas.intake import SourceDocumentType
from src.schemas.stage import InfoModality, StageType, TriggerType


def _base_input() -> CaseStructurerInput:
    return CaseStructurerInput(
        case_id="case-001",
        source_documents=(
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
        stage_id="stage-001",
        stage_index=0,
        stage_type=StageType.INITIAL_REVIEW,
        trigger_type=TriggerType.INITIAL_PRESENTATION,
        created_at=datetime(2026, 4, 27, 10, 0, 0),
        previous_stage_summary="Non-authoritative summary from previous stage.",
    )


def _base_payload() -> dict[str, object]:
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


def _set_payload_stage_id(payload: dict[str, object], *, stage_id: str) -> None:
    payload["proposed_stage_context"]["stage_id"] = stage_id

    for timeline_item in payload["timeline_items"]:
        timeline_item["stage_id"] = stage_id

    for finding in payload["normalized_findings"]:
        finding["stage_id"] = stage_id

    for clue_group in payload["candidate_clue_groups"]:
        clue_group["stage_id"] = stage_id


def test_valid_input_builds_prompt_with_source_documents_and_stage_metadata() -> None:
    input_model = _base_input()

    prompt = build_case_structurer_prompt(input_model)

    assert "### Input JSON" in prompt
    assert '"stage_id": "stage-001"' in prompt
    assert '"source_doc_id": "doc-001"' in prompt
    assert "Patient has chronic cough for 8 years." in prompt


def test_prompt_excludes_hypothesis_diagnosis_action_arbitration_payload_fields() -> None:
    input_model = _base_input()

    prompt = build_case_structurer_prompt(input_model)

    assert '"hypotheses"' not in prompt
    assert '"final_diagnosis"' not in prompt
    assert '"action_plan"' not in prompt
    assert '"arbitration_output"' not in prompt


def test_valid_payload_parses_into_accepted_result() -> None:
    result = parse_case_structurer_payload(_base_payload(), _base_input())

    assert result.status is CaseStructurerStatus.ACCEPTED
    assert result.draft is not None
    assert result.draft.case_id == "case-001"
    assert result.errors == ()


def test_payload_with_final_diagnosis_is_rejected() -> None:
    payload = _base_payload()
    payload["final_diagnosis"] = "IPF"

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert any("final_diagnosis" in error for error in result.errors)


def test_payload_with_hypotheses_is_rejected() -> None:
    payload = _base_payload()
    payload["hypotheses"] = ("hyp-001",)

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert any("hypotheses" in error for error in result.errors)


def test_payload_with_source_doc_outside_input_is_rejected() -> None:
    payload = _base_payload()
    payload["source_doc_ids"] = ("doc-001", "doc-999")
    payload["proposed_stage_context"]["source_doc_ids"] = ("doc-001", "doc-999")
    payload["normalized_findings"][0]["source_doc_id"] = "doc-001"

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert any("source_doc_ids" in error for error in result.errors)


def test_payload_with_stage_id_mismatch_is_rejected() -> None:
    payload = _base_payload()
    _set_payload_stage_id(payload, stage_id="stage-999")

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert any("stage_id" in error for error in result.errors)


def test_empty_source_documents_is_rejected() -> None:
    input_model = _base_input().model_copy(update={"source_documents": ()})

    result = parse_case_structurer_payload(_base_payload(), input_model)

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert any("source_documents" in error for error in result.errors)


def test_case_structurer_input_rejects_empty_source_documents_on_construction() -> None:
    with pytest.raises(ValidationError):
        CaseStructurerInput(
            case_id="case-001",
            source_documents=(),
            stage_id="stage-001",
            stage_index=0,
            stage_type=StageType.INITIAL_REVIEW,
            trigger_type=TriggerType.INITIAL_PRESENTATION,
            created_at=datetime(2026, 4, 27, 10, 0, 0),
        )


def test_payload_with_stage_index_mismatch_is_rejected() -> None:
    payload = _base_payload()
    payload["proposed_stage_context"]["stage_index"] = 99

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("stage_index" in error for error in result.errors)


def test_payload_with_stage_type_mismatch_is_rejected() -> None:
    payload = _base_payload()
    payload["proposed_stage_context"]["stage_type"] = StageType.FOLLOW_UP_REVIEW

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("stage_type" in error for error in result.errors)


def test_payload_with_trigger_type_mismatch_is_rejected() -> None:
    payload = _base_payload()
    payload["proposed_stage_context"]["trigger_type"] = TriggerType.CLINICAL_WORSENING

    result = parse_case_structurer_payload(payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("trigger_type" in error for error in result.errors)


def test_payload_with_parent_stage_id_mismatch_is_rejected() -> None:
    input_model = _base_input().model_copy(update={"parent_stage_id": "stage-900"})
    payload = _base_payload()

    result = parse_case_structurer_payload(payload, input_model)

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("parent_stage_id" in error for error in result.errors)


def test_payload_with_clinical_time_mismatch_is_rejected_when_input_provides_it() -> None:
    input_model = _base_input().model_copy(
        update={"clinical_time": datetime(2026, 4, 27, 8, 0, 0)}
    )
    payload = _base_payload()
    payload["proposed_stage_context"]["clinical_time"] = datetime(2026, 4, 27, 8, 30, 0)

    result = parse_case_structurer_payload(payload, input_model)

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("clinical_time" in error for error in result.errors)


def test_payload_with_stage_label_mismatch_is_rejected_when_input_provides_it() -> None:
    input_model = _base_input().model_copy(update={"stage_label": "Initial Stage"})
    payload = _base_payload()
    payload["proposed_stage_context"]["stage_label"] = "Different Label"

    result = parse_case_structurer_payload(payload, input_model)

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("stage_label" in error for error in result.errors)


def test_invalid_payload_returns_structured_errors_without_uncaught_exceptions() -> None:
    invalid_payload = {
        "kind": "case_structuring_draft",
        "unexpected": "value",
    }

    result = parse_case_structurer_payload(invalid_payload, _base_input())

    assert result.status is CaseStructurerStatus.REJECTED
    assert result.draft is None
    assert result.errors
    assert all(isinstance(error, str) for error in result.errors)


def test_forbidden_payload_is_rejected_even_with_diagnosis_like_previous_summary() -> None:
    input_model = _base_input().model_copy(
        update={
            "previous_stage_summary": (
                "Previous non-authoritative note mentioned probable IPF and suggested steroid adjustment."
            )
        }
    )
    payload = _base_payload()
    payload["hypotheses"] = ("hyp-001",)

    result = parse_case_structurer_payload(payload, input_model)

    assert result.status is CaseStructurerStatus.REJECTED
    assert any("hypotheses" in error for error in result.errors)
