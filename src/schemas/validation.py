"""Phase 1-1 validation report schema objects.

本文件作用：
1. 定义可复用的结构化校验结果对象。
2. 仅表达“校验报告数据结构”，不实现完整 validator engine。
3. 为 Phase1StateEnvelope 等状态对象提供可审计的报告载体。
"""

from __future__ import annotations

import re
from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import (
    NonEmptyStr,
    find_duplicate_items,
    normalize_optional_note,
    normalize_optional_text,
)


REPORT_ID_PATTERN = re.compile(r"^report[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
ISSUE_ID_PATTERN = re.compile(r"^issue[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
CASE_ID_PATTERN = re.compile(r"^case[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
STAGE_ID_PATTERN = re.compile(r"^stage[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
BOARD_ID_PATTERN = re.compile(r"^board[_-][A-Za-z0-9][A-Za-z0-9_-]*$")
ISSUE_CODE_PATTERN = re.compile(r"^[a-z][a-z0-9_.-]*$")


class ValidationSeverity(StrEnum):
    """Structured validation issue severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationTargetKind(StrEnum):
    """Primary object-kind taxonomy for structured issue targeting."""

    STAGE_CONTEXT = "stage_context"
    EVIDENCE_ATOM = "evidence_atom"
    CLAIM_REFERENCE = "claim_reference"
    HYPOTHESIS_STATE = "hypothesis_state"
    ACTION_CANDIDATE = "action_candidate"
    HYPOTHESIS_BOARD_INIT = "hypothesis_board_init"
    PHASE1_STATE_ENVELOPE = "phase1_state_envelope"
    STATE_VALIDATION_REPORT = "state_validation_report"
    OTHER = "other"


class ValidationIssue(BaseModel):
    """One structured validation issue item."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    issue_id: NonEmptyStr
    issue_code: NonEmptyStr
    severity: ValidationSeverity
    message: NonEmptyStr
    target_kind: ValidationTargetKind
    target_id: NonEmptyStr
    field_path: str | None = None
    related_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    blocking: bool
    suggested_fix: str | None = None
    non_authoritative_note: str | None = None

    @field_validator("issue_id")
    @classmethod
    def validate_issue_id_pattern(cls, value: str) -> str:
        if not ISSUE_ID_PATTERN.fullmatch(value):
            raise ValueError("issue_id must match pattern like issue_001 or issue-001")
        return value

    @field_validator("issue_code")
    @classmethod
    def validate_issue_code_pattern(cls, value: str) -> str:
        if not ISSUE_CODE_PATTERN.fullmatch(value):
            raise ValueError(
                "issue_code must start with a letter and use lowercase letters, numbers, dot, underscore, or hyphen"
            )
        return value

    @field_validator("field_path", "suggested_fix", mode="before")
    @classmethod
    def normalize_optional_text_fields(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("non_authoritative_note", mode="before")
    @classmethod
    def normalize_note(cls, value: object) -> str | None:
        return normalize_optional_note(value)

    @field_validator("related_ids")
    @classmethod
    def validate_related_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        duplicate_related_ids = find_duplicate_items(value)
        if duplicate_related_ids:
            raise ValueError("related_ids must not contain duplicates")
        return value


class StateValidationReport(BaseModel):
    """Structured state-validation report object for Phase 1 state writes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    report_id: NonEmptyStr
    case_id: NonEmptyStr
    stage_id: NonEmptyStr
    board_id: str | None = None
    generated_at: datetime
    is_valid: bool
    has_blocking_issue: bool
    issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    validator_name: NonEmptyStr
    validator_version: NonEmptyStr
    summary: str | None = None

    @field_validator("report_id")
    @classmethod
    def validate_report_id_pattern(cls, value: str) -> str:
        if not REPORT_ID_PATTERN.fullmatch(value):
            raise ValueError("report_id must match pattern like report_001 or report-001")
        return value

    @field_validator("case_id")
    @classmethod
    def validate_case_id_pattern(cls, value: str) -> str:
        if not CASE_ID_PATTERN.fullmatch(value):
            raise ValueError("case_id must match pattern like case_001 or case-001")
        return value

    @field_validator("stage_id")
    @classmethod
    def validate_stage_id_pattern(cls, value: str) -> str:
        if not STAGE_ID_PATTERN.fullmatch(value):
            raise ValueError("stage_id must match pattern like stage_001 or stage-001")
        return value

    @field_validator("board_id", mode="before")
    @classmethod
    def normalize_board_id(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @field_validator("board_id")
    @classmethod
    def validate_board_id_pattern(cls, value: str | None) -> str | None:
        if value is None:
            return None
        if not BOARD_ID_PATTERN.fullmatch(value):
            raise ValueError("board_id must match pattern like board_001 or board-001")
        return value

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "StateValidationReport":
        duplicate_issue_ids = find_duplicate_items(
            issue.issue_id for issue in self.issues
        )
        if duplicate_issue_ids:
            raise ValueError(
                "issues must not contain duplicate issue_id values: "
                + ", ".join(duplicate_issue_ids)
            )

        derived_has_blocking_issue = any(issue.blocking for issue in self.issues)
        if self.has_blocking_issue != derived_has_blocking_issue:
            raise ValueError("has_blocking_issue must match issues[].blocking")

        if self.is_valid and derived_has_blocking_issue:
            raise ValueError("is_valid must be false when blocking issues are present")

        if not self.is_valid and not self.issues:
            raise ValueError("invalid report must include at least one issue")

        return self


__all__ = [
    "StateValidationReport",
    "ValidationIssue",
    "ValidationSeverity",
    "ValidationTargetKind",
]
