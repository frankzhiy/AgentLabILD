"""Phase 1-1 证据原子 Schema（EvidenceAtom）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的最小权威证据单元。
2. 约束证据原子的来源锚点、语义属性与可选结构化值。
3. 为后续 ClaimReference / HypothesisState 提供可追溯 evidence_id 基础。

边界说明：
1. 本文件只描述“证据事实原子”，不承载诊断、仲裁或行动规划逻辑。
2. 证据对象必须显式关联 stage_id 与 source_doc_id，保证可追溯性。
3. non_authoritative_note 仅供说明，不可作为权威推理依据。

校验说明：
1. 权威字段必须为非空值。
2. 关键标识字段使用命名模式校验，降低 id 混用风险。
3. source span 需要成对出现且满足起止顺序。
4. normalized_key 会被归一化为 snake_case 形式。
5. category 与 modality 需要满足基础语义一致性。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    EVIDENCE_ID_PATTERN,
    SOURCE_DOC_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    validate_id_pattern,
)
from .stage import InfoModality


class EvidenceCategory(StrEnum):
    """Clinical-semantic evidence categories (source is handled by modality)."""

    DEMOGRAPHIC = "demographic"
    EXPOSURE = "exposure"
    SYMPTOM = "symptom"
    SIGN = "sign"
    LAB_FINDING = "lab_finding"
    PULMONARY_FUNCTION_FINDING = "pulmonary_function_finding"
    IMAGING_FINDING = "imaging_finding"
    PATHOLOGY_FINDING = "pathology_finding"
    TREATMENT_HISTORY = "treatment_history"
    DISEASE_COURSE = "disease_course"
    FAMILY_HISTORY = "family_history"
    OTHER = "other"


class EvidencePolarity(StrEnum):
    """Whether the evidence statement affirms or negates a fact."""

    PRESENT = "present"
    ABSENT = "absent"
    INDETERMINATE = "indeterminate"


class EvidenceCertainty(StrEnum):
    """Assertion source/strength for the evidence statement itself."""

    ASSERTED = "asserted"
    REPORTED = "reported"
    SUSPECTED = "suspected"
    CONFIRMED = "confirmed"


class EvidenceTemporality(StrEnum):
    """Temporal anchor of the evidence statement."""

    HISTORICAL = "historical"
    CURRENT = "current"
    NEWLY_OBSERVED = "newly_observed"
    PERSISTENT = "persistent"
    WORSENING = "worsening"
    IMPROVING = "improving"
    UNSPECIFIED = "unspecified"


class EvidenceSubject(StrEnum):
    """Subject to which the evidence statement applies."""

    PATIENT = "patient"
    FAMILY_MEMBER = "family_member"
    ENVIRONMENT = "environment"
    EXTERNAL_REPORT = "external_report"
    OTHER = "other"


ALLOWED_MODALITIES_BY_CATEGORY: dict[EvidenceCategory, set[InfoModality]] = {
    EvidenceCategory.DEMOGRAPHIC: {
        InfoModality.DEMOGRAPHICS,
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
    },
    EvidenceCategory.EXPOSURE: {
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
    },
    EvidenceCategory.SYMPTOM: {
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
    },
    EvidenceCategory.SIGN: {
        InfoModality.PHYSICAL_EXAM,
        InfoModality.FOLLOW_UP_NOTE,
    },
    EvidenceCategory.LAB_FINDING: {
        InfoModality.LABORATORY,
        InfoModality.SEROLOGY,
    },
    EvidenceCategory.PULMONARY_FUNCTION_FINDING: {
        InfoModality.PFT,
    },
    EvidenceCategory.IMAGING_FINDING: {
        InfoModality.HRCT_TEXT,
    },
    EvidenceCategory.PATHOLOGY_FINDING: {
        InfoModality.PATHOLOGY_TEXT,
        InfoModality.BALF_TEXT,
    },
    EvidenceCategory.TREATMENT_HISTORY: {
        InfoModality.TREATMENT_HISTORY,
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
    },
    EvidenceCategory.DISEASE_COURSE: {
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
        InfoModality.TREATMENT_HISTORY,
    },
    EvidenceCategory.FAMILY_HISTORY: {
        InfoModality.HISTORY,
        InfoModality.FOLLOW_UP_NOTE,
    },
    # OTHER is intentionally permissive for bootstrap and migration scenarios.
    EvidenceCategory.OTHER: set(),
}

class EvidenceAtom(BaseModel):
    """Authoritative minimal evidence unit for Phase 1-1."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["evidence_atom"] = "evidence_atom"
    evidence_id: NonEmptyStr
    stage_id: NonEmptyStr
    source_doc_id: NonEmptyStr
    atom_index: int = Field(ge=0)

    category: EvidenceCategory
    modality: InfoModality
    statement: NonEmptyStr
    raw_excerpt: NonEmptyStr
    polarity: EvidencePolarity
    certainty: EvidenceCertainty
    temporality: EvidenceTemporality
    subject: EvidenceSubject

    normalized_key: str | None = None
    value_text: str | None = None
    unit: str | None = None
    body_site: str | None = None
    source_span_start: int | None = Field(default=None, ge=0)
    source_span_end: int | None = Field(default=None, ge=0)
    extraction_method: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("evidence_id")
    @classmethod
    def validate_evidence_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=EVIDENCE_ID_PATTERN,
            field_name="evidence_id",
            example="ev_001 or evd-001",
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

    @field_validator(
        "value_text",
        "unit",
        "body_site",
        "extraction_method",
        "non_authoritative_note",
        mode="before",
    )
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("normalized_key", mode="before")
    @classmethod
    def normalize_normalized_key(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip().lower()
        if not cleaned:
            return None

        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or None

    @model_validator(mode="after")
    def validate_source_span_boundary(self) -> "EvidenceAtom":
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

    @model_validator(mode="after")
    def validate_category_modality_consistency(self) -> "EvidenceAtom":
        allowed_modalities = ALLOWED_MODALITIES_BY_CATEGORY[self.category]
        if allowed_modalities and self.modality not in allowed_modalities:
            allowed_text = ", ".join(sorted(item.value for item in allowed_modalities))
            raise ValueError(
                "category/modality mismatch: "
                f"category={self.category.value} does not allow modality={self.modality.value}; "
                f"allowed={allowed_text}"
            )

        return self


__all__ = [
    "EvidenceAtom",
    "EvidenceCategory",
    "EvidenceCertainty",
    "EvidencePolarity",
    "EvidenceSubject",
    "EvidenceTemporality",
]
