"""Phase 1-1 validation report schema objects.

本文件作用：
1. 定义可复用的结构化校验结果对象。
2. 仅表达“校验报告数据结构”，不实现完整 validator engine。
3. 为 Phase1StateEnvelope 等状态对象提供可审计的报告载体。
"""

from __future__ import annotations

from datetime import datetime
from enum import StrEnum

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from .common import NonEmptyStr


class ValidationSeverity(StrEnum):
    """Structured validation issue severity."""

    INFO = "info"
    WARNING = "warning"
    ERROR = "error"


class ValidationIssue(BaseModel):
    """One structured validation issue item."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    issue_code: NonEmptyStr
    severity: ValidationSeverity
    message: NonEmptyStr
    field_path: str | None = None
    related_ids: tuple[NonEmptyStr, ...] = Field(default_factory=tuple)
    non_authoritative_note: str | None = None

    @field_validator("field_path", "non_authoritative_note", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @field_validator("related_ids")
    @classmethod
    def validate_related_ids(cls, value: tuple[str, ...]) -> tuple[str, ...]:
        if len(set(value)) != len(value):
            raise ValueError("related_ids must not contain duplicates")
        return value


class StateValidationReport(BaseModel):
    """Structured state-validation report object for Phase 1 state writes."""

    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    generated_at: datetime
    is_valid: bool
    issues: tuple[ValidationIssue, ...] = Field(default_factory=tuple)
    validator_name: str | None = None
    validator_version: str | None = None
    summary: str | None = None

    @field_validator("validator_name", "validator_version", "summary", mode="before")
    @classmethod
    def normalize_optional_text(cls, value: object) -> str | None:
        if value is None:
            return None
        cleaned = str(value).strip()
        return cleaned or None

    @model_validator(mode="after")
    def validate_report_consistency(self) -> "StateValidationReport":
        has_error_issue = any(issue.severity is ValidationSeverity.ERROR for issue in self.issues)

        if self.is_valid and has_error_issue:
            raise ValueError("is_valid must be false when issues contain error severity")

        if not self.is_valid and not self.issues:
            raise ValueError("invalid report must include at least one issue")

        return self


__all__ = [
    "StateValidationReport",
    "ValidationIssue",
    "ValidationSeverity",
]
