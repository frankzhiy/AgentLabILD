"""Append-only in-memory state event log for Phase 1-5."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.state_event import StateEvent


@runtime_checkable
class EventLog(Protocol):
    """Event log contract for immutable state lifecycle events."""

    def append(self, event: StateEvent) -> None:
        """Append one event to the log."""

    def get(self, event_id: str) -> StateEvent | None:
        """Get one event by id."""

    def list_events(self, case_id: str) -> tuple[StateEvent, ...]:
        """List events for one case in deterministic order."""

    def list_events_for_state(self, state_id: str) -> tuple[StateEvent, ...]:
        """List events that directly reference one state_id."""


class InMemoryEventLog:
    """Deterministic append-only event log implementation."""

    def __init__(self) -> None:
        self._events_by_id: dict[str, StateEvent] = {}

    def append(self, event: StateEvent) -> None:
        if event.event_id in self._events_by_id:
            raise ValueError(f"duplicate event_id is not allowed: {event.event_id}")

        # Store deep copies so caller-side mutation does not affect log history.
        self._events_by_id[event.event_id] = event.model_copy(deep=True)

    def get(self, event_id: str) -> StateEvent | None:
        event = self._events_by_id.get(event_id)
        if event is None:
            return None

        return event.model_copy(deep=True)

    def list_events(self, case_id: str) -> tuple[StateEvent, ...]:
        ordered = sorted(
            (
                event
                for event in self._events_by_id.values()
                if event.case_id == case_id
            ),
            key=lambda event: (event.created_at, event.event_id),
        )

        return tuple(event.model_copy(deep=True) for event in ordered)

    def list_events_for_state(self, state_id: str) -> tuple[StateEvent, ...]:
        ordered = sorted(
            (
                event
                for event in self._events_by_id.values()
                if event.state_id == state_id
            ),
            key=lambda event: (event.created_at, event.event_id),
        )

        return tuple(event.model_copy(deep=True) for event in ordered)


__all__ = ["EventLog", "InMemoryEventLog"]
