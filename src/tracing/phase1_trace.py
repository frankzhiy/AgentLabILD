"""Phase 1 trace events for LLM-backed adapter agents."""

from __future__ import annotations

import hashlib
from collections.abc import Callable, Mapping
from datetime import datetime
from enum import StrEnum
from typing import Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator

from ..schemas.common import NonEmptyStr
from ..utils.time import utc_now


class Phase1TraceStep(StrEnum):
    """Traceable runtime steps for Phase 1 adapter agents."""

    PROMPT_HANDOFF = "prompt_handoff"
    RUNNER_RESULT = "runner_result"
    ADAPTER_RESULT = "adapter_result"
    MANUAL_REVIEW_DECISION = "manual_review_decision"


class Phase1TraceStatus(StrEnum):
    """Trace status values independent of clinical state authority."""

    HANDED_OFF = "handed_off"
    SUCCESS = "success"
    FAILURE = "failure"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class Phase1TraceEvent(BaseModel):
    """One privacy-conscious Phase 1 trace event."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    event_id: NonEmptyStr
    sequence_index: int = Field(ge=0)
    step_name: Phase1TraceStep
    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    status: Phase1TraceStatus
    agent_name: NonEmptyStr
    schema_name: str | None = None
    attempt_count: int | None = Field(default=None, ge=1)
    model_name: str | None = None
    error_messages: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warning_messages: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    artifact_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    artifact_hashes: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    created_at: datetime = Field(default_factory=utc_now)
    captured_payload: dict[str, object] | None = None

    @field_validator("schema_name", "model_name", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None


@runtime_checkable
class Phase1TraceRecorder(Protocol):
    """Protocol for Phase 1 trace event recorders."""

    def record_event(
        self,
        *,
        step_name: Phase1TraceStep,
        case_id: str,
        stage_id: str,
        status: Phase1TraceStatus,
        agent_name: str,
        schema_name: str | None = None,
        attempt_count: int | None = None,
        model_name: str | None = None,
        error_messages: tuple[str, ...] = (),
        warning_messages: tuple[str, ...] = (),
        artifact_ids: tuple[str, ...] = (),
        artifact_hashes: tuple[str, ...] = (),
        captured_payload: Mapping[str, object] | None = None,
    ) -> Phase1TraceEvent | None:
        """Record one event and return the stored event when enabled."""


class InMemoryPhase1TraceRecorder:
    """Deterministic in-memory Phase 1 trace recorder."""

    def __init__(
        self,
        *,
        enabled: bool = True,
        capture_payloads: bool = False,
        time_source: Callable[[], datetime] = utc_now,
    ) -> None:
        self._enabled = enabled
        self._capture_payloads = capture_payloads
        self._time_source = time_source
        self._events: list[Phase1TraceEvent] = []

    @property
    def enabled(self) -> bool:
        return self._enabled

    @property
    def capture_payloads(self) -> bool:
        return self._capture_payloads

    def record_event(
        self,
        *,
        step_name: Phase1TraceStep,
        case_id: str,
        stage_id: str,
        status: Phase1TraceStatus,
        agent_name: str,
        schema_name: str | None = None,
        attempt_count: int | None = None,
        model_name: str | None = None,
        error_messages: tuple[str, ...] = (),
        warning_messages: tuple[str, ...] = (),
        artifact_ids: tuple[str, ...] = (),
        artifact_hashes: tuple[str, ...] = (),
        captured_payload: Mapping[str, object] | None = None,
    ) -> Phase1TraceEvent | None:
        if not self._enabled:
            return None

        sequence_index = len(self._events)
        event = Phase1TraceEvent(
            event_id=f"event-trace-{sequence_index:06d}",
            sequence_index=sequence_index,
            step_name=step_name,
            case_id=case_id,
            stage_id=stage_id,
            status=status,
            agent_name=agent_name,
            schema_name=schema_name,
            attempt_count=attempt_count,
            model_name=model_name,
            error_messages=error_messages,
            warning_messages=warning_messages,
            artifact_ids=artifact_ids,
            artifact_hashes=artifact_hashes,
            created_at=self._time_source(),
            captured_payload=(
                dict(captured_payload)
                if self._capture_payloads and captured_payload is not None
                else None
            ),
        )
        self._events.append(event)
        return event

    def list_events(self) -> tuple[Phase1TraceEvent, ...]:
        return tuple(self._events)


def hash_text_artifact(*, label: str, text: str) -> str:
    """Build a stable hash label without retaining the raw artifact text."""

    cleaned_label = label.strip()
    if not cleaned_label:
        raise ValueError("label must not be empty")

    digest = hashlib.sha256(text.encode("utf-8")).hexdigest()
    return f"{cleaned_label}:sha256:{digest}"


def safe_record_phase1_event(
    recorder: Phase1TraceRecorder | None,
    *,
    step_name: Phase1TraceStep,
    case_id: str,
    stage_id: str,
    status: Phase1TraceStatus,
    agent_name: str,
    schema_name: str | None = None,
    attempt_count: int | None = None,
    model_name: str | None = None,
    error_messages: tuple[str, ...] = (),
    warning_messages: tuple[str, ...] = (),
    artifact_ids: tuple[str, ...] = (),
    artifact_hashes: tuple[str, ...] = (),
) -> None:
    """Best-effort trace emission that cannot affect agent behavior."""

    if recorder is None:
        return

    try:
        recorder.record_event(
            step_name=step_name,
            case_id=case_id,
            stage_id=stage_id,
            status=status,
            agent_name=agent_name,
            schema_name=schema_name,
            attempt_count=attempt_count,
            model_name=model_name,
            error_messages=error_messages,
            warning_messages=warning_messages,
            artifact_ids=artifact_ids,
            artifact_hashes=artifact_hashes,
        )
    except Exception:
        return


__all__ = [
    "InMemoryPhase1TraceRecorder",
    "Phase1TraceEvent",
    "Phase1TraceRecorder",
    "Phase1TraceStatus",
    "Phase1TraceStep",
    "hash_text_artifact",
    "safe_record_phase1_event",
]
