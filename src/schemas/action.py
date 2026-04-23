"""Phase 1-1 候选行动对象 Schema（ActionCandidate）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的权威候选行动对象（ActionCandidate）。
2. 将候选行动与 ClaimReference（claim_ref_id）建立显式链接，而不是直接引用 evidence_id。
3. 用结构化字段分离支持、反驳、缺失信息与安全关注四类 claim，支撑后续机制治理。

边界说明：
1. 本文件不承载仲裁、更新管理或最终管理计划逻辑。
2. 本文件不允许通过 direct evidence_ids 绕过 ClaimReference。
3. ActionCandidate 是“候选行动对象”，不是最终执行计划。
4. non_authoritative_note 仅用于说明，不可作为权威推理依据。

校验说明：
1. 使用 extra="forbid" 与 str_strip_whitespace=True。
2. action_candidate_id 与 stage_id 执行命名模式校验，降低 id 混用风险。
3. linked_hypothesis_ids 与四类 claim_ref_ids 均执行去重与模式校验。
4. 四类 claim_ref_ids 之间不得交叉复用同一 claim_ref_id。
5. 至少应包含一条 claim_ref_id，避免无依据候选行动进入状态层。
6. blocked 状态至少需要 refuting 或 safety_concern 依据，避免无阻断理由的阻断状态。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    ACTION_CANDIDATE_ID_PATTERN,
    CLAIM_REF_ID_PATTERN,
    HYPOTHESIS_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    validate_id_pattern,
)

ActionText = Annotated[str, Field(min_length=1, max_length=220)]


class ActionType(StrEnum):
    """Taxonomy of candidate action intent for staged ILD reasoning."""

    REQUEST_ADDITIONAL_HISTORY = "request_additional_history"
    ORDER_DIAGNOSTIC_TEST = "order_diagnostic_test"
    REQUEST_MULTIDISCIPLINARY_REVIEW = "request_multidisciplinary_review"
    START_OR_ADJUST_TREATMENT = "start_or_adjust_treatment"
    MONITOR_WITH_DEFINED_CHECKPOINT = "monitor_with_defined_checkpoint"
    SAFETY_ESCALATION = "safety_escalation"


class ActionStatus(StrEnum):
    """Working status for candidate action on hypothesis-aligned priority axis."""

    UNDER_CONSIDERATION = "under_consideration"
    PRIORITIZED = "prioritized"
    DEPRIORITIZED = "deprioritized"
    BLOCKED = "blocked"


class ActionUrgency(StrEnum):
    """Operational urgency level for candidate action tracking."""

    ROUTINE = "routine"
    EXPEDITED = "expedited"
    URGENT = "urgent"
    EMERGENT = "emergent"


class ActionCandidate(BaseModel):
    """Authoritative candidate-action object for Phase 1-1."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["action_candidate"] = "action_candidate"
    action_candidate_id: NonEmptyStr = Field(
        description="Unique object id for this ActionCandidate instance."
    )
    action_key: str | None = Field(
        default=None,
        description=(
            "Normalized semantic key used for cross-stage alignment/diff/dedup; "
            "not a unique identity field."
        ),
    )
    stage_id: NonEmptyStr
    action_type: ActionType
    action_text: ActionText
    status: ActionStatus
    urgency: ActionUrgency
    linked_hypothesis_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    supporting_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    refuting_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    missing_information_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(
        default_factory=tuple
    )
    safety_concern_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    rank_index: int | None = Field(default=None, ge=1)
    non_authoritative_note: str | None = None

    @field_validator("action_candidate_id")
    @classmethod
    def validate_action_candidate_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=ACTION_CANDIDATE_ID_PATTERN,
            field_name="action_candidate_id",
            example="action_001 or action_candidate-001",
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

    @field_validator("linked_hypothesis_ids")
    @classmethod
    def validate_linked_hypothesis_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("linked_hypothesis_ids must not contain duplicates")

        for hypothesis_id in value:
            if not HYPOTHESIS_ID_PATTERN.fullmatch(hypothesis_id):
                raise ValueError(
                    "linked_hypothesis_ids must match pattern like hyp_001 or hypothesis-001"
                )

        return value

    @field_validator(
        "supporting_claim_ref_ids",
        "refuting_claim_ref_ids",
        "missing_information_claim_ref_ids",
        "safety_concern_claim_ref_ids",
    )
    @classmethod
    def validate_claim_ref_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("claim_ref_ids must not contain duplicates")

        for claim_ref_id in value:
            if not CLAIM_REF_ID_PATTERN.fullmatch(claim_ref_id):
                raise ValueError(
                    "claim_ref_ids must match pattern like claim_ref_001 or claim_ref-001"
                )

        return value

    @field_validator("action_key", mode="before")
    @classmethod
    def normalize_action_key(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip().lower()
        if not cleaned:
            return None

        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or None

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_claim_ref_boundaries(self) -> "ActionCandidate":
        supporting_ids = set(self.supporting_claim_ref_ids)
        refuting_ids = set(self.refuting_claim_ref_ids)
        missing_info_ids = set(self.missing_information_claim_ref_ids)
        safety_ids = set(self.safety_concern_claim_ref_ids)

        if not (supporting_ids or refuting_ids or missing_info_ids or safety_ids):
            raise ValueError(
                "at least one claim_ref id is required across supporting/refuting/missing-information/safety-concern buckets"
            )

        bucket_sets = {
            "supporting_claim_ref_ids": supporting_ids,
            "refuting_claim_ref_ids": refuting_ids,
            "missing_information_claim_ref_ids": missing_info_ids,
            "safety_concern_claim_ref_ids": safety_ids,
        }

        bucket_names = tuple(bucket_sets)
        for left_index, left_name in enumerate(bucket_names):
            left_set = bucket_sets[left_name]
            for right_name in bucket_names[left_index + 1 :]:
                if left_set & bucket_sets[right_name]:
                    raise ValueError(f"{left_name} and {right_name} must not overlap")

        if self.status is ActionStatus.BLOCKED and not (refuting_ids or safety_ids):
            raise ValueError(
                "blocked status requires at least one refuting or safety_concern claim_ref id"
            )

        return self


__all__ = [
    "ActionCandidate",
    "ActionStatus",
    "ActionType",
    "ActionUrgency",
]
