"""Tests for Phase 1 raw-text intake schemas."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.intake import (
    RawInputEvent,
    RawInputMode,
    SourceDocument,
    SourceDocumentType,
    StageResolutionReport,
)
from src.schemas.stage import StageType, TriggerType


def _base_raw_input_event_payload() -> dict[str, object]:
    return {
        "input_event_id": "input_event-0001",
        "case_id": "case-abc",
        "arrival_index": 0,
        "raw_text": "患者, 女, 77岁, 咳嗽咳痰伴胸闷气短8年。",
        "received_at": datetime(2026, 4, 27, 9, 0, 0),
        "input_mode": RawInputMode.INITIAL_SUBMISSION,
        "parent_input_event_id": None,
    }


def _base_source_document_payload() -> dict[str, object]:
    return {
        "source_doc_id": "doc-001",
        "case_id": "case-abc",
        "input_event_id": "input_event-0001",
        "document_type": SourceDocumentType.FREE_TEXT_CASE_NOTE,
        "raw_text": "患者, 女, 77岁, 咳嗽咳痰伴胸闷气短8年。",
        "created_at": datetime(2026, 4, 27, 9, 0, 0),
    }


def _base_stage_resolution_payload() -> dict[str, object]:
    return {
        "stage_resolution_id": "stage_resolution-0001",
        "case_id": "case-abc",
        "candidate_stage_id": "stage-001",
        "candidate_stage_type": StageType.INITIAL_REVIEW,
        "candidate_trigger_type": TriggerType.INITIAL_PRESENTATION,
        "bound_input_event_ids": ("input_event-0001",),
        "bound_source_doc_ids": ("doc-001",),
        "resolution_confidence": 0.9,
        "manual_review_required": False,
        "resolution_rationale": "仅用于解释，不作为权威证据。",
        "created_at": datetime(2026, 4, 27, 10, 0, 0),
    }


def test_raw_input_event_valid_construction() -> None:
    event = RawInputEvent(**_base_raw_input_event_payload())

    assert event.kind == "raw_input_event"
    assert event.input_mode is RawInputMode.INITIAL_SUBMISSION


def test_initial_submission_cannot_define_parent_input_event_id() -> None:
    payload = _base_raw_input_event_payload()
    payload["parent_input_event_id"] = "input_event-0000"

    with pytest.raises(ValidationError):
        RawInputEvent(**payload)


def test_append_input_event_can_reference_parent_input_event_id() -> None:
    payload = _base_raw_input_event_payload()
    payload["input_event_id"] = "input_event-0002"
    payload["input_mode"] = RawInputMode.APPEND
    payload["parent_input_event_id"] = "input_event-0001"

    event = RawInputEvent(**payload)

    assert event.input_mode is RawInputMode.APPEND
    assert event.parent_input_event_id == "input_event-0001"


def test_source_document_valid_construction() -> None:
    source_document = SourceDocument(**_base_source_document_payload())

    assert source_document.kind == "source_document"
    assert source_document.document_type is SourceDocumentType.FREE_TEXT_CASE_NOTE


def test_stage_resolution_report_rejects_duplicate_bound_source_doc_ids() -> None:
    payload = _base_stage_resolution_payload()
    payload["bound_source_doc_ids"] = ("doc-001", "doc-001")

    with pytest.raises(ValidationError):
        StageResolutionReport(**payload)


def test_stage_resolution_report_requires_manual_review_when_confidence_low() -> None:
    payload = _base_stage_resolution_payload()
    payload["resolution_confidence"] = 0.6
    payload["manual_review_required"] = False

    with pytest.raises(ValidationError):
        StageResolutionReport(**payload)


def test_stage_resolution_report_low_confidence_allows_manual_review_true() -> None:
    payload = _base_stage_resolution_payload()
    payload["resolution_confidence"] = 0.6
    payload["manual_review_required"] = True

    report = StageResolutionReport(**payload)

    assert report.manual_review_required is True
