"""Tests for Phase 1 trace event helpers."""

from __future__ import annotations

from datetime import UTC, datetime

import pytest
from pydantic import ValidationError

from src.tracing.phase1_trace import (
    InMemoryPhase1TraceRecorder,
    Phase1TraceEvent,
    Phase1TraceStatus,
    Phase1TraceStep,
    hash_text_artifact,
    safe_record_phase1_event,
)


def _fixed_now() -> datetime:
    return datetime(2026, 4, 28, 9, 0, 0, tzinfo=UTC)


def _record_minimal_event(
    recorder: InMemoryPhase1TraceRecorder,
    *,
    step_name: Phase1TraceStep = Phase1TraceStep.PROMPT_HANDOFF,
    status: Phase1TraceStatus = Phase1TraceStatus.HANDED_OFF,
) -> Phase1TraceEvent:
    event = recorder.record_event(
        step_name=step_name,
        case_id="case-001",
        stage_id="stage-001",
        status=status,
        agent_name="case_structurer_agent",
        schema_name="CaseStructuringDraft",
    )
    assert event is not None
    return event


def test_in_memory_recorder_stores_ordered_events() -> None:
    recorder = InMemoryPhase1TraceRecorder(time_source=_fixed_now)

    first = _record_minimal_event(recorder)
    second = _record_minimal_event(
        recorder,
        step_name=Phase1TraceStep.RUNNER_RESULT,
        status=Phase1TraceStatus.SUCCESS,
    )

    events = recorder.list_events()
    assert events == (first, second)
    assert [event.sequence_index for event in events] == [0, 1]
    assert [event.event_id for event in events] == [
        "event-trace-000000",
        "event-trace-000001",
    ]
    assert all(event.created_at == _fixed_now() for event in events)


def test_recorder_can_be_disabled_or_omitted() -> None:
    disabled_recorder = InMemoryPhase1TraceRecorder(enabled=False)

    event = disabled_recorder.record_event(
        step_name=Phase1TraceStep.PROMPT_HANDOFF,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.HANDED_OFF,
        agent_name="case_structurer_agent",
    )

    assert event is None
    assert disabled_recorder.list_events() == ()
    safe_record_phase1_event(
        None,
        step_name=Phase1TraceStep.PROMPT_HANDOFF,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.HANDED_OFF,
        agent_name="case_structurer_agent",
    )


def test_safe_record_swallow_recorder_failures() -> None:
    class RaisingRecorder:
        def record_event(self, **_: object) -> None:
            raise RuntimeError("trace sink unavailable")

    safe_record_phase1_event(
        RaisingRecorder(),  # type: ignore[arg-type]
        step_name=Phase1TraceStep.PROMPT_HANDOFF,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.HANDED_OFF,
        agent_name="case_structurer_agent",
    )


def test_event_model_rejects_empty_step_or_status_identifiers() -> None:
    with pytest.raises(ValidationError):
        Phase1TraceEvent(
            event_id="event-trace-001",
            sequence_index=0,
            step_name="",
            case_id="case-001",
            stage_id="stage-001",
            status=Phase1TraceStatus.SUCCESS,
            agent_name="case_structurer_agent",
        )

    with pytest.raises(ValidationError):
        Phase1TraceEvent(
            event_id="event-trace-001",
            sequence_index=0,
            step_name=Phase1TraceStep.RUNNER_RESULT,
            case_id="case-001",
            stage_id="stage-001",
            status="",
            agent_name="case_structurer_agent",
        )


def test_default_event_does_not_store_raw_prompt_or_clinical_text() -> None:
    raw_prompt = "Prompt includes raw clinical text: Patient has chronic cough."
    recorder = InMemoryPhase1TraceRecorder()

    event = recorder.record_event(
        step_name=Phase1TraceStep.PROMPT_HANDOFF,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.HANDED_OFF,
        agent_name="case_structurer_agent",
        artifact_hashes=(hash_text_artifact(label="prompt", text=raw_prompt),),
        captured_payload={
            "prompt": raw_prompt,
            "raw_text": "Patient has chronic cough.",
        },
    )

    assert event is not None
    dumped = event.model_dump_json()
    assert raw_prompt not in dumped
    assert "Patient has chronic cough" not in dumped
    assert "prompt:sha256:" in dumped
    assert event.captured_payload is None


def test_optional_artifact_hashes_and_ids_are_allowed() -> None:
    recorder = InMemoryPhase1TraceRecorder()

    event = recorder.record_event(
        step_name=Phase1TraceStep.RUNNER_RESULT,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.SUCCESS,
        agent_name="case_structurer_agent",
        schema_name="CaseStructuringDraft",
        attempt_count=2,
        model_name="fake-model",
        artifact_ids=("response-001",),
        artifact_hashes=("prompt:sha256:" + "a" * 64,),
    )

    assert event is not None
    assert event.artifact_ids == ("response-001",)
    assert event.artifact_hashes == ("prompt:sha256:" + "a" * 64,)
    assert event.attempt_count == 2
    assert event.model_name == "fake-model"


def test_payload_capture_requires_opt_in() -> None:
    default_recorder = InMemoryPhase1TraceRecorder()
    default_event = default_recorder.record_event(
        step_name=Phase1TraceStep.ADAPTER_RESULT,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.SUCCESS,
        agent_name="case_structurer_agent",
        captured_payload={"adapter_status": "accepted"},
    )

    capture_recorder = InMemoryPhase1TraceRecorder(capture_payloads=True)
    captured_event = capture_recorder.record_event(
        step_name=Phase1TraceStep.ADAPTER_RESULT,
        case_id="case-001",
        stage_id="stage-001",
        status=Phase1TraceStatus.SUCCESS,
        agent_name="case_structurer_agent",
        captured_payload={"adapter_status": "accepted"},
    )

    assert default_event is not None
    assert default_event.captured_payload is None
    assert captured_event is not None
    assert captured_event.captured_payload == {"adapter_status": "accepted"}
