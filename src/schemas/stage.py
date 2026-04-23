"""Phase 1-1 阶段边界 Schema（StageContext）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的“阶段上下文”对象，而不是诊断对象。
2. 约束阶段级元数据的类型边界，供后续 validator / writer gate 使用。
3. 为后续 EvidenceAtom、ClaimReference、HypothesisState 提供 stage_id 锚点。

边界说明：
1. 本文件只描述“阶段边界与可见性上下文”。
2. 不承载诊断结论、假设状态、证据原子内容、行动计划。
3. non_authoritative_note 仅用于说明，不可作为权威决策依据。

枚举说明：
1. StageType：阶段类型（当前处于哪类临床评审阶段）。
2. TriggerType：触发阶段创建的临床事件。
3. InfoModality：该阶段可用的临床信息模态（语义模态，不是文件格式）。
4. StageFocus：阶段级运营/流程焦点（可多选，不承载具体临床鉴别问题）。
5. VisibilityPolicyHint：仅表达可见性/共享提示，不表达升级或安全状态。

StageContext 字段含义：
1. stage_id：阶段唯一标识。
2. case_id：病例唯一标识。
3. stage_index：该病例中的阶段序号（从 0 开始）。
4. stage_type：阶段类型（StageType）。
5. trigger_type：阶段触发类型（TriggerType）。
6. created_at：系统创建该阶段对象的时间。
7. clinical_time：该阶段对应的临床时间点，可为空。
8. parent_stage_id：父阶段 id，可为空；用于关联历史阶段。
9. available_modalities：当前阶段可用的信息模态集合（InfoModality）。
10. source_doc_ids：当前阶段可追溯的来源文档 id 集合。
11. stage_label：阶段显示标签，可为空。
12. stage_focus：阶段焦点集合（StageFocus），用于表达本阶段工作重心。
13. clinical_question_tags：病例特异的临床问题标签集合（如 ae_vs_infection）。
14. visibility_policy_hint：可见性提示（VisibilityPolicyHint），可为空。
15. non_authoritative_note：非权威备注，可为空，仅供阅读说明。

基础校验说明：
1. 禁止额外未声明字段（extra="forbid"）。
2. parent_stage_id 会做空白归一化。
3. available_modalities 与 source_doc_ids 不允许重复。
4. stage_focus 与 clinical_question_tags 不允许重复。
5. initial_review 阶段不允许设置 parent_stage_id。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    CASE_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    validate_id_pattern,
)


class StageType(StrEnum):
    """Controlled stage taxonomy for ILD-MDT staged review."""

    INITIAL_REVIEW = "initial_review"
    SUPPLEMENTARY_TEST_REVIEW = "supplementary_test_review"
    FOLLOW_UP_REVIEW = "follow_up_review"
    ACUTE_CHANGE_REVIEW = "acute_change_review"
    POST_MDT_REVIEW = "post_mdt_review"



class TriggerType(StrEnum):
    """Reason why a stage was created."""

    INITIAL_PRESENTATION = "initial_presentation"
    NEW_HRCT = "new_hrct"
    NEW_PATHOLOGY = "new_pathology"
    NEW_SEROLOGY = "new_serology"
    NEW_PFT = "new_pft"
    NEW_EXPOSURE_HISTORY = "new_exposure_history"
    CLINICAL_WORSENING = "clinical_worsening"
    TREATMENT_RESPONSE = "treatment_response"
    MDT_RE_REVIEW = "mdt_re_review"
    OTHER = "other"


class InfoModality(StrEnum):
    """Clinical information modalities available in this stage."""

    DEMOGRAPHICS = "demographics"
    HISTORY = "history"
    PHYSICAL_EXAM = "physical_exam"
    LABORATORY = "laboratory"
    SEROLOGY = "serology"
    PFT = "pft"
    HRCT_TEXT = "hrct_text"
    PATHOLOGY_TEXT = "pathology_text"
    BALF_TEXT = "balf_text"
    TREATMENT_HISTORY = "treatment_history"
    FOLLOW_UP_NOTE = "follow_up_note"


class StageFocus(StrEnum):
    """Stage-level operational focus, not case-specific question labels."""

    BASELINE_STRUCTURING = "baseline_structuring"
    EVIDENCE_AUGMENTATION = "evidence_augmentation"
    LONGITUDINAL_REASSESSMENT = "longitudinal_reassessment"
    WORKING_DIAGNOSIS_REVISION = "working_diagnosis_revision"
    MANAGEMENT_REVIEW = "management_review"
    SAFETY_REVIEW = "safety_review"


class VisibilityPolicyHint(StrEnum):
    """Visibility/sharing hint only; not escalation or safety state."""

    STAGE_LOCAL_ONLY = "stage_local_only"
    MDT_SHARED = "mdt_shared"
    MDT_RESTRICTED = "mdt_restricted"


class StageContext(BaseModel):
    """Authoritative stage-boundary object for Phase 1-1.

    The object only captures stage identity, temporal context, operational
    focus, case-specific question tags, and visibility hints.
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["stage_context"] = "stage_context"
    stage_id: NonEmptyStr
    case_id: NonEmptyStr
    stage_index: int = Field(ge=0)
    stage_type: StageType
    trigger_type: TriggerType
    created_at: datetime
    clinical_time: datetime | None = None
    parent_stage_id: str | None = None
    available_modalities: tuple[InfoModality, ...] = Field(default_factory=tuple)
    source_doc_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    stage_label: NonEmptyStr | None = None
    stage_focus: tuple[StageFocus, ...] = Field(default_factory=tuple)
    # Case-specific question tags are separate from stage-level StageFocus.
    clinical_question_tags: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    visibility_policy_hint: VisibilityPolicyHint | None = None
    non_authoritative_note: str | None = None

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
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

    @field_validator("parent_stage_id")
    @classmethod
    def normalize_parent_stage_id(cls, value: str | None) -> str | None:
        if value is None:
            return None
        cleaned = value.strip()
        return cleaned or None

    @field_validator("available_modalities")
    @classmethod
    def ensure_unique_modalities(
        cls, value: tuple[InfoModality, ...]
    ) -> tuple[InfoModality, ...]:
        if len(set(value)) != len(value):
            raise ValueError("available_modalities must not contain duplicates")
        return value

    @field_validator("source_doc_ids")
    @classmethod
    def ensure_unique_source_doc_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("source_doc_ids must not contain duplicates")
        return value

    @field_validator("stage_focus")
    @classmethod
    def ensure_unique_stage_focus(
        cls, value: tuple[StageFocus, ...]
    ) -> tuple[StageFocus, ...]:
        if len(set(value)) != len(value):
            raise ValueError("stage_focus must not contain duplicates")
        return value

    @field_validator("clinical_question_tags")
    @classmethod
    def ensure_unique_clinical_question_tags(
        cls, value: tuple[str, ...]
    ) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("clinical_question_tags must not contain duplicates")
        return value

    @model_validator(mode="after")
    def validate_parent_stage_boundary(self) -> "StageContext":
        if self.stage_type == StageType.INITIAL_REVIEW and self.parent_stage_id is not None:
            raise ValueError("initial_review stage must not define parent_stage_id")
        return self


__all__ = [
    "InfoModality",
    "StageContext",
    "StageFocus",
    "StageType",
    "TriggerType",
    "VisibilityPolicyHint",
]
