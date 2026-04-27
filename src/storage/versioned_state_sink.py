"""StateSink adapter that persists snapshots with state_persisted events."""

from __future__ import annotations

from ..schemas.state import Phase1StateEnvelope
from ..schemas.state_event import StateEvent, StateEventType
from ..utils.time import utc_now
from .event_log import EventLog
from .state_store import StateStore


class VersionedStateSink:
    """Bridge sink that writes both append-only event and snapshot state."""

    def __init__(
        self,
        *,
        state_store: StateStore,
        event_log: EventLog,
        created_by: str,
    ) -> None:
        cleaned_created_by = created_by.strip()
        if not cleaned_created_by:
            raise ValueError("created_by must not be empty")

        self._state_store = state_store
        self._event_log = event_log
        self._created_by = cleaned_created_by
        self._event_sequence = 0

    def persist(self, envelope: Phase1StateEnvelope) -> None:
        event = StateEvent(
            event_id=self._next_event_id(
                case_id=envelope.case_id,
                state_version=envelope.state_version,
            ),
            event_type=StateEventType.STATE_PERSISTED,
            case_id=envelope.case_id,
            stage_id=envelope.stage_context.stage_id,
            state_id=envelope.state_id,
            parent_state_id=envelope.parent_state_id,
            state_version=envelope.state_version,
            source_doc_ids=envelope.stage_context.source_doc_ids,
            input_event_ids=(),
            created_at=utc_now(),
            created_by=self._created_by,
        )

        self._event_log.append(event)
        self._state_store.persist_snapshot(envelope, created_from_event=event)

    def _next_event_id(self, *, case_id: str, state_version: int) -> str:
        while True:
            self._event_sequence += 1
            candidate = (
                "event-state_persisted-"
                f"{case_id}-v{state_version}-{self._event_sequence:06d}"
            )
            if self._event_log.get(candidate) is None:
                return candidate


__all__ = ["VersionedStateSink"]
