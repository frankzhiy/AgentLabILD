"""Phase 1-4 Evidence Atomizer adapter.

This module only prepares Evidence Atomizer prompts and parses adapter payloads
into EvidenceAtomizationDraft. It does not persist state and does not call write gate.
"""

from __future__ import annotations

import json
from collections.abc import Mapping
from datetime import datetime
from enum import StrEnum
from pathlib import Path

from pydantic import BaseModel, ConfigDict, Field, ValidationError, field_validator, model_validator

from ..prompts import render_template_file
from ..provenance.model import EXTRACTION_ACTIVITY_ID_PATTERN
from ..schemas.common import (
    CASE_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    validate_id_pattern,
)
from ..schemas.intake import SourceDocument
from ..schemas.stage import StageContext
from .case_structuring import CaseStructuringDraft
from .evidence_atomization import EvidenceAtomizationDraft

DEFAULT_PROMPT_PATH = (
    Path(__file__).resolve().parents[2]
    / "configs"
    / "prompts"
    / "v2"
    / "evidence_atomizer.md"
)

DEFAULT_PROMPT_CONTRACT = """You are an Evidence Atomizer adapter, not a diagnostician.
Return only one EvidenceAtomizationDraft-compatible JSON object.
Extract only evidence atoms from the provided stage metadata and source documents.
"""

FORBIDDEN_PAYLOAD_FIELDS = frozenset(
    {
        "final_diagnosis",
        "differential_diagnosis",
        "hypotheses",
        "hypothesis_state",
        "hypothesis_board",
        "claim_references",
        "action_candidates",
        "action_plan",
        "arbitration_output",
        "treatment_recommendation",
        "confidence",
        "safety_decision",
        "typed_conflicts",
        "conflict",
        "belief_revision",
        "update_trace",
    }
)


class EvidenceAtomizerStatus(StrEnum):
    """Decision status for one Evidence Atomizer adapter parse attempt."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


class EvidenceAtomizerInput(BaseModel):
    """Input contract for Evidence Atomizer adapter invocation."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_documents: tuple[SourceDocument, ...]
    stage_context: StageContext
    case_structuring_draft: CaseStructuringDraft | None = None
    extraction_activity_id: NonEmptyStr
    extractor_name: NonEmptyStr = "evidence_atomizer_adapter"
    extractor_version: NonEmptyStr = "0.1.0"
    occurred_at: datetime

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

    @field_validator("extraction_activity_id")
    @classmethod
    def validate_extraction_activity_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EXTRACTION_ACTIVITY_ID_PATTERN,
            field_name="extraction_activity_id",
            example="activity_001 or activity-001",
        )

    @field_validator("source_documents")
    @classmethod
    def validate_source_documents(cls, value: tuple[SourceDocument, ...]) -> tuple[SourceDocument, ...]:
        if not value:
            raise ValueError("source_documents must not be empty")

        duplicate_source_doc_ids = find_duplicate_items(
            source_document.source_doc_id for source_document in value
        )
        if duplicate_source_doc_ids:
            raise ValueError("source_documents must not contain duplicate source_doc_id")

        return value

    @model_validator(mode="after")
    def validate_cross_object_alignment(self) -> "EvidenceAtomizerInput":
        input_source_doc_ids = {
            source_document.source_doc_id for source_document in self.source_documents
        }

        for source_document in self.source_documents:
            if source_document.case_id != self.case_id:
                raise ValueError("every source document case_id must equal input case_id")

        stage_context = self.stage_context
        if stage_context.case_id != self.case_id:
            raise ValueError("stage_context.case_id must equal input case_id")

        if stage_context.stage_id != self.stage_id:
            raise ValueError("stage_context.stage_id must equal input stage_id")

        stage_unknown_source_doc_ids = sorted(
            set(stage_context.source_doc_ids) - input_source_doc_ids
        )
        if stage_unknown_source_doc_ids:
            raise ValueError(
                "stage_context.source_doc_ids must be a subset of input source document ids"
            )

        if self.case_structuring_draft is not None:
            draft = self.case_structuring_draft

            if draft.case_id != self.case_id:
                raise ValueError("case_structuring_draft.case_id must equal input case_id")

            if draft.proposed_stage_context.stage_id != self.stage_id:
                raise ValueError(
                    "case_structuring_draft.proposed_stage_context.stage_id must equal input stage_id"
                )

            unknown_draft_source_doc_ids = sorted(
                set(draft.source_doc_ids) - input_source_doc_ids
            )
            if unknown_draft_source_doc_ids:
                raise ValueError(
                    "case_structuring_draft.source_doc_ids must be a subset of input source document ids"
                )

        return self


class EvidenceAtomizerResult(BaseModel):
    """Non-authoritative parse result for Evidence Atomizer adapter output."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: EvidenceAtomizerStatus
    draft: EvidenceAtomizationDraft | None = None
    errors: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    warnings: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "EvidenceAtomizerResult":
        if self.status is EvidenceAtomizerStatus.ACCEPTED:
            if self.draft is None:
                raise ValueError("accepted result requires draft")
            if self.errors:
                raise ValueError("accepted result must not include errors")

        if self.status is EvidenceAtomizerStatus.REJECTED:
            if self.draft is not None:
                raise ValueError("rejected result must not include draft")
            if not self.errors:
                raise ValueError("rejected result must include errors")

        if self.status is EvidenceAtomizerStatus.MANUAL_REVIEW:
            if self.draft is None and not self.errors and not self.warnings:
                raise ValueError(
                    "manual_review result requires draft, errors, or warnings"
                )

        return self


def build_evidence_atomizer_prompt(input: EvidenceAtomizerInput) -> str:
    """Build one Evidence Atomizer prompt from stage metadata and source docs."""

    payload: dict[str, object] = {
        "stage_metadata": _serialize_stage_metadata(input.stage_context),
        "source_documents": [
            _serialize_source_document(source_document)
            for source_document in input.source_documents
        ],
    }
    if input.case_structuring_draft is not None:
        payload["case_structuring_draft_guidance"] = _serialize_case_structuring_draft_guidance(
            input.case_structuring_draft
        )

    if _should_use_evidence_atomizer_fallback_prompt():
        return _build_evidence_atomizer_fallback_prompt(payload)

    return render_template_file(
        DEFAULT_PROMPT_PATH,
        {
            "input_json": payload,
            "output_schema_json": EvidenceAtomizationDraft.model_json_schema(),
        },
    )


def parse_evidence_atomizer_payload(
    payload: Mapping[str, object],
    input: EvidenceAtomizerInput,
) -> EvidenceAtomizerResult:
    """Parse adapter payload into EvidenceAtomizationDraft without persistence."""

    try:
        input_errors = _validate_input_boundary(input)
        if input_errors:
            return _build_rejected_result(errors=input_errors)

        forbidden_field_errors = _detect_forbidden_payload_fields(payload)
        if forbidden_field_errors:
            return _build_rejected_result(errors=forbidden_field_errors)

        draft = EvidenceAtomizationDraft.model_validate(payload)

        alignment_errors = _validate_draft_alignment(draft=draft, input=input)
        if alignment_errors:
            return _build_rejected_result(errors=alignment_errors)

        return EvidenceAtomizerResult(
            status=EvidenceAtomizerStatus.ACCEPTED,
            draft=draft,
            errors=(),
            warnings=(),
        )
    except ValidationError as exc:
        return _build_rejected_result(errors=_extract_validation_errors(exc))
    except Exception as exc:
        return EvidenceAtomizerResult(
            status=EvidenceAtomizerStatus.MANUAL_REVIEW,
            draft=None,
            errors=(f"unexpected parser failure: {exc}",),
            warnings=(),
        )


def _should_use_evidence_atomizer_fallback_prompt() -> bool:
    try:
        prompt_contract = DEFAULT_PROMPT_PATH.read_text(encoding="utf-8")
    except OSError:
        return True

    return not prompt_contract.strip()


def _build_evidence_atomizer_fallback_prompt(payload: dict[str, object]) -> str:
    payload_json = json.dumps(payload, ensure_ascii=False, indent=2, sort_keys=True)
    return f"{DEFAULT_PROMPT_CONTRACT.rstrip()}\n\n### Input JSON\n{payload_json}\n"


def _serialize_stage_metadata(stage_context: StageContext) -> dict[str, object]:
    stage_metadata: dict[str, object] = {
        "case_id": stage_context.case_id,
        "stage_id": stage_context.stage_id,
        "stage_index": stage_context.stage_index,
        "stage_type": stage_context.stage_type.value,
        "trigger_type": stage_context.trigger_type.value,
        "created_at": stage_context.created_at.isoformat(),
        "available_modalities": [
            modality.value for modality in stage_context.available_modalities
        ],
        "source_doc_ids": list(stage_context.source_doc_ids),
        "stage_focus": [focus.value for focus in stage_context.stage_focus],
        "clinical_question_tags": list(stage_context.clinical_question_tags),
    }

    if stage_context.clinical_time is not None:
        stage_metadata["clinical_time"] = stage_context.clinical_time.isoformat()

    if stage_context.parent_stage_id is not None:
        stage_metadata["parent_stage_id"] = stage_context.parent_stage_id

    if stage_context.stage_label is not None:
        stage_metadata["stage_label"] = stage_context.stage_label

    if stage_context.visibility_policy_hint is not None:
        stage_metadata["visibility_policy_hint"] = (
            stage_context.visibility_policy_hint.value
        )

    if stage_context.non_authoritative_note is not None:
        stage_metadata["non_authoritative_note"] = stage_context.non_authoritative_note

    return stage_metadata


def _serialize_source_document(source_document: SourceDocument) -> dict[str, object]:
    return {
        "source_doc_id": source_document.source_doc_id,
        "document_type": source_document.document_type.value,
        "input_event_id": source_document.input_event_id,
        "created_at": source_document.created_at.isoformat(),
        "raw_text": source_document.raw_text,
    }


def _serialize_case_structuring_draft_guidance(
    case_structuring_draft: CaseStructuringDraft,
) -> dict[str, object]:
    return {
        "timeline_items": [
            {
                "timeline_item_id": item.timeline_item_id,
                "source_doc_id": item.source_doc_id,
                "event_type": item.event_type.value,
                "event_time_text": item.event_time_text,
                "description": item.description,
                "source_span_start": item.source_span_start,
                "source_span_end": item.source_span_end,
            }
            for item in case_structuring_draft.timeline_items
        ],
        "normalized_findings": [
            {
                "finding_id": finding.finding_id,
                "source_doc_id": finding.source_doc_id,
                "finding_key": finding.finding_key,
                "finding_text": finding.finding_text,
                "modality": finding.modality.value,
                "source_span_start": finding.source_span_start,
                "source_span_end": finding.source_span_end,
            }
            for finding in case_structuring_draft.normalized_findings
        ],
        "candidate_clue_groups": [
            {
                "clue_group_id": clue_group.clue_group_id,
                "group_key": clue_group.group_key.value,
                "finding_ids": list(clue_group.finding_ids),
                "summary": clue_group.summary,
            }
            for clue_group in case_structuring_draft.candidate_clue_groups
        ],
    }


def _validate_input_boundary(input: EvidenceAtomizerInput) -> tuple[str, ...]:
    errors: list[str] = []

    if not input.source_documents:
        errors.append("source_documents must not be empty")

    duplicate_source_doc_ids = find_duplicate_items(
        source_document.source_doc_id for source_document in input.source_documents
    )
    if duplicate_source_doc_ids:
        errors.append("source_documents must not contain duplicate source_doc_id")

    for source_document in input.source_documents:
        if source_document.case_id != input.case_id:
            errors.append("every source document case_id must equal input case_id")
            break

    input_source_doc_ids = {
        source_document.source_doc_id for source_document in input.source_documents
    }

    stage_context = input.stage_context
    if stage_context.case_id != input.case_id:
        errors.append("stage_context.case_id must equal input case_id")

    if stage_context.stage_id != input.stage_id:
        errors.append("stage_context.stage_id must equal input stage_id")

    unknown_stage_source_doc_ids = sorted(
        set(stage_context.source_doc_ids) - input_source_doc_ids
    )
    if unknown_stage_source_doc_ids:
        errors.append(
            "stage_context.source_doc_ids must be a subset of input source document ids"
        )

    if input.case_structuring_draft is not None:
        draft = input.case_structuring_draft

        if draft.case_id != input.case_id:
            errors.append("case_structuring_draft.case_id must equal input case_id")

        if draft.proposed_stage_context.stage_id != input.stage_id:
            errors.append(
                "case_structuring_draft.proposed_stage_context.stage_id must equal input stage_id"
            )

        unknown_draft_source_doc_ids = sorted(set(draft.source_doc_ids) - input_source_doc_ids)
        if unknown_draft_source_doc_ids:
            errors.append(
                "case_structuring_draft.source_doc_ids must be a subset of input source document ids"
            )

    return tuple(errors)


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
    draft: EvidenceAtomizationDraft,
    input: EvidenceAtomizerInput,
) -> tuple[str, ...]:
    errors: list[str] = []

    if draft.case_id != input.case_id:
        errors.append("draft.case_id must equal input.case_id")

    if draft.stage_id != input.stage_id:
        errors.append("draft.stage_id must equal input.stage_id")

    input_source_doc_ids = {
        source_document.source_doc_id for source_document in input.source_documents
    }
    unknown_draft_source_doc_ids = sorted(set(draft.source_doc_ids) - input_source_doc_ids)
    if unknown_draft_source_doc_ids:
        errors.append("draft.source_doc_ids must be a subset of input source document ids")

    extraction_activity = draft.extraction_activity
    if extraction_activity.stage_id != input.stage_id:
        errors.append("draft.extraction_activity.stage_id must equal input.stage_id")

    activity_source_doc_ids = set(extraction_activity.input_source_doc_ids)
    if not input_source_doc_ids.issubset(activity_source_doc_ids):
        errors.append(
            "draft.extraction_activity.input_source_doc_ids must cover input source document ids"
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


def _build_rejected_result(*, errors: tuple[str, ...]) -> EvidenceAtomizerResult:
    return EvidenceAtomizerResult(
        status=EvidenceAtomizerStatus.REJECTED,
        draft=None,
        errors=errors,
        warnings=(),
    )


__all__ = [
    "EvidenceAtomizerInput",
    "EvidenceAtomizerResult",
    "EvidenceAtomizerStatus",
    "build_evidence_atomizer_prompt",
    "parse_evidence_atomizer_payload",
]
