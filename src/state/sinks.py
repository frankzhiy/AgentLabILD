"""State sink abstractions for Phase 1-3 validator-gated writes.

This module defines lightweight sink contracts only. It does not implement
storage engines, transactions, or event sourcing.
"""

from __future__ import annotations

from typing import Protocol, runtime_checkable

from ..schemas.state import Phase1StateEnvelope


@runtime_checkable
class StateSink(Protocol):
    """Minimal sink protocol for persisting validated envelopes."""

    def persist(self, envelope: Phase1StateEnvelope) -> None:
        """Persist one authoritative envelope instance."""


class NoOpStateSink:
    """Sink implementation that intentionally performs no persistence."""

    def __init__(self) -> None:
        self._persist_call_count = 0

    @property
    def persist_call_count(self) -> int:
        """Return how many persist calls were received."""

        return self._persist_call_count

    def persist(self, envelope: Phase1StateEnvelope) -> None:
        del envelope
        self._persist_call_count += 1

    def list_state_ids(self) -> tuple[str, ...]:
        """Expose an empty view for test-friendly observability."""

        return ()


class InMemoryStateSink:
    """In-memory sink for deterministic tests and local experiments."""

    def __init__(self) -> None:
        self._envelopes_by_state_id: dict[str, Phase1StateEnvelope] = {}

    def persist(self, envelope: Phase1StateEnvelope) -> None:
        # Store a deep copy to decouple sink state from caller-side references.
        self._envelopes_by_state_id[envelope.state_id] = envelope.model_copy(deep=True)

    def get(self, state_id: str) -> Phase1StateEnvelope | None:
        """Get one persisted envelope by state_id."""

        return self._envelopes_by_state_id.get(state_id)

    def list_state_ids(self) -> tuple[str, ...]:
        """List persisted state ids in stable sorted order."""

        return tuple(sorted(self._envelopes_by_state_id))

    def list_envelopes(self) -> tuple[Phase1StateEnvelope, ...]:
        """List persisted envelopes in stable state_id order."""

        return tuple(
            self._envelopes_by_state_id[state_id]
            for state_id in sorted(self._envelopes_by_state_id)
        )

    def __len__(self) -> int:
        return len(self._envelopes_by_state_id)


__all__ = [
    "InMemoryStateSink",
    "NoOpStateSink",
    "StateSink",
]
