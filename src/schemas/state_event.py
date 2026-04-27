"""State-event schema for Phase 1-5 versioning and history tracing."""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    CASE_ID_PATTERN,
    EVENT_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    STATE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
    validate_id_pattern,
)
from .intake import INPUT_EVENT_ID_PATTERN


class StateEventType(StrEnum):
    """System event taxonomy for Phase 1 state history."""

    SOURCE_DOCUMENT_RECEIVED = "source_document_received"
    CANDIDATE_STATE_SUBMITTED = "candidate_state_submitted"
    STATE_VALIDATION_ACCEPTED = "state_validation_accepted"
    STATE_VALIDATION_REJECTED = "state_validation_rejected"
    STATE_PERSISTED = "state_persisted"
    SNAPSHOT_CREATED = "snapshot_created"


class StateEvent(BaseModel):
    """Append-only state event for traceable state lifecycle."""

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    kind: Literal["state_event"] = "state_event"
    event_id: NonEmptyStr
    event_type: StateEventType
    case_id: NonEmptyStr
    stage_id: str | None = None
    state_id: str | None = None
    parent_state_id: str | None = None
    state_version: int | None = Field(default=None, ge=1)
    source_doc_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    input_event_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    created_at: datetime
    created_by: NonEmptyStr
    non_authoritative_note: str | None = None

    @field_validator("event_id")
    @classmethod
    def validate_event_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EVENT_ID_PATTERN,
            field_name="event_id",
            example="event_001 or event-001",
        )

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("stage_id", mode="before")
    @classmethod
    def normalize_stage_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("state_id", mode="before")
    @classmethod
    def normalize_state_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("state_id")
    @classmethod
    def validate_state_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_id_pattern(
            value,
            pattern=STATE_ID_PATTERN,
            field_name="state_id",
            example="state_001 or state-001",
        )

    @field_validator("parent_state_id", mode="before")
    @classmethod
    def normalize_parent_state_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("parent_state_id")
    @classmethod
    def validate_parent_state_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_id_pattern(
            value,
            pattern=STATE_ID_PATTERN,
            field_name="parent_state_id",
            example="state_001 or state-001",
        )

    @field_validator("source_doc_ids")
    @classmethod
    def validate_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        duplicates = find_duplicate_items(value)
        if duplicates:
            raise ValueError("source_doc_ids must not contain duplicates")

        for source_doc_id in value:
            validate_id_pattern(
                source_doc_id,
                pattern=SOURCE_DOC_ID_PATTERN,
                field_name="source_doc_ids[]",
                example="doc_001 or doc-001",
            )

        return value

    @field_validator("input_event_ids")
    @classmethod
    def validate_input_event_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        duplicates = find_duplicate_items(value)
        if duplicates:
            raise ValueError("input_event_ids must not contain duplicates")

        for input_event_id in value:
            validate_id_pattern(
                input_event_id,
                pattern=INPUT_EVENT_ID_PATTERN,
                field_name="input_event_ids[]",
                example="input_event_001 or input_event-001",
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_event_consistency(self) -> "StateEvent":
        if self.parent_state_id is not None and self.parent_state_id == self.state_id:
            raise ValueError("parent_state_id must not equal state_id")

        if self.event_type is StateEventType.STATE_PERSISTED:
            if self.state_id is None or self.state_version is None:
                raise ValueError(
                    "state_persisted event requires both state_id and state_version"
                )

        if self.event_type is StateEventType.SOURCE_DOCUMENT_RECEIVED:
            if not self.source_doc_ids:
                raise ValueError(
                    "source_document_received event requires at least one source_doc_id"
                )

        return self


__all__ = ["StateEvent", "StateEventType"]
