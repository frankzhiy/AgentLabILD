"""Phase 1-3 conservative temporal validator.

本模块只做 Phase 1-3 范围内的保守时序检查：
1. 只检查同一 envelope 内部的基础时序一致性。
2. 不实现跨阶段回放、事件日志或长期纵向推理。
"""

from __future__ import annotations

from datetime import datetime

from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from ..utils.time import utc_now

TEMPORAL_VALIDATOR_NAME = "phase1_temporal_validator"
TEMPORAL_VALIDATOR_VERSION = "1.3.0"


def validate_phase1_temporal(
    envelope: Phase1StateEnvelope,
    *,
    report_id: str | None = None,
    generated_at: datetime | None = None,
    validator_name: str = TEMPORAL_VALIDATOR_NAME,
    validator_version: str = TEMPORAL_VALIDATOR_VERSION,
) -> StateValidationReport:
    """Run conservative intra-envelope temporal checks for Phase 1-3."""

    issues: list[ValidationIssue] = []

    if envelope.stage_context.created_at > envelope.created_at:
        issues.append(
            ValidationIssue(
                issue_id=f"issue-temporal-{len(issues) + 1:04d}",
                issue_code="temporal.stage_after_envelope",
                severity=ValidationSeverity.ERROR,
                message=(
                    "stage_context.created_at must be earlier than or equal to envelope.created_at"
                ),
                target_kind=ValidationTargetKind.STAGE_CONTEXT,
                target_id=envelope.stage_context.stage_id,
                field_path="stage_context.created_at",
                related_ids=(envelope.state_id,),
                blocking=True,
            )
        )

    if envelope.board_init.initialized_at > envelope.created_at:
        issues.append(
            ValidationIssue(
                issue_id=f"issue-temporal-{len(issues) + 1:04d}",
                issue_code="temporal.board_after_envelope",
                severity=ValidationSeverity.ERROR,
                message=(
                    "board_init.initialized_at must be earlier than or equal to envelope.created_at"
                ),
                target_kind=ValidationTargetKind.HYPOTHESIS_BOARD_INIT,
                target_id=envelope.board_init.board_id,
                field_path="board_init.initialized_at",
                related_ids=(envelope.state_id,),
                blocking=True,
            )
        )

    if envelope.stage_context.stage_index == 0 and envelope.parent_state_id is not None:
        issues.append(
            ValidationIssue(
                issue_id=f"issue-temporal-{len(issues) + 1:04d}",
                issue_code="temporal.invalid_root_parent",
                severity=ValidationSeverity.ERROR,
                message="stage_index == 0 requires parent_state_id to be None",
                target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
                target_id=envelope.state_id,
                field_path="parent_state_id",
                blocking=True,
            )
        )

    if envelope.parent_state_id is not None and envelope.state_version < 2:
        issues.append(
            ValidationIssue(
                issue_id=f"issue-temporal-{len(issues) + 1:04d}",
                issue_code="temporal.invalid_state_version",
                severity=ValidationSeverity.ERROR,
                message="parent_state_id present requires state_version >= 2",
                target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
                target_id=envelope.state_id,
                field_path="state_version",
                related_ids=(envelope.parent_state_id,),
                blocking=True,
            )
        )

    has_blocking_issue = any(issue.blocking for issue in issues)

    if generated_at is None:
        generated_at = utc_now()

    if report_id is None:
        report_id = f"report-temporal-{envelope.state_id}"

    if issues:
        summary = (
            "Temporal validation completed with blocking issues: "
            f"total={len(issues)}, blocking={sum(1 for issue in issues if issue.blocking)}."
        )
    else:
        summary = "Temporal validation passed."

    return StateValidationReport(
        report_id=report_id,
        case_id=envelope.case_id,
        stage_id=envelope.stage_context.stage_id,
        board_id=envelope.board_init.board_id,
        generated_at=generated_at,
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=tuple(issues),
        validator_name=validator_name,
        validator_version=validator_version,
        summary=summary,
    )


__all__ = [
    "TEMPORAL_VALIDATOR_NAME",
    "TEMPORAL_VALIDATOR_VERSION",
    "validate_phase1_temporal",
]