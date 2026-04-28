"""Tests for structured LLM retry policy."""

from __future__ import annotations

import pytest
from pydantic import ValidationError

from src.llm.retry_policy import (
    StructuredLLMFailureKind,
    StructuredLLMRetryPolicy,
)


def test_retry_policy_retries_transport_timeout_and_malformed_json_only() -> None:
    policy = StructuredLLMRetryPolicy(max_attempts=3)

    assert policy.should_retry(
        failure_kind=StructuredLLMFailureKind.TRANSPORT,
        attempt_number=1,
    )
    assert policy.should_retry(
        failure_kind=StructuredLLMFailureKind.TIMEOUT,
        attempt_number=1,
    )
    assert policy.should_retry(
        failure_kind=StructuredLLMFailureKind.MALFORMED_JSON,
        attempt_number=1,
    )
    assert not policy.should_retry(
        failure_kind=StructuredLLMFailureKind.SCHEMA_MISMATCH,
        attempt_number=1,
    )
    assert not policy.should_retry(
        failure_kind=StructuredLLMFailureKind.CLIENT_ERROR,
        attempt_number=1,
    )


def test_retry_policy_stops_at_max_attempts() -> None:
    policy = StructuredLLMRetryPolicy(max_attempts=2)

    assert policy.should_retry(
        failure_kind=StructuredLLMFailureKind.TRANSPORT,
        attempt_number=1,
    )
    assert not policy.should_retry(
        failure_kind=StructuredLLMFailureKind.TRANSPORT,
        attempt_number=2,
    )


def test_retry_policy_rejects_non_retryable_configured_kinds() -> None:
    with pytest.raises(ValidationError):
        StructuredLLMRetryPolicy(
            retryable_failure_kinds=(StructuredLLMFailureKind.SCHEMA_MISMATCH,)
        )


def test_retry_policy_rejects_duplicate_retryable_kinds() -> None:
    with pytest.raises(ValidationError):
        StructuredLLMRetryPolicy(
            retryable_failure_kinds=(
                StructuredLLMFailureKind.TRANSPORT,
                StructuredLLMFailureKind.TRANSPORT,
            )
        )


def test_retry_policy_rejects_invalid_attempt_number() -> None:
    policy = StructuredLLMRetryPolicy()

    with pytest.raises(ValueError, match="attempt_number"):
        policy.should_retry(
            failure_kind=StructuredLLMFailureKind.TRANSPORT,
            attempt_number=0,
        )
