"""Integration tests for VersionedStateSink with validator-gated writer."""

from __future__ import annotations

from datetime import datetime, timezone

from src.schemas.state_event import StateEvent, StateEventType
from src.state import WriteDecisionStatus, attempt_phase1_write
from src.storage import InMemoryEventLog, InMemoryStateStore, VersionedStateSink
from src.validators.pipeline import ValidationPipelinePolicy
from tests.test_provenance_checker import build_valid_envelope


def test_versioned_state_sink_persists_snapshot_and_state_persisted_event() -> None:
    state_store = InMemoryStateStore()
    event_log = InMemoryEventLog()
    sink = VersionedStateSink(
        state_store=state_store,
        event_log=event_log,
        created_by="phase1_state_writer",
    )

    envelope = build_valid_envelope()
    decision = attempt_phase1_write(
        envelope,
        sink=sink,
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    persisted = state_store.get_state(envelope.state_id)
    events = event_log.list_events(envelope.case_id)

    assert decision.status is WriteDecisionStatus.ACCEPTED
    assert persisted is not None
    assert persisted.state_id == envelope.state_id
    assert len(events) == 1
    assert events[0].event_type is StateEventType.STATE_PERSISTED
    assert events[0].state_id == envelope.state_id
    assert events[0].state_version == envelope.state_version


def test_versioned_state_sink_generates_non_colliding_event_ids() -> None:
    state_store = InMemoryStateStore()
    event_log = InMemoryEventLog()
    sink = VersionedStateSink(
        state_store=state_store,
        event_log=event_log,
        created_by="phase1_state_writer",
    )

    event_log.append(
        StateEvent(
            event_id="event-state_persisted-case-abc-v1-000001",
            event_type=StateEventType.STATE_PERSISTED,
            case_id="case-abc",
            stage_id="stage-001",
            state_id="state-preexisting",
            parent_state_id=None,
            state_version=1,
            source_doc_ids=("doc-001",),
            input_event_ids=(),
            created_at=datetime(2026, 4, 27, 21, 0, 0, tzinfo=timezone.utc),
            created_by="bootstrap",
        )
    )

    envelope = build_valid_envelope()
    decision = attempt_phase1_write(
        envelope,
        sink=sink,
        validation_policy=ValidationPipelinePolicy(require_provenance=True),
    )

    events = event_log.list_events("case-abc")
    event_ids = tuple(event.event_id for event in events)
    persisted_event = [event for event in events if event.state_id == envelope.state_id]

    assert decision.status is WriteDecisionStatus.ACCEPTED
    assert len(events) == 2
    assert len(set(event_ids)) == 2
    assert len(persisted_event) == 1
    assert persisted_event[0].event_id.endswith("000002")
    assert state_store.get_latest_state("case-abc") is not None
    assert state_store.get_latest_state("case-abc").state_id == envelope.state_id
