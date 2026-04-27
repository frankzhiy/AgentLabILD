"""Tests for Phase 1-4 Case Structurer adapter contract schemas."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.adapters.case_structuring import CaseStructuringDraft, NormalizedFinding
from src.schemas.stage import InfoModality, StageType, TriggerType


def _base_stage_context_payload() -> dict[str, object]:
    return {
        "stage_id": "stage-001",
        "case_id": "case-001",
        "stage_index": 0,
        "stage_type": StageType.INITIAL_REVIEW,
        "trigger_type": TriggerType.INITIAL_PRESENTATION,
        "created_at": datetime(2026, 4, 27, 10, 0, 0),
        "available_modalities": (InfoModality.HISTORY, InfoModality.SEROLOGY),
        "source_doc_ids": ("doc-001", "doc-002"),
    }


def _base_case_structuring_payload() -> dict[str, object]:
    return {
        "draft_id": "case_struct_draft-001",
        "case_id": "case-001",
        "source_doc_ids": ("doc-001", "doc-002"),
        "proposed_stage_context": _base_stage_context_payload(),
        "timeline_items": (
            {
                "timeline_item_id": "timeline_item-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-001",
                "event_type": "symptom_onset",
                "event_time_text": "8 years ago",
                "description": "Chronic cough and exertional dyspnea started.",
            },
        ),
        "normalized_findings": (
            {
                "finding_id": "finding-001",
                "stage_id": "stage-001",
                "source_doc_id": "doc-002",
                "finding_key": "ANA Titer 1:320",
                "finding_text": "ANA positive at 1:320.",
                "modality": InfoModality.SEROLOGY,
            },
        ),
        "candidate_clue_groups": (
            {
                "clue_group_id": "clue_group-001",
                "stage_id": "stage-001",
                "group_key": "autoimmune_clues",
                "finding_ids": ("finding-001",),
                "summary": "Autoimmune-related clues are present.",
            },
        ),
    }


def test_case_structuring_draft_valid_construction() -> None:
    draft = CaseStructuringDraft(**_base_case_structuring_payload())

    assert draft.kind == "case_structuring_draft"
    assert draft.proposed_stage_context.stage_id == "stage-001"
    assert draft.normalized_findings[0].finding_key == "ana_titer_1_320"


def test_case_structuring_draft_rejects_duplicate_source_doc_ids() -> None:
    payload = _base_case_structuring_payload()
    payload["source_doc_ids"] = ("doc-001", "doc-001")

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_duplicate_timeline_item_ids() -> None:
    payload = _base_case_structuring_payload()
    payload["timeline_items"] = (
        payload["timeline_items"][0],
        {
            "timeline_item_id": "timeline_item-001",
            "stage_id": "stage-001",
            "source_doc_id": "doc-002",
            "event_type": "follow_up",
            "event_time_text": "last month",
            "description": "Follow-up visit documented persistent cough.",
        },
    )

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_duplicate_finding_ids() -> None:
    payload = _base_case_structuring_payload()
    payload["normalized_findings"] = (
        payload["normalized_findings"][0],
        {
            "finding_id": "finding-001",
            "stage_id": "stage-001",
            "source_doc_id": "doc-001",
            "finding_key": "RF Positive",
            "finding_text": "Rheumatoid factor is positive.",
            "modality": InfoModality.SEROLOGY,
        },
    )

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_duplicate_clue_group_ids() -> None:
    payload = _base_case_structuring_payload()
    payload["candidate_clue_groups"] = (
        payload["candidate_clue_groups"][0],
        {
            "clue_group_id": "clue_group-001",
            "stage_id": "stage-001",
            "group_key": "other_clues",
            "finding_ids": (),
            "summary": "Other non-diagnostic clues.",
        },
    )

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_case_id_mismatch() -> None:
    payload = _base_case_structuring_payload()
    payload["case_id"] = "case-999"

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_stage_source_doc_outside_draft() -> None:
    payload = _base_case_structuring_payload()
    payload["source_doc_ids"] = ("doc-001",)
    payload["proposed_stage_context"]["source_doc_ids"] = ("doc-001", "doc-999")

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


@pytest.mark.parametrize("target_field", ["timeline_items", "normalized_findings"])
def test_case_structuring_draft_rejects_stage_mismatch(target_field: str) -> None:
    payload = _base_case_structuring_payload()
    payload[target_field][0]["stage_id"] = "stage-999"

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_missing_finding_reference() -> None:
    payload = _base_case_structuring_payload()
    payload["candidate_clue_groups"][0]["finding_ids"] = ("finding-404",)

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_normalized_finding_normalizes_finding_key_to_snake_case() -> None:
    finding = NormalizedFinding(
        finding_id="finding-777",
        stage_id="stage-001",
        source_doc_id="doc-001",
        finding_key="ESR + CRP Elevation",
        finding_text="Elevated ESR and CRP.",
        modality=InfoModality.LABORATORY,
    )

    assert finding.finding_key == "esr_crp_elevation"


def test_case_structuring_draft_rejects_diagnosis_like_group_key() -> None:
    payload = _base_case_structuring_payload()
    payload["candidate_clue_groups"][0]["group_key"] = "ipf_clues"

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)


def test_case_structuring_draft_rejects_extra_final_diagnosis_field() -> None:
    payload = _base_case_structuring_payload()
    payload["final_diagnosis"] = "IPF"

    with pytest.raises(ValidationError):
        CaseStructuringDraft(**payload)
