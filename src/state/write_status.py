"""Write-decision status contract for Phase 1-3.

本模块仅定义写门禁结果状态，不包含校验、持久化或编排逻辑。
"""

from __future__ import annotations

from enum import StrEnum


class WriteDecisionStatus(StrEnum):
    """Outcome class for one attempted authoritative write."""

    ACCEPTED = "accepted"
    REJECTED = "rejected"
    MANUAL_REVIEW = "manual_review"


__all__ = ["WriteDecisionStatus"]
