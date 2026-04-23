"""Phase 1-1 假设板初始化根对象 Schema（HypothesisBoardInit）。

本文件作用：
1. 定义 ILD-MDT 分阶段推理中的“阶段作用域 board 根对象”。
2. board 仅通过 id 引用 evidence / hypothesis / action 对象，不内嵌对象内容。
3. 为后续阶段化演化保留 parent_board_id 与初始化来源字段，不引入仲裁/更新机制。

边界说明：
1. 本文件不是诊断对象，不承载最终诊断结论。
2. 本文件不实现冲突处理、仲裁逻辑或更新逻辑。
3. ranked_hypothesis_ids 仅表达排序视图，不改变 hypothesis 对象本身。
4. non_authoritative_note 仅用于说明，不可作为权威推理依据。

校验说明：
1. 使用 extra="forbid" 与 str_strip_whitespace=True。
2. case_id、board_id、stage_id 执行命名模式校验，降低 id 混用风险。
3. hypothesis_ids 必须非空。
4. ranked_hypothesis_ids 必须是 hypothesis_ids 的子集。
5. parent_board_id 若存在，不得与 board_id 相同。
6. init_source 与 parent_board_id 需要满足语义联动约束。
7. evidence/hypothesis/action 引用字段均执行去重与 id pattern 校验。
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum
from typing import Annotated, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    ACTION_CANDIDATE_ID_PATTERN,
    BOARD_ID_PATTERN,
    CASE_ID_PATTERN,
    EVIDENCE_ID_PATTERN,
    HYPOTHESIS_ID_PATTERN,
    STAGE_ID_PATTERN,
    NonEmptyStr,
    validate_id_pattern,
)

class BoardStatus(StrEnum):
    """Board root status taxonomy for initialization phase."""

    DRAFT = "draft"
    INITIALIZED = "initialized"
    READY_FOR_REVIEW = "ready_for_review"


class BoardInitSource(StrEnum):
    """Controlled source taxonomy for board initialization."""

    STAGE_BOOTSTRAP = "stage_bootstrap"
    PARENT_BOARD_PROPAGATION = "parent_board_propagation"
    MANUAL_STRUCTURED_ENTRY = "manual_structured_entry"
    MIGRATION = "migration"


class HypothesisBoardInit(BaseModel):
    """Authoritative stage-scoped board root object for Phase 1-1."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    kind: Literal["hypothesis_board_init"] = "hypothesis_board_init"
    board_id: NonEmptyStr
    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    board_status: BoardStatus
    init_source: BoardInitSource
    initialized_at: datetime
    evidence_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    hypothesis_ids: tuple[NonEmptyStr, ...]
    action_candidate_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    ranked_hypothesis_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    parent_board_id: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("board_id")
    @classmethod
    def validate_board_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=BOARD_ID_PATTERN,
            field_name="board_id",
            example="board_001 or board-001",
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

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STAGE_ID_PATTERN,
            field_name="stage_id",
            example="stage_001 or stage-001",
        )

    @field_validator("parent_board_id", mode="before")
    @classmethod
    def normalize_parent_board_id(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("parent_board_id")
    @classmethod
    def validate_parent_board_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        return validate_id_pattern(
            value,
            pattern=BOARD_ID_PATTERN,
            field_name="parent_board_id",
            example="board_001 or board-001",
        )

    @field_validator("evidence_ids")
    @classmethod
    def validate_evidence_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("evidence_ids must not contain duplicates")

        for evidence_id in value:
            if not EVIDENCE_ID_PATTERN.fullmatch(evidence_id):
                raise ValueError(
                    "evidence_ids must match pattern like ev_001 or evd-001"
                )

        return value

    @field_validator("hypothesis_ids")
    @classmethod
    def validate_hypothesis_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if not value:
            raise ValueError("hypothesis_ids must contain at least one hypothesis id")
        if len(set(value)) != len(value):
            raise ValueError("hypothesis_ids must not contain duplicates")

        for hypothesis_id in value:
            if not HYPOTHESIS_ID_PATTERN.fullmatch(hypothesis_id):
                raise ValueError(
                    "hypothesis_ids must match pattern like hyp_001 or hypothesis-001"
                )

        return value

    @field_validator("action_candidate_ids")
    @classmethod
    def validate_action_candidate_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("action_candidate_ids must not contain duplicates")

        for action_candidate_id in value:
            if not ACTION_CANDIDATE_ID_PATTERN.fullmatch(action_candidate_id):
                raise ValueError(
                    "action_candidate_ids must match pattern like action_001 or action_candidate-001"
                )

        return value

    @field_validator("ranked_hypothesis_ids")
    @classmethod
    def validate_ranked_hypothesis_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("ranked_hypothesis_ids must not contain duplicates")

        for hypothesis_id in value:
            if not HYPOTHESIS_ID_PATTERN.fullmatch(hypothesis_id):
                raise ValueError(
                    "ranked_hypothesis_ids must match pattern like hyp_001 or hypothesis-001"
                )

        return value

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_non_authoritative_note(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_board_boundaries(self) -> "HypothesisBoardInit":
        if not set(self.ranked_hypothesis_ids).issubset(set(self.hypothesis_ids)):
            raise ValueError("ranked_hypothesis_ids must be a subset of hypothesis_ids")

        if self.parent_board_id is not None and self.parent_board_id == self.board_id:
            raise ValueError("parent_board_id must not equal board_id")

        if self.init_source is BoardInitSource.PARENT_BOARD_PROPAGATION:
            if self.parent_board_id is None:
                raise ValueError(
                    "parent_board_id is required when init_source is parent_board_propagation"
                )

        if self.init_source is BoardInitSource.STAGE_BOOTSTRAP:
            if self.parent_board_id is not None:
                raise ValueError(
                    "parent_board_id must be empty when init_source is stage_bootstrap"
                )

        return self


__all__ = [
    "BoardInitSource",
    "BoardStatus",
    "HypothesisBoardInit",
]
