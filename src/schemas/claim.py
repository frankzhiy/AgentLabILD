"""Phase 1-1 ClaimReference Schema（权威 claim-证据链接对象）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的权威 ClaimReference 对象。
2. 将“claim 与 evidence_ids 的关联”显式化，供后续 HypothesisState / ActionCandidate 复用。
3. 通过严格校验阻断无证据 claim、id 混用和字段漂移。

边界说明：
1. 本文件不承载诊断置信度、仲裁流程逻辑、source span。
2. non_authoritative_note 仅用于说明，不可作为权威推理依据。
3. ClaimReference 是“可追溯链接对象”，不是最终诊断对象。
4. claim_ref_id 是对象实例唯一标识；claim_key 是语义对齐键，不能替代对象身份。

校验说明：
1. 使用 extra="forbid" 与 str_strip_whitespace=True。
2. evidence_ids 必须非空且不允许重复。
3. claim_key 在写入前归一化为 snake_case。
4. target_id 不得与 claim_ref_id 相同，避免对象自引用。
5. claim_text 必须表达单个原子判断，且长度受限以避免回退到长篇解释。
6. strength 表示 claim 与 target 的关系强度，不表示诊断置信度。
"""

from __future__ import annotations

import re
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..provenance.model import ClaimProvenance
from .common import (
    ACTION_CANDIDATE_ID_PATTERN,
    CLAIM_REF_ID_PATTERN,
    HYPOTHESIS_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    validate_id_pattern,
)

AtomicClaimText = Annotated[str, Field(min_length=1, max_length=300)]


class ClaimTargetKind(StrEnum):
    """Claim 指向的目标对象类型。"""

    HYPOTHESIS = "hypothesis"
    ACTION = "action"


class ClaimRelation(StrEnum):
    """Claim 与目标对象之间的关系类型。"""

    SUPPORTS = "supports"
    REFUTES = "refutes"
    INDICATES_MISSING_INFORMATION_FOR = "indicates_missing_information_for"
    RAISES_SAFETY_CONCERN_FOR = "raises_safety_concern_for"


class ClaimStrength(StrEnum):
    """Claim-to-target relation strength（非诊断置信度）。"""

    WEAK = "weak"
    MODERATE = "moderate"
    STRONG = "strong"


class ClaimReference(BaseModel):
    """Authoritative claim-to-evidence link object for Phase 1-1.

    Field semantics:
    1. claim_ref_id: unique object id for this ClaimReference instance.
    2. claim_key: normalized semantic key for alignment/diff/dedup, not identity.
    3. strength: strength of claim-to-target relation, not diagnostic confidence.
    4. claim_text: one atomic judgment only (bounded length to avoid long-form reasoning).
    """

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["claim_reference"] = "claim_reference"
    claim_ref_id: NonEmptyStr = Field(
        description="Unique object id for this ClaimReference instance."
    )
    stage_id: NonEmptyStr
    target_kind: ClaimTargetKind
    target_id: NonEmptyStr
    claim_text: AtomicClaimText
    relation: ClaimRelation
    evidence_ids: tuple[NonEmptyStr, ...]
    claim_key: str | None = Field(
        default=None,
        description=(
            "Normalized semantic key used for alignment/diff/dedup across stages; "
            "not a unique identity field."
        ),
    )
    strength: ClaimStrength | None = Field(
        default=None,
        description=(
            "Strength of the claim-to-target relation; not diagnostic confidence."
        ),
    )
    non_authoritative_note: str | None = None
    provenance: ClaimProvenance | None = None

    @field_validator("target_kind", mode="before")
    @classmethod
    def normalize_target_kind(cls, value: object) -> object:
        # Backward-aware normalization for historical payloads.
        if isinstance(value, str) and value == "action_candidate":
            return ClaimTargetKind.ACTION.value
        return value

    @field_validator("claim_ref_id")
    @classmethod
    def validate_claim_ref_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=CLAIM_REF_ID_PATTERN,
            field_name="claim_ref_id",
            example="claim_ref_001 or claim_ref-001",
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

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("evidence_ids must contain at least one evidence id")
        if len(set(value)) != len(value):
            raise ValueError("evidence_ids must not contain duplicates")
        return value

    @field_validator("claim_key", mode="before")
    @classmethod
    def normalize_claim_key(cls, value: object) -> str | None:
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
    def validate_target_boundary(self) -> "ClaimReference":
        if self.target_id == self.claim_ref_id:
            raise ValueError("target_id must not equal claim_ref_id")

        if self.target_kind is ClaimTargetKind.HYPOTHESIS:
            if not HYPOTHESIS_ID_PATTERN.fullmatch(self.target_id):
                raise ValueError(
                    "target_id must match hypothesis pattern like hyp_001 or hypothesis-001"
                )

        if self.target_kind is ClaimTargetKind.ACTION:
            if not ACTION_CANDIDATE_ID_PATTERN.fullmatch(self.target_id):
                raise ValueError(
                    "target_id must match action pattern like action_001 or action_candidate-001"
                )

        return self

    @model_validator(mode="after")
    def validate_provenance_alignment(self) -> "ClaimReference":
        if self.provenance is None:
            return self

        if self.provenance.stage_id != self.stage_id:
            raise ValueError("provenance.stage_id must equal claim stage_id")

        if self.provenance.claim_ref_id != self.claim_ref_id:
            raise ValueError("provenance.claim_ref_id must equal claim_ref_id")

        missing_evidence_ids = set(self.provenance.evidence_ids) - set(self.evidence_ids)
        if missing_evidence_ids:
            raise ValueError(
                "provenance.evidence_ids must be subset of claim evidence_ids"
            )

        return self


__all__ = [
    "ClaimReference",
    "ClaimRelation",
    "ClaimStrength",
    "ClaimTargetKind",
]