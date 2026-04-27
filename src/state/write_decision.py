"""Write decision contract for Phase 1-3 validator-gated writes.

本对象只汇总一次 authoritative write 尝试的判定结果：
- 不执行验证
- 不执行持久化
- 不执行自动修复
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field, field_validator, model_validator

from ..schemas.common import NonEmptyStr, STATE_ID_PATTERN, normalize_optional_text, validate_id_pattern
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import StateValidationReport
from .write_policy import WritePolicy
from .write_status import WriteDecisionStatus


class WriteDecision(BaseModel):
    """Outcome contract for one attempted Phase1StateEnvelope write.

    该对象仅表达 validation-gate 的判定结果，不保证持久化副作用已成功完成。
    持久化失败会由 writer/sink 异常路径向上抛出。
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    candidate_state_id: NonEmptyStr
    status: WriteDecisionStatus
    policy: WritePolicy = Field(default_factory=WritePolicy)
    accepted_envelope: Phase1StateEnvelope | None = None
    reports: tuple[StateValidationReport, ...] = Field(default_factory=tuple)
    has_blocking_issue: bool | None = None
    should_persist: bool | None = None
    summary: str | None = None

    @field_validator("candidate_state_id")
    @classmethod
    def validate_candidate_state_id_pattern(cls, value: str) -> str:
        return validate_id_pattern(
            value,
            pattern=STATE_ID_PATTERN,
            field_name="candidate_state_id",
            example="state_001 or state-001",
        )

    @field_validator("summary", mode="before")
    @classmethod
    def normalize_summary(cls, value: object) -> str | None:
        return normalize_optional_text(value)

    @model_validator(mode="after")
    def validate_write_decision(self) -> "WriteDecision":
        derived_blocking = any(report.has_blocking_issue for report in self.reports)

        if self.has_blocking_issue is None:
            resolved_blocking = derived_blocking
        else:
            resolved_blocking = self.has_blocking_issue
            if self.reports and self.has_blocking_issue != derived_blocking:
                raise ValueError(
                    "has_blocking_issue must match reports[].has_blocking_issue when reports are provided"
                )

        if self.status == WriteDecisionStatus.ACCEPTED:
            if resolved_blocking:
                raise ValueError("accepted decision cannot include blocking issues")
            if self.accepted_envelope is None:
                raise ValueError("accepted decision requires accepted_envelope")

        if (
            self.status != WriteDecisionStatus.ACCEPTED
            and self.accepted_envelope is not None
        ):
            raise ValueError("accepted_envelope must exist only for accepted decisions")

        if self.accepted_envelope is not None:
            if self.accepted_envelope.state_id != self.candidate_state_id:
                raise ValueError(
                    "candidate_state_id must match accepted_envelope.state_id"
                )

        expected_should_persist = self.policy.should_persist(
            status=self.status,
            has_blocking_issue=resolved_blocking,
        )

        if self.should_persist is None:
            resolved_should_persist = expected_should_persist
        else:
            resolved_should_persist = self.should_persist
            if self.should_persist != expected_should_persist:
                raise ValueError(
                    "should_persist must match policy decision for status and blocking state"
                )

        if resolved_should_persist and self.accepted_envelope is None:
            raise ValueError("accepted_envelope is required when should_persist is true")

        if resolved_should_persist and self.status != WriteDecisionStatus.ACCEPTED:
            raise ValueError("only accepted decisions can set should_persist to true")

        object.__setattr__(self, "has_blocking_issue", resolved_blocking)
        object.__setattr__(self, "should_persist", resolved_should_persist)
        return self


__all__ = ["WriteDecision"]
