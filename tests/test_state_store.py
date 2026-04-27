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


def _build_created_from_event(
    *,
    snapshot: Phase1StateEnvelope,
    event_id: str,
    event_type: StateEventType = StateEventType.STATE_PERSISTED,
    stage_id: str | None = None,
    parent_state_id: str | None = None,
) -> StateEvent:
    resolved_stage_id = stage_id if stage_id is not None else snapshot.stage_context.stage_id
    resolved_parent_state_id = (
        parent_state_id if parent_state_id is not None else snapshot.parent_state_id
    )

    return StateEvent(
        event_id=event_id,
        event_type=event_type,
        case_id=snapshot.case_id,
        stage_id=resolved_stage_id,
        state_id=snapshot.state_id,
        parent_state_id=resolved_parent_state_id,
        state_version=snapshot.state_version,
        source_doc_ids=snapshot.stage_context.source_doc_ids,
        input_event_ids=(),
        created_at=snapshot.created_at,
        created_by="phase1_state_writer",
    )


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


def test_first_state_rejects_parent_state_id_when_set() -> None:
    store = InMemoryStateStore()
    snapshot = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id="state-000",
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )

    with pytest.raises(ValueError, match="must not define parent_state_id"):
        store.persist_snapshot(snapshot)


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


def test_state_store_accepts_snapshot_created_event_for_created_from_event() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    snapshot_event = _build_created_from_event(
        snapshot=first,
        event_id="event-snapshot-0001",
        event_type=StateEventType.SNAPSHOT_CREATED,
    )

    store.persist_snapshot(first, created_from_event=snapshot_event)
    versions = store.list_state_versions("case-abc")

    assert snapshot_event.event_type is StateEventType.SNAPSHOT_CREATED
    assert len(versions) == 1
    assert versions[0].stage_context.stage_id == "stage-001"


def test_state_store_rejects_created_from_event_stage_id_mismatch() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    bad_event = _build_created_from_event(
        snapshot=first,
        event_id="event-0001",
        stage_id="stage-999",
    )

    with pytest.raises(ValueError, match="created_from_event.stage_id"):
        store.persist_snapshot(first, created_from_event=bad_event)


def test_state_store_rejects_created_from_event_parent_state_id_mismatch() -> None:
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
        parent_state_id="state-001",
        created_at=datetime(2026, 4, 27, 20, 0, 1),
    )
    bad_event = _build_created_from_event(
        snapshot=second,
        event_id="event-0002",
        parent_state_id="state-999",
    )

    with pytest.raises(ValueError, match="created_from_event.parent_state_id"):
        store.persist_snapshot(second, created_from_event=bad_event)


def test_state_store_rejects_created_from_event_invalid_event_type() -> None:
    store = InMemoryStateStore()
    first = _build_snapshot(
        state_id="state-001",
        state_version=1,
        parent_state_id=None,
        created_at=datetime(2026, 4, 27, 20, 0, 0),
    )
    bad_event = _build_created_from_event(
        snapshot=first,
        event_id="event-0003",
        event_type=StateEventType.CANDIDATE_STATE_SUBMITTED,
    )

    with pytest.raises(ValueError, match="event_type"):
        store.persist_snapshot(first, created_from_event=bad_event)
