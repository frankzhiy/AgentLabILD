"""Phase 1 raw-text intake schemas.

These models represent pre-authoritative intake artifacts and do not replace
the existing Phase1StateEnvelope write boundary.
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    CASE_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
    validate_id_pattern,
)
from .stage import StageType, TriggerType


INPUT_EVENT_ID_PATTERN = re.compile(r"^input_event[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_RESOLUTION_ID_PATTERN = re.compile(
    r"^stage_resolution[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)


class RawInputMode(StrEnum):
    """Mode taxonomy for one raw free-text intake event."""

    INITIAL_SUBMISSION = "initial_submission"
    APPEND = "append"
    CORRECTION = "correction"
    REPLACEMENT = "replacement"


class SourceDocumentType(StrEnum):
    """Source document type taxonomy for intake-origin text units."""

    FREE_TEXT_CASE_NOTE = "free_text_case_note"
    HRCT_REPORT_TEXT = "hrct_report_text"
    PATHOLOGY_REPORT_TEXT = "pathology_report_text"
    LAB_SUMMARY_TEXT = "lab_summary_text"
    FOLLOWUP_NOTE_TEXT = "followup_note_text"
    TREATMENT_NOTE_TEXT = "treatment_note_text"
    OTHER_TEXT = "other_text"


class RawIntakeStatus(StrEnum):
    """Decision status for one raw-text intake attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class RawInputEvent(BaseModel):
    """One immutable raw free-text intake event from external user input."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["raw_input_event"] = "raw_input_event"
    input_event_id: NonEmptyStr
    case_id: NonEmptyStr
    arrival_index: int = Field(ge=0)
    raw_text: NonEmptyStr
    received_at: datetime
    input_mode: RawInputMode
    parent_input_event_id: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("input_event_id")
    @classmethod
    def validate_input_event_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=INPUT_EVENT_ID_PATTERN,
            field_name="input_event_id",
            example="input_event_001 or input_event-001",
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

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("raw_text must not be empty")
        return value

    @field_validator("parent_input_event_id", mode="before")
    @classmethod
    def normalize_parent_input_event_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("parent_input_event_id")
    @classmethod
    def validate_parent_input_event_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_id_pattern(
            value,
            pattern=INPUT_EVENT_ID_PATTERN,
            field_name="parent_input_event_id",
            example="input_event_001 or input_event-001",
        )

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_parent_boundary(self) -> "RawInputEvent":
        if (
            self.input_mode is RawInputMode.INITIAL_SUBMISSION
            and self.parent_input_event_id is not None
        ):
            raise ValueError(
                "initial_submission input must not define parent_input_event_id"
            )

        return self


class SourceDocument(BaseModel):
    """Immutable source text unit referenced by evidence source_doc_id."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["source_document"] = "source_document"
    source_doc_id: NonEmptyStr
    case_id: NonEmptyStr
    input_event_id: NonEmptyStr
    document_type: SourceDocumentType
    raw_text: NonEmptyStr
    created_at: datetime
    chunk_strategy: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("source_doc_id")
    @classmethod
    def validate_source_doc_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=SOURCE_DOC_ID_PATTERN,
            field_name="source_doc_id",
            example="doc_001 or doc-001",
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

    @field_validator("input_event_id")
    @classmethod
    def validate_input_event_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=INPUT_EVENT_ID_PATTERN,
            field_name="input_event_id",
            example="input_event_001 or input_event-001",
        )

    @field_validator("raw_text")
    @classmethod
    def validate_raw_text_non_empty(cls, value: str) -> str:
        if not value:
            raise ValueError("raw_text must not be empty")
        return value

    @field_validator("chunk_strategy", mode="before")
    @classmethod
    def normalize_chunk_strategy(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)


class StageResolutionReport(BaseModel):
    """Record of mapping intake artifacts to one clinical stage candidate."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["stage_resolution_report"] = "stage_resolution_report"
    stage_resolution_id: NonEmptyStr
    case_id: NonEmptyStr
    candidate_stage_id: NonEmptyStr
    candidate_stage_type: StageType
    candidate_trigger_type: TriggerType
    bound_input_event_ids: tuple[NonEmptyStr, ...]
    bound_source_doc_ids: tuple[NonEmptyStr, ...]
    resolution_confidence: float = Field(ge=0.0, le=1.0)
    manual_review_required: bool = False
    resolution_rationale: str | None = None
    created_at: datetime

    @field_validator("stage_resolution_id")
    @classmethod
    def validate_stage_resolution_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_RESOLUTION_ID_PATTERN,
            field_name="stage_resolution_id",
            example="stage_resolution_001 or stage_resolution-001",
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

    @field_validator("candidate_stage_id")
    @classmethod
    def validate_candidate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="candidate_stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("bound_input_event_ids")
    @classmethod
    def validate_bound_input_event_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("bound_input_event_ids must not be empty")

        duplicates = find_duplicate_items(value)
        if duplicates:
            raise ValueError("bound_input_event_ids must not contain duplicates")

        for input_event_id in value:
            validate_id_pattern(
                input_event_id,
                pattern=INPUT_EVENT_ID_PATTERN,
                field_name="bound_input_event_ids[]",
                example="input_event_001 or input_event-001",
            )

        return value

    @field_validator("bound_source_doc_ids")
    @classmethod
    def validate_bound_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("bound_source_doc_ids must not be empty")

        duplicates = find_duplicate_items(value)
        if duplicates:
            raise ValueError("bound_source_doc_ids must not contain duplicates")

        for source_doc_id in value:
            validate_id_pattern(
                source_doc_id,
                pattern=SOURCE_DOC_ID_PATTERN,
                field_name="bound_source_doc_ids[]",
                example="doc_001 or doc-001",
            )

        return value

    @field_validator("resolution_rationale", mode="before")
    @classmethod
    def normalize_resolution_rationale(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_manual_review_requirement(self) -> "StageResolutionReport":
        if self.resolution_confidence < 0.75 and not self.manual_review_required:
            raise ValueError(
                "manual_review_required must be true when resolution_confidence < 0.75"
            )

        return self


class RawIntakeDecision(BaseModel):
    """Decision object for one raw-text intake attempt."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: RawIntakeStatus
    raw_input_event: RawInputEvent | None
    source_document: SourceDocument | None
    summary: NonEmptyStr
    blocking_errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_decision_consistency(self) -> "RawIntakeDecision":
        if self.status is RawIntakeStatus.ACCEPTED:
            if self.raw_input_event is None or self.source_document is None:
                raise ValueError(
                    "accepted intake requires both raw_input_event and source_document"
                )
            if self.blocking_errors:
                raise ValueError("accepted intake must not carry blocking_errors")

        if self.status is RawIntakeStatus.REJECTED:
            if self.raw_input_event is not None or self.source_document is not None:
                raise ValueError(
                    "rejected intake must not include raw_input_event or source_document"
                )
            if not self.blocking_errors:
                raise ValueError("rejected intake must include blocking_errors")

        if self.raw_input_event is not None and self.source_document is not None:
            if self.raw_input_event.input_event_id != self.source_document.input_event_id:
                raise ValueError(
                    "raw_input_event and source_document must share the same input_event_id"
                )
            if self.raw_input_event.case_id != self.source_document.case_id:
                raise ValueError(
                    "raw_input_event and source_document must share the same case_id"
                )

        return self


__all__ = [
    "INPUT_EVENT_ID_PATTERN",
    "RawInputEvent",
    "RawInputMode",
    "RawIntakeDecision",
    "RawIntakeStatus",
    "STAGE_RESOLUTION_ID_PATTERN",
    "SourceDocument",
    "SourceDocumentType",
    "StageResolutionReport",
]
