"""Version-aware in-memory snapshot store for Phase 1-5."""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.state import Phase1StateEnvelope
from ..schemas.state_event import StateEvent, StateEventType


@runtime_checkable
class StateStore(Protocol):
    """Snapshot store contract for versioned Phase1StateEnvelope history."""

    def persist_snapshot(
        self,
        envelope: Phase1StateEnvelope,
        created_from_event: StateEvent | None = None,
    ) -> None:
        """Persist one accepted state snapshot."""

    def get_state(self, state_id: str) -> Phase1StateEnvelope | None:
        """Get one state snapshot by state_id."""

    def get_latest_state(self, case_id: str) -> Phase1StateEnvelope | None:
        """Get latest state snapshot for one case."""

    def list_state_versions(self, case_id: str) -> tuple[Phase1StateEnvelope, ...]:
        """List all versions for one case in ascending state_version order."""

    def replay(
        self,
        case_id: str,
        until_state_id: str | None = None,
    ) -> Phase1StateEnvelope | None:
        """Snapshot-level replay helper.

        This returns already persisted snapshots, not event-derived reconstruction
        or Phase 4 belief-revision replay.
        """


class InMemoryStateStore:
    """In-memory snapshot store with strict per-case version lineage checks."""

    def __init__(self) -> None:
        self._states_by_id: dict[str, Phase1StateEnvelope] = {}
        self._state_ids_by_case: dict[str, list[str]] = {}
        self._created_from_event_by_state_id: dict[str, StateEvent] = {}

    def persist_snapshot(
        self,
        envelope: Phase1StateEnvelope,
        created_from_event: StateEvent | None = None,
    ) -> None:
        if envelope.state_id in self._states_by_id:
            raise ValueError(f"duplicate state_id is not allowed: {envelope.state_id}")

        existing_states = self.list_state_versions(envelope.case_id)
        if not existing_states:
            if envelope.state_version != 1:
                raise ValueError(
                    "the first persisted snapshot for one case must have state_version=1"
                )

            if envelope.parent_state_id is not None:
                raise ValueError(
                    "the first persisted snapshot for one case must not define parent_state_id"
                )
        else:
            previous = existing_states[-1]
            expected_next_version = previous.state_version + 1

            if envelope.state_version <= previous.state_version:
                raise ValueError(
                    "state_version must strictly increase within one case"
                )

            if envelope.state_version != expected_next_version:
                raise ValueError(
                    "state_version must increment by 1 from the previous version"
                )

            if envelope.parent_state_id != previous.state_id:
                raise ValueError(
                    "parent_state_id must reference the previous state_id when state_version > 1"
                )

        if created_from_event is not None:
            self._validate_created_from_event(
                envelope=envelope,
                created_from_event=created_from_event,
            )

        self._states_by_id[envelope.state_id] = envelope.model_copy(deep=True)
        self._state_ids_by_case.setdefault(envelope.case_id, []).append(envelope.state_id)

        if created_from_event is not None:
            self._created_from_event_by_state_id[envelope.state_id] = (
                created_from_event.model_copy(deep=True)
            )

    def persist(self, envelope: Phase1StateEnvelope) -> None:
        """StateSink compatibility entrypoint used by phase1 state_writer."""

        self.persist_snapshot(envelope)

    def get_state(self, state_id: str) -> Phase1StateEnvelope | None:
        state = self._states_by_id.get(state_id)
        if state is None:
            return None

        return state.model_copy(deep=True)

    def get_latest_state(self, case_id: str) -> Phase1StateEnvelope | None:
        state_ids = self._state_ids_by_case.get(case_id)
        if not state_ids:
            return None

        latest_state_id = state_ids[-1]
        return self._states_by_id[latest_state_id].model_copy(deep=True)

    def list_state_versions(self, case_id: str) -> tuple[Phase1StateEnvelope, ...]:
        state_ids = self._state_ids_by_case.get(case_id)
        if not state_ids:
            return ()

        return tuple(
            self._states_by_id[state_id].model_copy(deep=True) for state_id in state_ids
        )

    def replay(
        self,
        case_id: str,
        until_state_id: str | None = None,
    ) -> Phase1StateEnvelope | None:
        if until_state_id is None:
            return self.get_latest_state(case_id)

        state = self._states_by_id.get(until_state_id)
        if state is None:
            return None

        if state.case_id != case_id:
            return None

        return state.model_copy(deep=True)

    def _validate_created_from_event(
        self,
        *,
        envelope: Phase1StateEnvelope,
        created_from_event: StateEvent,
    ) -> None:
        if created_from_event.event_type not in {
            StateEventType.STATE_PERSISTED,
            StateEventType.SNAPSHOT_CREATED,
        }:
            raise ValueError(
                "created_from_event.event_type must be state_persisted or snapshot_created"
            )

        if created_from_event.case_id != envelope.case_id:
            raise ValueError("created_from_event.case_id must equal envelope.case_id")

        if (
            created_from_event.stage_id is not None
            and created_from_event.stage_id != envelope.stage_context.stage_id
        ):
            raise ValueError(
                "created_from_event.stage_id must be absent or equal to envelope.stage_context.stage_id"
            )

        if (
            created_from_event.state_id is not None
            and created_from_event.state_id != envelope.state_id
        ):
            raise ValueError(
                "created_from_event.state_id must be absent or equal to envelope.state_id"
            )

        if (
            created_from_event.parent_state_id is not None
            and created_from_event.parent_state_id != envelope.parent_state_id
        ):
            raise ValueError(
                "created_from_event.parent_state_id must be absent or equal to envelope.parent_state_id"
            )

        if (
            created_from_event.state_version is not None
            and created_from_event.state_version != envelope.state_version
        ):
            raise ValueError(
                "created_from_event.state_version must be absent or equal to envelope.state_version"
            )


__all__ = ["InMemoryStateStore", "StateStore"]
