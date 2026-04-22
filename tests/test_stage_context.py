"""Tests for Phase 1-1 StageContext schema."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.stage import (
    InfoModality,
    StageContext,
    StageFocus,
    StageType,
    TriggerType,
    VisibilityPolicyHint,
)


def _base_payload() -> dict[str, object]:
    return {
        "stage_id": "stage-001",
        "case_id": "case-abc",
        "stage_index": 0,
        "stage_type": StageType.INITIAL_REVIEW,
        "trigger_type": TriggerType.INITIAL_PRESENTATION,
        "created_at": datetime(2026, 4, 22, 9, 30, 0),
        "clinical_time": datetime(2026, 4, 21, 16, 15, 0),
        "parent_stage_id": None,
        "available_modalities": [
            InfoModality.DEMOGRAPHICS,
            InfoModality.HRCT_TEXT,
        ],
        "source_doc_ids": ["doc-001", "doc-002"],
        "stage_label": "Initial MDT Review",
        "stage_focus": [StageFocus.BASELINE_STRUCTURING],
        "clinical_question_tags": ["ctd_ild_screen"],
        "visibility_policy_hint": VisibilityPolicyHint.MDT_SHARED,
        "non_authoritative_note": "This note is for display only.",
    }


def test_stage_context_valid_construction() -> None:
    ctx = StageContext(**_base_payload())

    assert ctx.stage_id == "stage-001"
    assert ctx.stage_type is StageType.INITIAL_REVIEW
    assert InfoModality.DEMOGRAPHICS in ctx.available_modalities
    assert "ctd_ild_screen" in ctx.clinical_question_tags


def test_stage_focus_is_operational_taxonomy_only() -> None:
    expected = {
        "baseline_structuring",
        "evidence_augmentation",
        "longitudinal_reassessment",
        "working_diagnosis_revision",
        "management_review",
        "safety_review",
    }
    forbidden_case_specific_items = {
        "ae_vs_infection",
        "ipf_vs_fibrotic_hp",
        "ctd_ild_screen",
    }
    actual = {item.value for item in StageFocus}

    assert actual == expected
    assert actual.isdisjoint(forbidden_case_specific_items)


def test_visibility_policy_hint_contains_visibility_values_only() -> None:
    expected = {"stage_local_only", "mdt_shared", "mdt_restricted"}
    actual = {item.value for item in VisibilityPolicyHint}

    assert actual == expected
    assert "safety_escalation_required" not in actual


def test_stage_context_invalid_enum_value() -> None:
    payload = _base_payload()
    payload["stage_type"] = "unsupported_stage"

    with pytest.raises(ValidationError):
        StageContext(**payload)


def test_initial_stage_allows_no_parent() -> None:
    payload = _base_payload()
    payload["parent_stage_id"] = None
    payload["stage_type"] = StageType.INITIAL_REVIEW

    ctx = StageContext(**payload)

    assert ctx.parent_stage_id is None


def test_non_authoritative_note_does_not_drive_logic() -> None:
    payload = _base_payload()
    payload["stage_type"] = StageType.FOLLOW_UP_REVIEW
    payload["parent_stage_id"] = None
    payload["non_authoritative_note"] = "Treat this as initial stage."

    ctx = StageContext(**payload)

    assert ctx.stage_type is StageType.FOLLOW_UP_REVIEW
    assert ctx.parent_stage_id is None


def test_clinical_question_tags_are_independent_from_stage_focus() -> None:
    payload = _base_payload()
    payload["stage_focus"] = [StageFocus.SAFETY_REVIEW]
    payload["clinical_question_tags"] = [
        "ae_vs_infection",
        "ipf_vs_fibrotic_hp",
    ]

    ctx = StageContext(**payload)

    assert ctx.stage_focus == (StageFocus.SAFETY_REVIEW,)
    assert ctx.clinical_question_tags == (
        "ae_vs_infection",
        "ipf_vs_fibrotic_hp",
    )


def test_initial_stage_rejects_parent_stage_id() -> None:
    payload = _base_payload()
    payload["stage_type"] = StageType.INITIAL_REVIEW
    payload["parent_stage_id"] = "stage-000"

    with pytest.raises(ValidationError):
        StageContext(**payload)


def test_stage_context_serialization_roundtrip() -> None:
    ctx = StageContext(**_base_payload())

    serialized = ctx.model_dump_json()
    restored = StageContext.model_validate_json(serialized)

    assert restored == ctx


def test_duplicate_stage_focus_rejected() -> None:
    payload = _base_payload()
    payload["stage_focus"] = [
        StageFocus.BASELINE_STRUCTURING,
        StageFocus.BASELINE_STRUCTURING,
    ]

    with pytest.raises(ValidationError):
        StageContext(**payload)


def test_duplicate_clinical_question_tags_rejected() -> None:
    payload = _base_payload()
    payload["clinical_question_tags"] = [
        "ae_vs_infection",
        "ae_vs_infection",
    ]

    with pytest.raises(ValidationError):
        StageContext(**payload)
