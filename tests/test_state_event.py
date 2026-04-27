"""Tests for Phase 1-5 state event schema."""

from __future__ import annotations

from datetime import datetime

import pytest
from pydantic import ValidationError

from src.schemas.state_event import StateEvent, StateEventType


def _base_payload() -> dict[str, object]:
    return {
        "event_id": "event-0001",
        "event_type": StateEventType.CANDIDATE_STATE_SUBMITTED,
        "case_id": "case-abc",
        "stage_id": "stage-001",
        "state_id": "state-001",
        "parent_state_id": None,
        "state_version": 1,
        "source_doc_ids": ("doc-001",),
        "created_at": datetime(2026, 4, 27, 18, 0, 0),
        "created_by": "phase1_state_writer",
        "non_authoritative_note": None,
    }


def test_state_event_valid_construction() -> None:
    event = StateEvent(**_base_payload())

    assert event.kind == "state_event"
    assert event.event_type is StateEventType.CANDIDATE_STATE_SUBMITTED


def test_state_persisted_event_requires_state_id_and_state_version() -> None:
    payload = _base_payload()
    payload["event_type"] = StateEventType.STATE_PERSISTED
    payload["state_id"] = None

    with pytest.raises(ValidationError):
        StateEvent(**payload)

    payload = _base_payload()
    payload["event_type"] = StateEventType.STATE_PERSISTED
    payload["state_version"] = None

    with pytest.raises(ValidationError):
        StateEvent(**payload)


def test_source_document_received_requires_non_empty_source_doc_ids() -> None:
    payload = _base_payload()
    payload["event_type"] = StateEventType.SOURCE_DOCUMENT_RECEIVED
    payload["source_doc_ids"] = ()

    with pytest.raises(ValidationError):
        StateEvent(**payload)


def test_state_event_rejects_duplicate_source_doc_ids() -> None:
    payload = _base_payload()
    payload["source_doc_ids"] = ("doc-001", "doc-001")

    with pytest.raises(ValidationError):
        StateEvent(**payload)


def test_state_event_rejects_parent_state_id_equal_to_state_id() -> None:
    payload = _base_payload()
    payload["parent_state_id"] = payload["state_id"]

    with pytest.raises(ValidationError):
        StateEvent(**payload)


def test_free_text_submission_is_one_source_document_event_not_stage_split() -> None:
    payload = _base_payload()
    payload["event_type"] = StateEventType.SOURCE_DOCUMENT_RECEIVED
    payload["state_id"] = None
    payload["state_version"] = None
    payload["stage_id"] = None
    payload["source_doc_ids"] = ("doc-raw-001",)
    payload["non_authoritative_note"] = (
        "原文包含 8 years ago、2 months ago、2024-06-11 CT 等时间线片段，但仍是一次输入事件"
    )

    event = StateEvent(**payload)

    dumped = event.model_dump(mode="python")
    assert event.event_type is StateEventType.SOURCE_DOCUMENT_RECEIVED
    assert event.stage_id is None
    assert event.source_doc_ids == ("doc-raw-001",)
    assert "stage_contexts" not in dumped
