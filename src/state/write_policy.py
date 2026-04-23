"""Write policy contract for Phase 1-3 write-gate.

本模块只建模“门禁策略参数”，不承载 validator 报告内容。
"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict

from .write_status import WriteDecisionStatus


class WritePolicy(BaseModel):
    """Minimal write-gate behavior contract.

    Phase 1-3 约束：
    1. blocking issue 永远阻断持久化。
    2. accepted 默认可持久化。
    3. manual_review 默认不可持久化，需显式策略放开。
    """

    model_config = ConfigDict(extra="forbid", frozen=True)

    allow_manual_review_persist: bool = False

    def should_persist(
        self,
        *,
        status: WriteDecisionStatus,
        has_blocking_issue: bool,
    ) -> bool:
        """Decide persistence intent from status + blocking signal."""

        if has_blocking_issue:
            return False

        if status == WriteDecisionStatus.ACCEPTED:
            return True

        if status == WriteDecisionStatus.MANUAL_REVIEW:
            return self.allow_manual_review_persist

        return False


__all__ = ["WritePolicy"]
