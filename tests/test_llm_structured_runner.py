"""Tests for the injectable structured LLM runner."""

from __future__ import annotations

from dataclasses import dataclass

import pytest
from pydantic import ValidationError

from src.llm.provider_config import LLMProvider, LLMProviderConfig
from src.llm.retry_policy import StructuredLLMFailureKind, StructuredLLMRetryPolicy
from src.llm.structured_runner import (
    StructuredLLMClientResponse,
    StructuredLLMMessage,
    StructuredLLMRequest,
    StructuredLLMRunner,
    StructuredLLMStatus,
    StructuredLLMTimeoutError,
    StructuredLLMTransportError,
)


@dataclass
class FakeStructuredClient:
    responses: list[object]

    def __post_init__(self) -> None:
        self.requests: list[StructuredLLMRequest] = []

    def complete(self, request: StructuredLLMRequest) -> object:
        self.requests.append(request)
        response = self.responses.pop(0)
        if isinstance(response, BaseException):
            raise response
        return response


def _provider_config() -> LLMProviderConfig:
    return LLMProviderConfig(provider=LLMProvider.TEST, model="fake-model")


def test_runner_accepts_rendered_prompt_and_returns_parsed_dict() -> None:
    client = FakeStructuredClient(
        responses=[
            StructuredLLMClientResponse(
                content='{"draft_id": "draft-001", "case_id": "case-001"}',
                raw_response_id="resp-001",
                model="fake-model",
                finish_reason="stop",
            )
        ]
    )
    runner = StructuredLLMRunner(client=client, provider_config=_provider_config())

    result = runner.run_prompt(
        "rendered prompt",
        output_schema={"type": "object"},
        metadata={"case_id": "case-001"},
    )

    assert result.status is StructuredLLMStatus.SUCCESS
    assert result.parsed == {"draft_id": "draft-001", "case_id": "case-001"}
    assert result.attempts == 1
    assert result.raw_response_id == "resp-001"
    assert client.requests[0].prompt == "rendered prompt"
    assert client.requests[0].output_schema == {"type": "object"}
    assert client.requests[0].metadata == {"case_id": "case-001"}


def test_runner_accepts_rendered_messages() -> None:
    client = FakeStructuredClient(responses=[{"ok": True}])
    runner = StructuredLLMRunner(client=client, provider_config=_provider_config())
    messages = (
        StructuredLLMMessage(role="system", content="system prompt"),
        StructuredLLMMessage(role="user", content="user prompt"),
    )

    result = runner.run_messages(messages)

    assert result.status is StructuredLLMStatus.SUCCESS
    assert result.parsed == {"ok": True}
    assert client.requests[0].messages == messages
    assert client.requests[0].prompt is None


def test_runner_retries_malformed_json_and_then_succeeds() -> None:
    client = FakeStructuredClient(responses=["not-json", '{"ok": true}'])
    runner = StructuredLLMRunner(
        client=client,
        provider_config=_provider_config(),
        retry_policy=StructuredLLMRetryPolicy(max_attempts=2),
    )

    result = runner.run_prompt("rendered prompt")

    assert result.status is StructuredLLMStatus.SUCCESS
    assert result.parsed == {"ok": True}
    assert result.attempts == 2
    assert len(client.requests) == 2


def test_runner_retries_transport_error_and_returns_failure_when_exhausted() -> None:
    client = FakeStructuredClient(
        responses=[
            StructuredLLMTransportError("network down"),
            StructuredLLMTransportError("still down"),
        ]
    )
    runner = StructuredLLMRunner(
        client=client,
        provider_config=_provider_config(),
        retry_policy=StructuredLLMRetryPolicy(max_attempts=2),
    )

    result = runner.run_prompt("rendered prompt")

    assert result.status is StructuredLLMStatus.FAILURE
    assert result.parsed is None
    assert result.attempts == 2
    assert result.failure_kind is StructuredLLMFailureKind.TRANSPORT
    assert result.errors == ("still down",)


def test_runner_retries_timeout_error() -> None:
    client = FakeStructuredClient(
        responses=[
            StructuredLLMTimeoutError("timeout"),
            {"ok": True},
        ]
    )
    runner = StructuredLLMRunner(
        client=client,
        provider_config=_provider_config(),
        retry_policy=StructuredLLMRetryPolicy(max_attempts=2),
    )

    result = runner.run_prompt("rendered prompt")

    assert result.status is StructuredLLMStatus.SUCCESS
    assert result.parsed == {"ok": True}
    assert result.attempts == 2


def test_runner_returns_manual_review_for_non_object_json_without_auto_repair() -> None:
    client = FakeStructuredClient(responses=['["not", "an", "object"]'])
    runner = StructuredLLMRunner(client=client, provider_config=_provider_config())

    result = runner.run_prompt("rendered prompt")

    assert result.status is StructuredLLMStatus.MANUAL_REVIEW
    assert result.parsed is None
    assert result.failure_kind is StructuredLLMFailureKind.EMPTY_RESPONSE
    assert "JSON must be an object" in result.errors[0]


def test_runner_does_not_retry_non_retryable_empty_response() -> None:
    client = FakeStructuredClient(responses=["", '{"ok": true}'])
    runner = StructuredLLMRunner(
        client=client,
        provider_config=_provider_config(),
        retry_policy=StructuredLLMRetryPolicy(max_attempts=2),
    )

    result = runner.run_prompt("rendered prompt")

    assert result.status is StructuredLLMStatus.MANUAL_REVIEW
    assert result.failure_kind is StructuredLLMFailureKind.EMPTY_RESPONSE
    assert result.attempts == 1
    assert len(client.requests) == 1


def test_request_requires_prompt_or_messages_but_not_both() -> None:
    with pytest.raises(ValidationError):
        StructuredLLMRequest(provider_config=_provider_config())

    with pytest.raises(ValidationError):
        StructuredLLMRequest(
            provider_config=_provider_config(),
            prompt="prompt",
            messages=(StructuredLLMMessage(role="user", content="message"),),
        )
