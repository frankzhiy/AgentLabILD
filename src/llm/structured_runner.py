"""Reusable structured LLM runner with injectable clients.

The runner owns provider-call semantics for this package. It accepts rendered
prompts or rendered messages, delegates the actual call to an injected client,
and returns a normalized result object instead of raw provider responses.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from enum import StrEnum
from typing import Any, Literal, Protocol, runtime_checkable

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .provider_config import LLMProviderConfig
from .retry_policy import StructuredLLMFailureKind, StructuredLLMRetryPolicy


class StructuredLLMStatus(StrEnum):
    """Normalized structured runner status."""

    SUCCESS = "success"
    FAILURE = "failure"
    MANUAL_REVIEW = "manual_review"


class StructuredLLMTransportError(RuntimeError):
    """Retryable provider transport failure raised by injected clients."""


class StructuredLLMTimeoutError(TimeoutError):
    """Retryable provider timeout failure raised by injected clients."""


class StructuredLLMMessage(BaseModel):
    """One already-rendered chat message."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    role: Literal["system", "user", "assistant"]
    content: str = Field(min_length=1)


class StructuredLLMRequest(BaseModel):
    """Request passed to an injected structured LLM client."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    provider_config: LLMProviderConfig
    prompt: str | None = None
    messages: tuple[StructuredLLMMessage, ...] = Field(default_factory=tuple)
    output_schema: dict[str, object] | None = None
    metadata: dict[str, object] = Field(default_factory=dict)

    @field_validator("prompt", mode="before")
    @classmethod
    def normalize_prompt(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_prompt_or_messages(self) -> "StructuredLLMRequest":
        if self.prompt is None and not self.messages:
            raise ValueError("request requires prompt or messages")

        if self.prompt is not None and self.messages:
            raise ValueError("request must use either prompt or messages, not both")

        return self


class StructuredLLMClientResponse(BaseModel):
    """Provider-client response normalized at the client boundary."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    content: dict[str, object] | str
    raw_response_id: str | None = None
    model: str | None = None
    finish_reason: str | None = None


class StructuredLLMRunnerResult(BaseModel):
    """Structured output of one runner invocation."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    status: StructuredLLMStatus
    parsed: dict[str, object] | None = None
    attempts: int = Field(ge=1)
    errors: tuple[str, ...] = Field(default_factory=tuple)
    failure_kind: StructuredLLMFailureKind | None = None
    raw_response_id: str | None = None
    model: str | None = None
    finish_reason: str | None = None

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "StructuredLLMRunnerResult":
        if self.status is StructuredLLMStatus.SUCCESS:
            if self.parsed is None:
                raise ValueError("success result requires parsed payload")
            if self.errors:
                raise ValueError("success result must not include errors")
            if self.failure_kind is not None:
                raise ValueError("success result must not include failure_kind")

        if self.status is StructuredLLMStatus.FAILURE:
            if self.parsed is not None:
                raise ValueError("failure result must not include parsed payload")
            if not self.errors:
                raise ValueError("failure result requires errors")
            if self.failure_kind is None:
                raise ValueError("failure result requires failure_kind")

        if self.status is StructuredLLMStatus.MANUAL_REVIEW:
            if not self.errors:
                raise ValueError("manual_review result requires errors")

        return self


@runtime_checkable
class StructuredLLMClient(Protocol):
    """Protocol implemented by provider adapters or deterministic test fakes."""

    def complete(self, request: StructuredLLMRequest) -> StructuredLLMClientResponse | dict[str, object] | str:
        """Return a structured response for one rendered prompt/messages request."""


class StructuredLLMRunner:
    """Run structured LLM calls through an injected client and retry policy."""

    def __init__(
        self,
        *,
        client: StructuredLLMClient,
        provider_config: LLMProviderConfig,
        retry_policy: StructuredLLMRetryPolicy | None = None,
    ) -> None:
        self._client = client
        self._provider_config = provider_config
        self._retry_policy = retry_policy or StructuredLLMRetryPolicy()

    def run_prompt(
        self,
        prompt: str,
        *,
        output_schema: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> StructuredLLMRunnerResult:
        """Run one already-rendered prompt and parse the structured response."""

        return self.run_request(
            StructuredLLMRequest(
                provider_config=self._provider_config,
                prompt=prompt,
                output_schema=_copy_mapping(output_schema),
                metadata=_copy_mapping(metadata) or {},
            )
        )

    def run_messages(
        self,
        messages: tuple[StructuredLLMMessage, ...],
        *,
        output_schema: Mapping[str, object] | None = None,
        metadata: Mapping[str, object] | None = None,
    ) -> StructuredLLMRunnerResult:
        """Run already-rendered messages and parse the structured response."""

        return self.run_request(
            StructuredLLMRequest(
                provider_config=self._provider_config,
                messages=messages,
                output_schema=_copy_mapping(output_schema),
                metadata=_copy_mapping(metadata) or {},
            )
        )

    def run_request(
        self,
        request: StructuredLLMRequest,
    ) -> StructuredLLMRunnerResult:
        """Run one structured request using retry policy for allowed failures."""

        attempt_number = 0
        last_error = "structured LLM call failed"
        last_failure_kind = StructuredLLMFailureKind.CLIENT_ERROR

        while True:
            attempt_number += 1

            try:
                client_response = self._client.complete(request)
                response = _coerce_client_response(client_response)
                parsed = _parse_response_content(response.content)
                return StructuredLLMRunnerResult(
                    status=StructuredLLMStatus.SUCCESS,
                    parsed=parsed,
                    attempts=attempt_number,
                    raw_response_id=response.raw_response_id,
                    model=response.model,
                    finish_reason=response.finish_reason,
                )
            except StructuredLLMTimeoutError as exc:
                last_failure_kind = StructuredLLMFailureKind.TIMEOUT
                last_error = str(exc) or "structured LLM call timed out"
            except StructuredLLMTransportError as exc:
                last_failure_kind = StructuredLLMFailureKind.TRANSPORT
                last_error = str(exc) or "structured LLM transport failure"
            except json.JSONDecodeError as exc:
                last_failure_kind = StructuredLLMFailureKind.MALFORMED_JSON
                last_error = f"malformed JSON response: {exc.msg}"
            except ValueError as exc:
                last_failure_kind = StructuredLLMFailureKind.EMPTY_RESPONSE
                last_error = str(exc)
            except Exception as exc:  # pragma: no cover - defensive boundary
                last_failure_kind = StructuredLLMFailureKind.CLIENT_ERROR
                last_error = f"unexpected structured LLM client failure: {exc}"

            if not self._retry_policy.should_retry(
                failure_kind=last_failure_kind,
                attempt_number=attempt_number,
            ):
                status = (
                    StructuredLLMStatus.FAILURE
                    if last_failure_kind
                    in {
                        StructuredLLMFailureKind.TRANSPORT,
                        StructuredLLMFailureKind.TIMEOUT,
                        StructuredLLMFailureKind.CLIENT_ERROR,
                    }
                    else StructuredLLMStatus.MANUAL_REVIEW
                )
                return StructuredLLMRunnerResult(
                    status=status,
                    parsed=None,
                    attempts=attempt_number,
                    errors=(last_error,),
                    failure_kind=last_failure_kind,
                )


def _coerce_client_response(
    response: StructuredLLMClientResponse | dict[str, object] | str,
) -> StructuredLLMClientResponse:
    if isinstance(response, StructuredLLMClientResponse):
        return response

    if isinstance(response, dict | str):
        return StructuredLLMClientResponse(content=response)

    raise ValueError("structured LLM client returned unsupported response type")


def _parse_response_content(content: dict[str, object] | str) -> dict[str, object]:
    if isinstance(content, dict):
        return dict(content)

    cleaned = content.strip()
    if not cleaned:
        raise ValueError("structured LLM response content is empty")

    parsed = json.loads(cleaned)
    if not isinstance(parsed, dict):
        raise ValueError("structured LLM response JSON must be an object")

    return parsed


def _copy_mapping(value: Mapping[str, object] | None) -> dict[str, object] | None:
    if value is None:
        return None

    return dict(value)


__all__ = [
    "StructuredLLMClient",
    "StructuredLLMClientResponse",
    "StructuredLLMMessage",
    "StructuredLLMRequest",
    "StructuredLLMRunner",
    "StructuredLLMRunnerResult",
    "StructuredLLMStatus",
    "StructuredLLMTimeoutError",
    "StructuredLLMTransportError",
]
