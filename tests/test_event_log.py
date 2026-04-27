"""Tests for Phase 1-5 append-only in-memory event log."""

from __future__ import annotations

from datetime import datetime

import pytest

from src.schemas.state_event import StateEvent, StateEventType
from src.storage.event_log import InMemoryEventLog


def _build_event(
    *,
    event_id: str,
    created_at: datetime,
    event_type: StateEventType = StateEventType.CANDIDATE_STATE_SUBMITTED,
    state_id: str | None = "state-001",
    state_version: int | None = 1,
) -> StateEvent:
    return StateEvent(
        event_id=event_id,
        event_type=event_type,
        case_id="case-abc",
        stage_id="stage-001",
        state_id=state_id,
        parent_state_id=None,
        state_version=state_version,
        source_doc_ids=("doc-001",),
        created_at=created_at,
        created_by="phase1_state_writer",
    )


def test_event_log_append_and_retrieve() -> None:
    log = InMemoryEventLog()
    event = _build_event(
        event_id="event-0001",
        created_at=datetime(2026, 4, 27, 19, 0, 0),
    )

    log.append(event)
    persisted = log.get("event-0001")

    assert persisted is not None
    assert persisted.event_id == "event-0001"
    assert log.list_events("case-abc")[0].event_id == "event-0001"


def test_event_log_rejects_duplicate_event_id() -> None:
    log = InMemoryEventLog()
    event = _build_event(
        event_id="event-0001",
        created_at=datetime(2026, 4, 27, 19, 0, 0),
    )

    log.append(event)

    with pytest.raises(ValueError, match="duplicate event_id"):
        log.append(event)


def test_event_log_lists_events_by_created_at_then_event_id() -> None:
    log = InMemoryEventLog()

    event_late = _build_event(
        event_id="event-0003",
        created_at=datetime(2026, 4, 27, 19, 0, 1),
    )
    event_same_time_larger_id = _build_event(
        event_id="event-0002",
        created_at=datetime(2026, 4, 27, 19, 0, 0),
    )
    event_same_time_smaller_id = _build_event(
        event_id="event-0001",
        created_at=datetime(2026, 4, 27, 19, 0, 0),
    )

    log.append(event_late)
    log.append(event_same_time_larger_id)
    log.append(event_same_time_smaller_id)

    ordered_ids = tuple(event.event_id for event in log.list_events("case-abc"))

    assert ordered_ids == ("event-0001", "event-0002", "event-0003")


def test_event_log_list_events_for_state_filters_by_state_id() -> None:
    log = InMemoryEventLog()
    log.append(
        _build_event(
            event_id="event-0001",
            created_at=datetime(2026, 4, 27, 19, 0, 0),
            state_id="state-001",
            state_version=1,
        )
    )
    log.append(
        _build_event(
            event_id="event-0002",
            created_at=datetime(2026, 4, 27, 19, 0, 1),
            state_id="state-002",
            state_version=2,
        )
    )

    filtered = log.list_events_for_state("state-001")

    assert len(filtered) == 1
    assert filtered[0].event_id == "event-0001"


def test_event_log_stores_and_returns_deep_copies() -> None:
    log = InMemoryEventLog()
    event = _build_event(
        event_id="event-0001",
        created_at=datetime(2026, 4, 27, 19, 0, 0),
    )

    log.append(event)
    event.created_by = "changed-after-append"

    first_read = log.get("event-0001")
    assert first_read is not None
    first_read.created_by = "changed-after-read"

    second_read = log.get("event-0001")
    assert second_read is not None
    assert second_read.created_by == "phase1_state_writer"
