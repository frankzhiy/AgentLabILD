"""Phase 1-4 adapter contract schemas for Case Structurer."""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..schemas.common import (
    CASE_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
    validate_id_pattern,
)
from ..schemas.stage import InfoModality, StageContext

CASE_STRUCTURING_DRAFT_ID_PATTERN = re.compile(
    r"^case_struct_draft[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)
TIMELINE_ITEM_ID_PATTERN = re.compile(
    r"^timeline_item[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)
FINDING_ID_PATTERN = re.compile(r"^finding[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
CLUE_GROUP_ID_PATTERN = re.compile(
    r"^clue_group[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)


def _normalize_to_snake_case(value: object) -> str:
    cleaned = str(value).strip().lower()
    if not cleaned:
        raise ValueError("finding_key must not be empty")

    cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
    cleaned = re.sub(r"_+", "_", cleaned).strip("_")
    if not cleaned:
        raise ValueError("finding_key must contain at least one alphanumeric character")

    return cleaned


class CaseTimelineEventType(StrEnum):
    """Controlled event taxonomy for timeline draft entries."""

    SYMPTOM_ONSET = "symptom_onset"
    SYMPTOM_CHANGE = "symptom_change"
    TEST_RESULT = "test_result"
    TREATMENT = "treatment"
    DIAGNOSIS_HISTORY = "diagnosis_history"
    HOSPITALIZATION = "hospitalization"
    FOLLOW_UP = "follow_up"
    OTHER = "other"


class CandidateClueGroupKey(StrEnum):
    """Allowed non-diagnosis clue grouping keys."""

    RESPIRATORY_SYMPTOM_CLUES = "respiratory_symptom_clues"
    AUTOIMMUNE_CLUES = "autoimmune_clues"
    EXPOSURE_CLUES = "exposure_clues"
    INFECTION_CLUES = "infection_clues"
    DISEASE_COURSE_CLUES = "disease_course_clues"
    TREATMENT_HISTORY_CLUES = "treatment_history_clues"
    COMORBIDITY_CLUES = "comorbidity_clues"
    MISSING_INFORMATION_CLUES = "missing_information_clues"
    OTHER_CLUES = "other_clues"


class CaseTimelineItem(BaseModel):
    """One structured timeline item extracted by Case Structurer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["case_timeline_item"] = "case_timeline_item"
    timeline_item_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_doc_id: NonEmptyStr
    event_type: CaseTimelineEventType
    event_time_text: str | None = None
    description: NonEmptyStr
    source_span_start: int | None = Field(default=None, ge=0)
    source_span_end: int | None = Field(default=None, ge=0)
    non_authoritative_note: str | None = None

    @field_validator("timeline_item_id")
    @classmethod
    def validate_timeline_item_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=TIMELINE_ITEM_ID_PATTERN,
            field_name="timeline_item_id",
            example="timeline_item_001 or timeline_item-001",
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

    @field_validator("source_doc_id")
    @classmethod
    def validate_source_doc_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=SOURCE_DOC_ID_PATTERN,
            field_name="source_doc_id",
            example="doc_001 or doc-001",
        )

    @field_validator("event_time_text", mode="before")
    @classmethod
    def normalize_event_time_text(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_source_span_boundary(self) -> "CaseTimelineItem":
        if (self.source_span_start is None) ^ (self.source_span_end is None):
            raise ValueError(
                "source_span_start and source_span_end must be provided together"
            )

        if (
            self.source_span_start is not None
            and self.source_span_end is not None
            and self.source_span_start > self.source_span_end
        ):
            raise ValueError("source_span_start must be <= source_span_end")

        return self


class NormalizedFinding(BaseModel):
    """One normalized finding entry produced by Case Structurer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["normalized_finding"] = "normalized_finding"
    finding_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_doc_id: NonEmptyStr
    finding_key: NonEmptyStr
    finding_text: NonEmptyStr
    modality: InfoModality
    source_span_start: int | None = Field(default=None, ge=0)
    source_span_end: int | None = Field(default=None, ge=0)
    non_authoritative_note: str | None = None

    @field_validator("finding_id")
    @classmethod
    def validate_finding_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=FINDING_ID_PATTERN,
            field_name="finding_id",
            example="finding_001 or finding-001",
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

    @field_validator("source_doc_id")
    @classmethod
    def validate_source_doc_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=SOURCE_DOC_ID_PATTERN,
            field_name="source_doc_id",
            example="doc_001 or doc-001",
        )

    @field_validator("finding_key", mode="before")
    @classmethod
    def normalize_finding_key(cls, value: object) -> str:
        return _normalize_to_snake_case(value)

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_source_span_boundary(self) -> "NormalizedFinding":
        if (self.source_span_start is None) ^ (self.source_span_end is None):
            raise ValueError(
                "source_span_start and source_span_end must be provided together"
            )

        if (
            self.source_span_start is not None
            and self.source_span_end is not None
            and self.source_span_start > self.source_span_end
        ):
            raise ValueError("source_span_start must be <= source_span_end")

        return self


class CandidateClueGroup(BaseModel):
    """One non-diagnosis clue grouping generated by Case Structurer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["candidate_clue_group"] = "candidate_clue_group"
    clue_group_id: NonEmptyStr
    stage_id: NonEmptyStr
    group_key: CandidateClueGroupKey
    finding_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    summary: NonEmptyStr
    non_authoritative_note: str | None = None

    @field_validator("clue_group_id")
    @classmethod
    def validate_clue_group_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CLUE_GROUP_ID_PATTERN,
            field_name="clue_group_id",
            example="clue_group_001 or clue_group-001",
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

    @field_validator("finding_ids")
    @classmethod
    def validate_finding_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        duplicate_ids = find_duplicate_items(value)
        if duplicate_ids:
            raise ValueError("finding_ids must not contain duplicates")

        for finding_id in value:
            validate_id_pattern(
                finding_id,
                pattern=FINDING_ID_PATTERN,
                field_name="finding_ids[]",
                example="finding_001 or finding-001",
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)


class CaseStructuringDraft(BaseModel):
    """Non-authoritative adapter draft produced by Case Structurer."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["case_structuring_draft"] = "case_structuring_draft"
    draft_id: NonEmptyStr
    case_id: NonEmptyStr
    source_doc_ids: tuple[NonEmptyStr, ...]
    proposed_stage_context: StageContext
    timeline_items: tuple[CaseTimelineItem, ...] = Field(default_factory=tuple)
    normalized_findings: tuple[NormalizedFinding, ...] = Field(default_factory=tuple)
    candidate_clue_groups: tuple[CandidateClueGroup, ...] = Field(default_factory=tuple)
    non_authoritative_note: str | None = None

    @field_validator("draft_id")
    @classmethod
    def validate_draft_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CASE_STRUCTURING_DRAFT_ID_PATTERN,
            field_name="draft_id",
            example="case_struct_draft_001 or case_struct_draft-001",
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

    @field_validator("source_doc_ids")
    @classmethod
    def validate_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("source_doc_ids must not be empty")

        duplicate_ids = find_duplicate_items(value)
        if duplicate_ids:
            raise ValueError("source_doc_ids must not contain duplicates")

        for source_doc_id in value:
            validate_id_pattern(
                source_doc_id,
                pattern=SOURCE_DOC_ID_PATTERN,
                field_name="source_doc_ids[]",
                example="doc_001 or doc-001",
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_cross_object_alignment(self) -> "CaseStructuringDraft":
        stage_context = self.proposed_stage_context

        if stage_context.case_id != self.case_id:
            raise ValueError("proposed_stage_context.case_id must equal draft case_id")

        duplicate_timeline_item_ids = find_duplicate_items(
            timeline_item.timeline_item_id for timeline_item in self.timeline_items
        )
        if duplicate_timeline_item_ids:
            raise ValueError(
                "timeline_items must not contain duplicate timeline_item_id values"
            )

        duplicate_finding_ids = find_duplicate_items(
            finding.finding_id for finding in self.normalized_findings
        )
        if duplicate_finding_ids:
            raise ValueError(
                "normalized_findings must not contain duplicate finding_id values"
            )

        duplicate_clue_group_ids = find_duplicate_items(
            clue_group.clue_group_id for clue_group in self.candidate_clue_groups
        )
        if duplicate_clue_group_ids:
            raise ValueError(
                "candidate_clue_groups must not contain duplicate clue_group_id values"
            )

        draft_source_doc_ids = set(self.source_doc_ids)
        stage_source_doc_ids = set(stage_context.source_doc_ids)
        if not stage_source_doc_ids.issubset(draft_source_doc_ids):
            raise ValueError(
                "proposed_stage_context.source_doc_ids must be a subset of draft source_doc_ids"
            )

        expected_stage_id = stage_context.stage_id
        for item in self.timeline_items:
            if item.stage_id != expected_stage_id:
                raise ValueError(
                    "all timeline_items must align to proposed_stage_context.stage_id"
                )
            if item.source_doc_id not in draft_source_doc_ids:
                raise ValueError(
                    "timeline_items source_doc_id must be included in draft source_doc_ids"
                )

        for finding in self.normalized_findings:
            if finding.stage_id != expected_stage_id:
                raise ValueError(
                    "all normalized_findings must align to proposed_stage_context.stage_id"
                )
            if finding.source_doc_id not in draft_source_doc_ids:
                raise ValueError(
                    "normalized_findings source_doc_id must be included in draft source_doc_ids"
                )

        finding_ids = {finding.finding_id for finding in self.normalized_findings}
        for clue_group in self.candidate_clue_groups:
            if clue_group.stage_id != expected_stage_id:
                raise ValueError(
                    "all candidate_clue_groups must align to proposed_stage_context.stage_id"
                )

            missing_finding_ids = sorted(set(clue_group.finding_ids) - finding_ids)
            if missing_finding_ids:
                raise ValueError(
                    "candidate_clue_groups finding_ids must reference normalized_findings"
                )

        return self


__all__ = [
    "CASE_STRUCTURING_DRAFT_ID_PATTERN",
    "CLUE_GROUP_ID_PATTERN",
    "FINDING_ID_PATTERN",
    "TIMELINE_ITEM_ID_PATTERN",
    "CandidateClueGroup",
    "CandidateClueGroupKey",
    "CaseStructuringDraft",
    "CaseTimelineEventType",
    "CaseTimelineItem",
    "NormalizedFinding",
]
