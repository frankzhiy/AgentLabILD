"""Phase 1-2 provenance validator.

本模块职责：
1. 调用 provenance checker 收集结构化 issue。
2. 将 issue 转换为 ValidationIssue。
3. 生成可直接用于写入门禁的 StateValidationReport（本任务仅建模，不实现 state_writer）。
"""

from __future__ import annotations

from datetime import datetime

from ..provenance.checker import ProvenanceCheckIssue, check_phase1_provenance
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import StateValidationReport, ValidationIssue

DEFAULT_VALIDATOR_NAME = "phase1_provenance_validator"
DEFAULT_VALIDATOR_VERSION = "1.2.0"


def build_provenance_validation_issues(
    envelope: Phase1StateEnvelope,
    *,
    require_provenance: bool = False,
) -> tuple[ValidationIssue, ...]:
    """Collect provenance checker issues and convert them to ValidationIssue."""

    raw_issues = check_phase1_provenance(
        envelope,
        require_provenance=require_provenance,
    )
    return convert_provenance_issues_to_validation_issues(raw_issues)


def convert_provenance_issues_to_validation_issues(
    issues: tuple[ProvenanceCheckIssue, ...],
) -> tuple[ValidationIssue, ...]:
    """Convert checker issues into ValidationIssue with stable generated issue_id."""

    validation_issues: list[ValidationIssue] = []

    for index, issue in enumerate(issues, start=1):
        validation_issues.append(
            ValidationIssue(
                issue_id=f"issue-provenance-{index:04d}",
                issue_code=issue.issue_code,
                severity=issue.severity,
                message=issue.message,
                target_kind=issue.target_kind,
                target_id=issue.target_id,
                field_path=issue.field_path,
                related_ids=issue.related_ids,
                blocking=issue.blocking,
                suggested_fix=issue.suggested_fix,
                non_authoritative_note=issue.non_authoritative_note,
            )
        )

    return tuple(validation_issues)


def validate_phase1_provenance(
    envelope: Phase1StateEnvelope,
    *,
    require_provenance: bool = False,
    report_id: str | None = None,
    generated_at: datetime | None = None,
    validator_name: str = DEFAULT_VALIDATOR_NAME,
    validator_version: str = DEFAULT_VALIDATOR_VERSION,
) -> StateValidationReport:
    """Build a provenance-focused StateValidationReport for one envelope."""

    issues = build_provenance_validation_issues(
        envelope,
        require_provenance=require_provenance,
    )

    has_blocking_issue = any(issue.blocking for issue in issues)
    issue_count = len(issues)
    blocking_issue_count = sum(1 for issue in issues if issue.blocking)
    non_blocking_issue_count = issue_count - blocking_issue_count

    if issue_count == 0:
        summary = "No provenance issues found."
    else:
        summary = (
            "Provenance validation completed: "
            f"total={issue_count}, blocking={blocking_issue_count}, "
            f"non_blocking={non_blocking_issue_count}."
        )

    if generated_at is None:
        generated_at = datetime.utcnow()

    if report_id is None:
        report_id = f"report-provenance-{envelope.state_id}"

    return StateValidationReport(
        report_id=report_id,
        case_id=envelope.case_id,
        stage_id=envelope.stage_context.stage_id,
        board_id=envelope.board_init.board_id,
        generated_at=generated_at,
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=issues,
        validator_name=validator_name,
        validator_version=validator_version,
        summary=summary,
    )


__all__ = [
    "DEFAULT_VALIDATOR_NAME",
    "DEFAULT_VALIDATOR_VERSION",
    "build_provenance_validation_issues",
    "convert_provenance_issues_to_validation_issues",
    "validate_phase1_provenance",
]
