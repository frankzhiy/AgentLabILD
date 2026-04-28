"""Retry policy for structured LLM calls."""

from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator


class StructuredLLMFailureKind(StrEnum):
    """Failure kinds understood by the structured runner retry policy."""

    TRANSPORT = "transport"
    TIMEOUT = "timeout"
    MALFORMED_JSON = "malformed_json"
    CLIENT_ERROR = "client_error"
    EMPTY_RESPONSE = "empty_response"
    SCHEMA_MISMATCH = "schema_mismatch"


DEFAULT_RETRYABLE_FAILURE_KINDS: tuple[StructuredLLMFailureKind, ...] = (
    StructuredLLMFailureKind.TRANSPORT,
    StructuredLLMFailureKind.TIMEOUT,
    StructuredLLMFailureKind.MALFORMED_JSON,
)


class StructuredLLMRetryPolicy(BaseModel):
    """Retry policy scoped to provider/transport and JSON-shape failures only."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    max_attempts: int = Field(default=2, ge=1)
    retryable_failure_kinds: tuple[StructuredLLMFailureKind, ...] = Field(
        default=DEFAULT_RETRYABLE_FAILURE_KINDS
    )

    @field_validator("retryable_failure_kinds")
    @classmethod
    def validate_retryable_failure_kinds(
        cls,
        value: tuple[StructuredLLMFailureKind, ...],
    ) -> tuple[StructuredLLMFailureKind, ...]:
        if len(set(value)) != len(value):
            raise ValueError("retryable_failure_kinds must not contain duplicates")

        allowed = set(DEFAULT_RETRYABLE_FAILURE_KINDS)
        disallowed = sorted(kind.value for kind in value if kind not in allowed)
        if disallowed:
            raise ValueError(
                "retryable_failure_kinds may only include transport, timeout, or malformed_json"
            )

        return value

    def should_retry(
        self,
        *,
        failure_kind: StructuredLLMFailureKind,
        attempt_number: int,
    ) -> bool:
        """Return whether another attempt is allowed after `attempt_number`."""

        if attempt_number < 1:
            raise ValueError("attempt_number must be >= 1")

        if attempt_number >= self.max_attempts:
            return False

        return failure_kind in self.retryable_failure_kinds


__all__ = [
    "DEFAULT_RETRYABLE_FAILURE_KINDS",
    "StructuredLLMFailureKind",
    "StructuredLLMRetryPolicy",
]
