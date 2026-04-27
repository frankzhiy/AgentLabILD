"""Tests for Phase 1-5 in-memory versioned snapshot store."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.state import Phase1StateEnvelope
from src.schemas.state_event import StateEvent, StateEventType
from src.storage.state_store import InMemoryStateStore
from tests.test_provenance_checker import build_valid_envelope


def _build_snapshot(
    *,
    state_id: str,
    state_version: int,
    parent_state_id: str | None,
    created_at: datetime,
) -> Phase1StateEnvelope:
    snapshot = build_valid_envelope()
    snapshot.state_id = state_id
    snapshot.state_version = state_version
    snapshot.parent_state_id = parent_state_id
    snapshot.created_at = created_at
    return snapshot


def test_first_state_can_persist_with_version_1_and_no_parent() -> None:
    store = InMemoryStateStore()
    snapshot = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )

    store.persist_snapshot(snapshot)
    persisted = store.get_state("state-001")

    assert persisted is not None
    assert persisted.state_version == 1
    assert persisted.parent_state_id is None


def test_second_state_must_reference_previous_state_id() -> None:
    store = InMemoryStateStore()

    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    store.persist_snapshot(first)

    second = _build_snapshot(
        state_id="state-002",
        state_version=2,
        parent_state_id="state-999",
        created_at=datetime(2026, 4, 27, 20, 0, 1),
    )

    with pytest.raises(ValueError, match="parent_state_id"):
        store.persist_snapshot(second)


def test_state_store_replay_returns_latest_state() -> None:
    store = InMemoryStateStore()

    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    second = _build_snapshot(
        state_id="state-002",
        state_version=2,
        parent_state_id="state-001",
        created_at=datetime(2026, 4, 27, 20, 0, 1),
    )

    store.persist_snapshot(first)
    store.persist_snapshot(second)

    replayed = store.replay("case-abc")

    assert replayed is not None
    assert replayed.state_id == "state-002"


def test_state_store_replay_until_state_id_returns_requested_state() -> None:
    store = InMemoryStateStore()

    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    second = _build_snapshot(
        state_id="state-002",
        state_version=2,
        parent_state_id="state-001",
        created_at=datetime(2026, 4, 27, 20, 0, 1),
    )

    store.persist_snapshot(first)
    store.persist_snapshot(second)

    replayed = store.replay("case-abc", until_state_id="state-001")

    assert replayed is not None
    assert replayed.state_id == "state-001"


def test_state_store_rejects_duplicate_state_id() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )

    store.persist_snapshot(first)

    with pytest.raises(ValueError, match="duplicate state_id"):
        store.persist_snapshot(first)


def test_state_store_persisted_snapshots_are_deep_copied() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )

    store.persist_snapshot(first)

    first.state_id = "state-mutated"
    first.stage_context.stage_id = "stage-mutated"

    persisted = store.get_state("state-001")
    assert persisted is not None
    assert persisted.state_id == "state-001"
    assert persisted.stage_context.stage_id == "stage-001"

    persisted.stage_context.stage_id = "stage-after-read"
    persisted_again = store.get_state("state-001")
    assert persisted_again is not None
    assert persisted_again.stage_context.stage_id == "stage-001"


def test_state_store_implements_state_sink_persist_compatibility() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )

    store.persist(first)

    latest = store.get_latest_state("case-abc")
    assert latest is not None
    assert latest.state_id == "state-001"


def test_free_text_submission_uses_source_document_received_event() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    intake_event = StateEvent(
        event_id="event-raw-0001",
        event_type=StateEventType.SOURCE_DOCUMENT_RECEIVED,
        case_id="case-abc",
        stage_id=None,
        state_id=None,
        parent_state_id=None,
        state_version=None,
        source_doc_ids=("doc-001",),
        created_at=datetime(2026, 4, 27, 19, 59, 59),
        created_by="raw_intake_gate",
        non_authoritative_note=(
            "原文中包含 8 years ago / 2 months ago / 2024-06-11 CT，但仍是一次 free-text 提交"
        ),
    )

    store.persist_snapshot(first, created_from_event=intake_event)
    versions = store.list_state_versions("case-abc")

    assert intake_event.event_type is StateEventType.SOURCE_DOCUMENT_RECEIVED
    assert intake_event.stage_id is None
    assert len(versions) == 1
    assert versions[0].stage_context.stage_id == "stage-001"
