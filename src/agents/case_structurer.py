"""Phase 1-4 Case Structurer adapter.

This module only prepares Case Structurer prompts and parses adapter payloads
into CaseStructuringDraft. It does not persist state and does not call write gate.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..adapters.case_structuring import CaseStructuringDraft
from ..schemas.common import (
    CASE_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
    validate_id_pattern,
)
from ..schemas.intake import SourceDocument
from ..schemas.stage import StageType, TriggerType

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "prompts"
    / "v2"
    / "case_structurer.md"
)

DEFAULT_PROMPT_CONTRACT = """You are a Case Structurer adapter, not a diagnostician.
Return only one CaseStructuringDraft-compatible JSON object.
Use only source documents and stage metadata provided in the input.
"""

FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "final_diagnosis",
        "differential_diagnosis",
        "hypotheses",
        "hypothesis_state",
        "evidence_atoms",
        "action_candidates",
        "action_plan",
        "arbitration_output",
        "treatment_recommendation",
        "confidence",
        "safety_decision",
        "conflict",
    }
)


class CaseStructurerStatus(StrEnum):
    """Decision status for one Case Structurer adapter parse attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class CaseStructurerInput(BaseModel):
    """Input contract for Case Structurer adapter invocation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: NonEmptyStr
    source_documents: tuple[SourceDocument, ...]
    stage_id: NonEmptyStr
    stage_index: int = Field(ge=0)
    stage_type: StageType
    trigger_type: TriggerType
    created_at: datetime
    clinical_time: datetime | None = None
    parent_stage_id: str | None = None
    stage_label: str | None = None
    previous_stage_summary: str | None = None

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_ID_PATTERN,
            field_name="case_id",
            example="case_001 or case-001",
        )

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("parent_stage_id", mode="before")
    @classmethod
    def normalize_parent_stage_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("parent_stage_id")
    @classmethod
    def validate_parent_stage_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None

        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="parent_stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("stage_label", mode="before")
    @classmethod
    def normalize_stage_label(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("previous_stage_summary", mode="before")
    @classmethod
    def normalize_previous_stage_summary(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @field_validator("source_documents")
    @classmethod
    def validate_source_document_ids_unique(
        cls, value: tuple[SourceDocument, ...]
    ) -> tuple[SourceDocument, ...]:
        duplicate_source_doc_ids = find_duplicate_items(
            source_document.source_doc_id for source_document in value
        )
        if duplicate_source_doc_ids:
            raise ValueError("source_documents must not contain duplicate source_doc_id")

        return value

    @model_validator(mode="after")
    def validate_source_document_alignment(self) -> "CaseStructurerInput":
        for source_document in self.source_documents:
            if source_document.case_id != self.case_id:
                raise ValueError("every source document case_id must equal input case_id")

        return self


class CaseStructurerResult(BaseModel):
    """Non-authoritative parse result for Case Structurer adapter output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: CaseStructurerStatus
    draft: CaseStructuringDraft | None = None
    errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "CaseStructurerResult":
        if self.status is CaseStructurerStatus.ACCEPTED:
            if self.draft is None:
                raise ValueError("accepted result requires draft")
            if self.errors:
                raise ValueError("accepted result must not include errors")

        if self.status is CaseStructurerStatus.REJECTED:
            if self.draft is not None:
                raise ValueError("rejected result must not include draft")
            if not self.errors:
                raise ValueError("rejected result must include errors")

        if self.status is CaseStructurerStatus.MANUAL_REVIEW:
            if self.draft is None and not self.errors and not self.warnings:
                raise ValueError(
                    "manual_review result requires draft, errors, or warnings"
                )

        return self


def build_case_structurer_prompt(input: CaseStructurerInput) -> str:
    """Build one Case Structurer prompt from stage metadata and source docs only."""

    prompt_contract = _load_case_structurer_prompt_contract()
    payload = {
        "stage_metadata": _serialize_stage_metadata(input),
        "source_documents": [
            _serialize_source_document(source_document)
            for source_document in input.source_documents
        ],
    }
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)

    return f"{prompt_contract.rstrip()}\n\n### Input JSON\n{payload_json}\n"


def parse_case_structurer_payload(
    payload: Mapping[str, object],
    input: CaseStructurerInput,
) -> CaseStructurerResult:
    """Parse adapter payload into CaseStructuringDraft without persistence."""

    try:
        input_errors = _validate_input_boundary(input)
        if input_errors:
            return _build_rejected_result(errors=input_errors)

        forbidden_field_errors = _detect_forbidden_payload_fields(payload)
        if forbidden_field_errors:
            return _build_rejected_result(errors=forbidden_field_errors)

        draft = CaseStructuringDraft.model_validate(payload)

        alignment_errors = _validate_draft_alignment(draft=draft, input=input)
        if alignment_errors:
            return _build_rejected_result(errors=alignment_errors)

        return CaseStructurerResult(
            status=CaseStructurerStatus.ACCEPTED,
            draft=draft,
            errors=(),
            warnings=(),
        )
    except ValidationError as exc:
        return _build_rejected_result(errors=_extract_validation_errors(exc))
    except Exception as exc:
        return CaseStructurerResult(
            status=CaseStructurerStatus.MANUAL_REVIEW,
            draft=None,
            errors=(f"unexpected parser failure: {exc}",),
            warnings=(),
        )


def _load_case_structurer_prompt_contract() -> str:
    try:
        prompt_contract = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8").strip()
    except OSError:
        return DEFAULT_PROMPT_CONTRACT.strip()

    if not prompt_contract:
        return DEFAULT_PROMPT_CONTRACT.strip()

    return prompt_contract


def _serialize_stage_metadata(input: CaseStructurerInput) -> dict[str, object]:
    stage_metadata: dict[str, object] = {
        "case_id": input.case_id,
        "stage_id": input.stage_id,
        "stage_index": input.stage_index,
        "stage_type": input.stage_type.value,
        "trigger_type": input.trigger_type.value,
        "created_at": input.created_at.isoformat(),
    }

    if input.clinical_time is not None:
        stage_metadata["clinical_time"] = input.clinical_time.isoformat()

    if input.parent_stage_id is not None:
        stage_metadata["parent_stage_id"] = input.parent_stage_id

    if input.stage_label is not None:
        stage_metadata["stage_label"] = input.stage_label

    if input.previous_stage_summary is not None:
        stage_metadata["previous_stage_summary_non_authoritative"] = (
            input.previous_stage_summary
        )

    return stage_metadata


def _serialize_source_document(source_document: SourceDocument) -> dict[str, object]:
    return {
        "source_doc_id": source_document.source_doc_id,
        "document_type": source_document.document_type.value,
        "input_event_id": source_document.input_event_id,
        "created_at": source_document.created_at.isoformat(),
        "raw_text": source_document.raw_text,
    }


def _validate_input_boundary(input: CaseStructurerInput) -> tuple[str, ...]:
    if input.source_documents:
        return ()

    return ("source_documents must not be empty",)


def _detect_forbidden_payload_fields(payload: Mapping[str, object]) -> tuple[str, ...]:
    payload_keys = {key for key in payload.keys() if isinstance(key, str)}
    forbidden_fields = sorted(payload_keys.intersection(FORBIDDEN_PAYLOAD_FIELDS))

    if not forbidden_fields:
        return ()

    return tuple(
        f"payload contains forbidden field: {field_name}" for field_name in forbidden_fields
    )


def _validate_draft_alignment(
    *,
    draft: CaseStructuringDraft,
    input: CaseStructurerInput,
) -> tuple[str, ...]:
    errors: list[str] = []

    if draft.case_id != input.case_id:
        errors.append("draft.case_id must equal input.case_id")

    allowed_source_doc_ids = {
        source_document.source_doc_id for source_document in input.source_documents
    }
    unknown_source_doc_ids = sorted(set(draft.source_doc_ids) - allowed_source_doc_ids)
    if unknown_source_doc_ids:
        errors.append(
            "draft.source_doc_ids must be a subset of input source document ids"
        )

    if draft.proposed_stage_context.stage_id != input.stage_id:
        errors.append(
            "draft.proposed_stage_context.stage_id must equal input.stage_id"
        )

    return tuple(errors)


def _extract_validation_errors(exc: ValidationError) -> tuple[str, ...]:
    error_messages: list[str] = []
    for error_item in exc.errors(include_url=False):
        location = ".".join(str(part) for part in error_item.get("loc", ()))
        message = str(error_item.get("msg", "validation error"))
        if location:
            error_messages.append(f"{location}: {message}")
        else:
            error_messages.append(message)

    if error_messages:
        return tuple(error_messages)

    return ("payload validation failed",)


def _build_rejected_result(*, errors: tuple[str, ...]) -> CaseStructurerResult:
    return CaseStructurerResult(
        status=CaseStructurerStatus.REJECTED,
        draft=None,
        errors=errors,
        warnings=(),
    )


__all__ = [
    "CaseStructurerInput",
    "CaseStructurerResult",
    "CaseStructurerStatus",
    "build_case_structurer_prompt",
    "parse_case_structurer_payload",
]
