"""Tests for the LLM-backed Hypothesis Board Bootstrapper agent."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass

from src.adapters.hypothesis_board_bootstrapper_adapter import (
    HypothesisBoardBootstrapperStatus,
)
from src.agents.hypothesis_board_bootstrapper_agent import (
    HYPOTHESIS_BOARD_BOOTSTRAP_SCHEMA_NAME,
    HYPOTHESIS_BOARD_BOOTSTRAPPER_AGENT_NAME,
    HypothesisBoardBootstrapperAgent,
)
from src.llm.retry_policy import StructuredLLMFailureKind
from src.llm.structured_runner import StructuredLLMRunnerResult, StructuredLLMStatus
from src.tracing.phase1_trace import (
    InMemoryPhase1TraceRecorder,
    Phase1TraceStatus,
    Phase1TraceStep,
)
from tests.test_hypothesis_board_bootstrapper_adapter import (
    _base_input,
    valid_hypothesis_board_bootstrap_payload,
)


@dataclass
class FakeStructuredRunner:
    result: StructuredLLMRunnerResult

    def __post_init__(self) -> None:
        self.prompts: list[str] = []
        self.output_schemas: list[dict[str, object] | None] = []
        self.metadata: list[dict[str, object] | None] = []

    def run_prompt(
        self,
        prompt: str,
        *,
        output_schema: dict[str, object] | None = None,
        metadata: dict[str, object] | None = None,
    ) -> StructuredLLMRunnerResult:
        self.prompts.append(prompt)
        self.output_schemas.append(output_schema)
        self.metadata.append(metadata)
        return self.result


def test_hypothesis_board_bootstrapper_agent_success_path_calls_runner_and_adapter() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.SUCCESS,
            parsed=valid_hypothesis_board_bootstrap_payload(),
            attempts=1,
        )
    )
    agent = HypothesisBoardBootstrapperAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.ACCEPTED
    assert result.draft is not None
    assert "{{" not in fake_runner.prompts[0]
    assert "}}" not in fake_runner.prompts[0]
    assert fake_runner.output_schemas[0] is not None
    assert fake_runner.output_schemas[0]["title"] == "HypothesisBoardBootstrapDraft"
    assert fake_runner.metadata[0] == {
        "agent_name": HYPOTHESIS_BOARD_BOOTSTRAPPER_AGENT_NAME,
        "case_id": "case-001",
        "stage_id": "stage-001",
        "schema_name": HYPOTHESIS_BOARD_BOOTSTRAP_SCHEMA_NAME,
    }


def test_hypothesis_board_bootstrapper_agent_returns_adapter_rejection() -> None:
    payload = deepcopy(valid_hypothesis_board_bootstrap_payload())
    payload["final_diagnosis"] = "IPF"
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.SUCCESS,
            parsed=payload,
            attempts=1,
        )
    )
    agent = HypothesisBoardBootstrapperAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.REJECTED
    assert result.draft is None
    assert any("final_diagnosis" in error for error in result.errors)


def test_hypothesis_board_bootstrapper_agent_runner_failure_returns_manual_review() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.FAILURE,
            parsed=None,
            attempts=1,
            errors=("runner failed",),
            failure_kind=StructuredLLMFailureKind.TRANSPORT,
        )
    )
    agent = HypothesisBoardBootstrapperAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.MANUAL_REVIEW
    assert result.draft is None
    assert result.errors == ("runner failed",)


def test_hypothesis_board_bootstrapper_agent_runner_manual_review_returns_manual_review() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.MANUAL_REVIEW,
            parsed=None,
            attempts=1,
            errors=("needs review",),
            failure_kind=StructuredLLMFailureKind.EMPTY_RESPONSE,
        )
    )
    agent = HypothesisBoardBootstrapperAgent(fake_runner)  # type: ignore[arg-type]

    result = agent.run(_base_input())

    assert result.status is HypothesisBoardBootstrapperStatus.MANUAL_REVIEW
    assert result.draft is None
    assert result.errors == ("needs review",)


def test_hypothesis_board_bootstrapper_agent_emits_trace_events_on_success() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.SUCCESS,
            parsed=valid_hypothesis_board_bootstrap_payload(),
            attempts=1,
            raw_response_id="response-001",
            model="fake-model",
        )
    )
    recorder = InMemoryPhase1TraceRecorder()
    agent = HypothesisBoardBootstrapperAgent(
        fake_runner,  # type: ignore[arg-type]
        trace_recorder=recorder,
    )

    result = agent.run(_base_input())

    events = recorder.list_events()
    assert result.status is HypothesisBoardBootstrapperStatus.ACCEPTED
    assert [event.step_name for event in events] == [
        Phase1TraceStep.PROMPT_HANDOFF,
        Phase1TraceStep.RUNNER_RESULT,
        Phase1TraceStep.ADAPTER_RESULT,
    ]
    assert [event.status for event in events] == [
        Phase1TraceStatus.HANDED_OFF,
        Phase1TraceStatus.SUCCESS,
        Phase1TraceStatus.SUCCESS,
    ]
    assert events[0].artifact_hashes[0].startswith("prompt:sha256:")
    assert events[1].artifact_ids == ("response-001",)
    assert events[1].model_name == "fake-model"
    assert events[2].artifact_ids == ("hypothesis_board_bootstrap_draft-001",)
    assert "Chronic cough" not in "".join(
        event.model_dump_json() for event in events
    )


def test_hypothesis_board_bootstrapper_agent_emits_trace_events_on_runner_failure() -> None:
    fake_runner = FakeStructuredRunner(
        StructuredLLMRunnerResult(
            status=StructuredLLMStatus.FAILURE,
            parsed=None,
            attempts=2,
            errors=("runner failed",),
            failure_kind=StructuredLLMFailureKind.TRANSPORT,
            model="fake-model",
        )
    )
    recorder = InMemoryPhase1TraceRecorder()
    agent = HypothesisBoardBootstrapperAgent(
        fake_runner,  # type: ignore[arg-type]
        trace_recorder=recorder,
    )

    result = agent.run(_base_input())

    events = recorder.list_events()
    assert result.status is HypothesisBoardBootstrapperStatus.MANUAL_REVIEW
    assert [event.step_name for event in events] == [
        Phase1TraceStep.PROMPT_HANDOFF,
        Phase1TraceStep.RUNNER_RESULT,
        Phase1TraceStep.MANUAL_REVIEW_DECISION,
    ]
    assert [event.status for event in events] == [
        Phase1TraceStatus.HANDED_OFF,
        Phase1TraceStatus.FAILURE,
        Phase1TraceStatus.MANUAL_REVIEW,
    ]
    assert events[1].attempt_count == 2
    assert events[1].error_messages == ("runner failed",)
    assert events[2].error_messages == ("runner failed",)
