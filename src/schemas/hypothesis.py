"""Phase 1-1 候选假设账本 Schema（HypothesisState）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的权威候选假设对象（HypothesisState）。
2. 将候选假设与 ClaimReference（claim_ref_id）建立显式链接，而不是直接引用 evidence_id。
3. 用结构化字段分离支持、反驳、缺失信息三类 claim，便于后续版本化修订。

边界说明：
1. 本文件不承载仲裁、冲突解决、更新管理或行动规划逻辑。
2. 本文件不允许通过 direct evidence_ids 绕过 ClaimReference。
3. next_best_test 仅为简短测试方向提示，不是详细行动计划。
4. non_authoritative_note 仅用于说明，不可作为权威推理依据。

校验说明：
1. 使用 extra="forbid" 与 str_strip_whitespace=True。
2. hypothesis_id 与 stage_id 均执行命名模式校验，降低 id 混用风险。
3. supporting/refuting/missing_information 三类 claim_ref_ids 各自去重且均需匹配 claim_ref id 模式。
4. 三类 claim_ref_ids 之间不得交叉复用同一 claim_ref_id。
5. 至少应包含一条 claim_ref_id，避免无依据候选假设进入账本。
6. hypothesis_key 在写入前归一化为 snake_case，用于跨阶段语义对齐。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator


NonEmptyStr = Annotated[str, Field(min_length=1)]
HypothesisLabel = Annotated[str, Field(min_length=1, max_length=160)]
NextBestTestText = Annotated[str, Field(min_length=1, max_length=120)]


HYPOTHESIS_ID_PATTERN = re.compile(r"^hyp(?:othesis)?[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_ID_PATTERN = re.compile(r"^stage[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
CLAIM_REF_ID_PATTERN = re.compile(r"^claim_ref[_-][A-Za-z0-9][A-Za-z0-9_-]*$")


class HypothesisStatus(StrEnum):
    """Working status for a candidate hypothesis in staged ledger."""

    UNDER_CONSIDERATION = "under_consideration"
    PRIORITIZED = "prioritized"
    DEPRIORITIZED = "deprioritized"
    RULED_OUT = "ruled_out"


class HypothesisConfidenceLevel(StrEnum):
    """Coarse confidence level for candidate hypothesis tracking."""

    VERY_LOW = "very_low"
    LOW = "low"
    MODERATE = "moderate"
    HIGH = "high"
    VERY_HIGH = "very_high"


class HypothesisState(BaseModel):
    """Authoritative candidate-hypothesis ledger object for Phase 1-1."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["hypothesis_state"] = "hypothesis_state"
    hypothesis_id: NonEmptyStr = Field(
        description="Unique object id for this HypothesisState instance."
    )
    hypothesis_key: str | None = Field(
        default=None,
        description=(
            "Normalized semantic key used for cross-stage alignment/diff/dedup; "
            "not a unique identity field."
        ),
    )
    stage_id: NonEmptyStr
    hypothesis_label: HypothesisLabel
    status: HypothesisStatus
    confidence_level: HypothesisConfidenceLevel
    supporting_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    refuting_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    missing_information_claim_ref_ids: tuple[NonEmptyStr, ...] = Field(
        default_factory=tuple
    )
    rank_index: int | None = Field(default=None, ge=1)
    next_best_test: NextBestTestText | None = Field(
        default=None,
        description="Optional concise hint of what test could best reduce uncertainty.",
    )
    non_authoritative_note: str | None = None

    @field_validator("hypothesis_id")
    @classmethod
    def validate_hypothesis_id_pattern(cls, value: str) -> str:
        if not HYPOTHESIS_ID_PATTERN.fullmatch(value):
            raise ValueError(
                "hypothesis_id must match pattern like hyp_001 or hypothesis-001"
            )
        return value

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        if not STAGE_ID_PATTERN.fullmatch(value):
            raise ValueError("stage_id must match pattern like stage_001 or stage-001")
        return value

    @field_validator("hypothesis_key", mode="before")
    @classmethod
    def normalize_hypothesis_key(cls, value: object) -> str | None:
        if value is None:
            return None

        cleaned = str(value).strip().lower()
        if not cleaned:
            return None

        cleaned = re.sub(r"[^a-z0-9]+", "_", cleaned)
        cleaned = re.sub(r"_+", "_", cleaned).strip("_")
        return cleaned or None

    @field_validator(
        "supporting_claim_ref_ids",
        "refuting_claim_ref_ids",
        "missing_information_claim_ref_ids",
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

    @field_validator("next_best_test", "non_authoritative_note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_claim_ref_boundaries(self) -> "HypothesisState":
        supporting_ids = set(self.supporting_claim_ref_ids)
        refuting_ids = set(self.refuting_claim_ref_ids)
        missing_info_ids = set(self.missing_information_claim_ref_ids)

        if not (supporting_ids or refuting_ids or missing_info_ids):
            raise ValueError(
                "at least one claim_ref id is required across supporting/refuting/missing-information buckets"
            )

        if supporting_ids & refuting_ids:
            raise ValueError(
                "supporting_claim_ref_ids and refuting_claim_ref_ids must not overlap"
            )

        if supporting_ids & missing_info_ids:
            raise ValueError(
                "supporting_claim_ref_ids and missing_information_claim_ref_ids must not overlap"
            )

        if refuting_ids & missing_info_ids:
            raise ValueError(
                "refuting_claim_ref_ids and missing_information_claim_ref_ids must not overlap"
            )

        return self


__all__ = [
    "HypothesisConfidenceLevel",
    "HypothesisState",
    "HypothesisStatus",
]
