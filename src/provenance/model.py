"""Phase 1-2 PROV-lite schema models for evidence/claim traceability.

本文件提供最小可用的 provenance 机制对象：
1. SourceAnchor：来源锚点（文档 + 可选 span）
2. ExtractionActivity：结构化抽取活动
3. EvidenceProvenance：证据级 provenance 绑定
4. ClaimProvenance：claim 级 provenance 绑定

边界：
1. 仅定义数据结构与一致性校验，不实现 writer gate。
2. 不承载自由文本 provenance blob，要求显式 id 与结构化字段。
3. 与现有 EvidenceAtom / ClaimReference 保持兼容（通过可选挂接字段集成）。
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..schemas.common import (
    CLAIM_REF_ID_PATTERN,
    EVIDENCE_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
    validate_id_pattern,
)
from ..schemas.stage import InfoModality

SOURCE_ANCHOR_ID_PATTERN = re.compile(r"^anchor[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
EXTRACTION_ACTIVITY_ID_PATTERN = re.compile(
    r"^activity[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)
EVIDENCE_PROVENANCE_ID_PATTERN = re.compile(
    r"^eprov[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)
CLAIM_PROVENANCE_ID_PATTERN = re.compile(
    r"^cprov[_-][A-Za-z0-9][A-Za-z0-9_-]*$"
)


class ExtractionMethod(StrEnum):
    """Controlled extraction-method taxonomy for provenance activities."""

    RULE_BASED = "rule_based"
    LLM_STRUCTURED = "llm_structured"
    MANUAL_CURATION = "manual_curation"
    HYBRID = "hybrid"


class SourceAnchor(BaseModel):
    """Structured source anchor (document anchor + optional span)."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["source_anchor"] = "source_anchor"
    anchor_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_doc_id: NonEmptyStr
    modality: InfoModality
    raw_excerpt: NonEmptyStr
    section_label: str | None = None
    span_start: int | None = Field(default=None, ge=0)
    span_end: int | None = Field(default=None, ge=0)

    @field_validator("anchor_id")
    @classmethod
    def validate_anchor_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=SOURCE_ANCHOR_ID_PATTERN,
            field_name="anchor_id",
            example="anchor_001 or anchor-001",
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

    @field_validator("section_label", mode="before")
    @classmethod
    def normalize_section_label(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_span_boundary(self) -> "SourceAnchor":
        if (self.span_start is None) ^ (self.span_end is None):
            raise ValueError("span_start and span_end must be provided together")

        if (
            self.span_start is not None
            and self.span_end is not None
            and self.span_start > self.span_end
        ):
            raise ValueError("span_start must be <= span_end")

        return self


class ExtractionActivity(BaseModel):
    """Structured extraction activity for provenance chains."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["extraction_activity"] = "extraction_activity"
    activity_id: NonEmptyStr
    stage_id: NonEmptyStr
    extraction_method: ExtractionMethod
    extractor_name: NonEmptyStr
    extractor_version: NonEmptyStr
    occurred_at: datetime
    input_source_doc_ids: tuple[NonEmptyStr, ...]
    model_name: str | None = None
    prompt_template_id: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("activity_id")
    @classmethod
    def validate_activity_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EXTRACTION_ACTIVITY_ID_PATTERN,
            field_name="activity_id",
            example="activity_001 or activity-001",
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

    @field_validator("input_source_doc_ids")
    @classmethod
    def validate_input_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("input_source_doc_ids must contain at least one doc id")

        duplicate_source_doc_ids = find_duplicate_items(value)
        if duplicate_source_doc_ids:
            raise ValueError("input_source_doc_ids must not contain duplicates")

        for source_doc_id in value:
            validate_id_pattern(
                source_doc_id,
                pattern=SOURCE_DOC_ID_PATTERN,
                field_name="input_source_doc_ids",
                example="doc_001 or doc-001",
            )

        return value

    @field_validator("model_name", "prompt_template_id", mode="before")
    @classmethod
    def normalize_optional_text_fields(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)


class EvidenceProvenance(BaseModel):
    """Provenance package bound to one EvidenceAtom identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["evidence_provenance"] = "evidence_provenance"
    evidence_provenance_id: NonEmptyStr
    stage_id: NonEmptyStr
    evidence_id: NonEmptyStr
    source_anchors: tuple[SourceAnchor, ...]
    extraction_activity: ExtractionActivity
    non_authoritative_note: str | None = None

    @field_validator("evidence_provenance_id")
    @classmethod
    def validate_evidence_provenance_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EVIDENCE_PROVENANCE_ID_PATTERN,
            field_name="evidence_provenance_id",
            example="eprov_001 or eprov-001",
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

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EVIDENCE_ID_PATTERN,
            field_name="evidence_id",
            example="ev_001 or evd-001",
        )

    @field_validator("source_anchors")
    @classmethod
    def validate_source_anchors(
        cls, value: tuple[SourceAnchor, ...]
    ) -> tuple[SourceAnchor, ...]:
        if not value:
            raise ValueError("source_anchors must contain at least one source anchor")

        duplicate_anchor_ids = find_duplicate_items(anchor.anchor_id for anchor in value)
        if duplicate_anchor_ids:
            raise ValueError("source_anchors must not contain duplicate anchor_id values")

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_stage_and_source_alignment(self) -> "EvidenceProvenance":
        if self.extraction_activity.stage_id != self.stage_id:
            raise ValueError(
                "extraction_activity.stage_id must equal evidence provenance stage_id"
            )

        anchor_stage_mismatches = [
            anchor.anchor_id
            for anchor in self.source_anchors
            if anchor.stage_id != self.stage_id
        ]
        if anchor_stage_mismatches:
            raise ValueError(
                "all source_anchors must align with evidence provenance stage_id"
            )

        activity_source_doc_ids = set(self.extraction_activity.input_source_doc_ids)
        anchor_source_doc_ids = {anchor.source_doc_id for anchor in self.source_anchors}
        if not anchor_source_doc_ids.issubset(activity_source_doc_ids):
            raise ValueError(
                "source_anchors source_doc_id values must be included in extraction_activity.input_source_doc_ids"
            )

        return self


class ClaimProvenance(BaseModel):
    """Provenance package bound to one ClaimReference identity."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["claim_provenance"] = "claim_provenance"
    claim_provenance_id: NonEmptyStr
    stage_id: NonEmptyStr
    claim_ref_id: NonEmptyStr
    evidence_ids: tuple[NonEmptyStr, ...]
    evidence_provenance_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    derivation_activity: ExtractionActivity
    non_authoritative_note: str | None = None

    @field_validator("claim_provenance_id")
    @classmethod
    def validate_claim_provenance_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CLAIM_PROVENANCE_ID_PATTERN,
            field_name="claim_provenance_id",
            example="cprov_001 or cprov-001",
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

    @field_validator("claim_ref_id")
    @classmethod
    def validate_claim_ref_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CLAIM_REF_ID_PATTERN,
            field_name="claim_ref_id",
            example="claim_ref_001 or claim_ref-001",
        )

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence_ids must contain at least one evidence id")

        duplicate_evidence_ids = find_duplicate_items(value)
        if duplicate_evidence_ids:
            raise ValueError("evidence_ids must not contain duplicates")

        for evidence_id in value:
            validate_id_pattern(
                evidence_id,
                pattern=EVIDENCE_ID_PATTERN,
                field_name="evidence_ids",
                example="ev_001 or evd-001",
            )

        return value

    @field_validator("evidence_provenance_ids")
    @classmethod
    def validate_evidence_provenance_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        duplicate_provenance_ids = find_duplicate_items(value)
        if duplicate_provenance_ids:
            raise ValueError("evidence_provenance_ids must not contain duplicates")

        for evidence_provenance_id in value:
            validate_id_pattern(
                evidence_provenance_id,
                pattern=EVIDENCE_PROVENANCE_ID_PATTERN,
                field_name="evidence_provenance_ids",
                example="eprov_001 or eprov-001",
            )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @model_validator(mode="after")
    def validate_stage_alignment(self) -> "ClaimProvenance":
        if self.derivation_activity.stage_id != self.stage_id:
            raise ValueError("derivation_activity.stage_id must equal claim provenance stage_id")
        return self


__all__ = [
    "ClaimProvenance",
    "EvidenceProvenance",
    "ExtractionActivity",
    "ExtractionMethod",
    "SourceAnchor",
]
