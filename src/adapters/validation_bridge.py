from __future__ import annotations

from enum import StrEnum

from pydantic import BaseModel, ConfigDict, model_validator

from ..schemas.common import find_duplicate_items
from ..schemas.intake import SourceDocument
from ..schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from ..utils.time import utc_now
from ..validators.provenance_validator import validate_evidence_atoms_against_sources
from .case_structuring import CaseStructuringDraft
from .evidence_atomization import EvidenceAtomizationDraft

CASE_STRUCTURING_BRIDGE_VALIDATOR_NAME = "phase1_case_structuring_adapter_bridge"
CASE_STRUCTURING_BRIDGE_VALIDATOR_VERSION = "1.0.0"

EVIDENCE_ATOMIZATION_BRIDGE_VALIDATOR_NAME = "phase1_evidence_atomization_adapter_bridge"
EVIDENCE_ATOMIZATION_BRIDGE_VALIDATOR_VERSION = "1.0.0"


class AdapterValidationBridgeStatus(StrEnum):
    PASSED = "passed"
    FAILED = "failed"
    MANUAL_REVIEW = "manual_review"


class AdapterValidationBridgeResult(BaseModel):
    model_config = ConfigDict(extra="forbid", str_strip_whitespace=True)

    status: AdapterValidationBridgeStatus
    case_structuring_report: StateValidationReport | None = None
    evidence_atomization_report: StateValidationReport | None = None
    has_blocking_issue: bool
    summary: str

    @model_validator(mode="after")
    def validate_result_consistency(self) -> "AdapterValidationBridgeResult":
        if self.status is AdapterValidationBridgeStatus.PASSED:
            if self.has_blocking_issue:
                raise ValueError("passed status must not contain blocking issues")
            if (
                self.case_structuring_report is None
                and self.evidence_atomization_report is None
            ):
                raise ValueError("passed status requires at least one validation report")

        if self.status is AdapterValidationBridgeStatus.FAILED:
            if not self.has_blocking_issue:
                raise ValueError("failed status requires has_blocking_issue=True")

        return self


def validate_case_structuring_draft_against_sources(
    draft: CaseStructuringDraft,
    source_documents: tuple[SourceDocument, ...],
) -> StateValidationReport:
    issues: list[ValidationIssue] = []

    duplicate_source_doc_ids = find_duplicate_items(
        source_document.source_doc_id for source_document in source_documents
    )
    if duplicate_source_doc_ids:
        issues.append(
            _build_issue(
                issue_id_prefix="issue-adapter-case-",
                index=len(issues) + 1,
                issue_code="adapter_bridge.duplicate_source_document_id",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Source document registry has duplicate source_doc_id values: "
                    + ", ".join(duplicate_source_doc_ids)
                    + "."
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id="source_document_registry",
                field_path="source_documents.source_doc_id",
                related_ids=duplicate_source_doc_ids,
                blocking=True,
            )
        )

    source_documents_by_id = {
        source_document.source_doc_id: source_document
        for source_document in source_documents
    }
    registered_source_doc_ids = set(source_documents_by_id)

    unknown_draft_source_doc_ids = tuple(
        sorted(set(draft.source_doc_ids) - registered_source_doc_ids)
    )
    if unknown_draft_source_doc_ids:
        issues.append(
            _build_issue(
                issue_id_prefix="issue-adapter-case-",
                index=len(issues) + 1,
                issue_code="adapter_bridge.case_draft_source_doc_not_registered",
                severity=ValidationSeverity.ERROR,
                message=(
                    "draft.source_doc_ids must be covered by registered source documents"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id=draft.draft_id,
                field_path="source_doc_ids",
                related_ids=unknown_draft_source_doc_ids,
                blocking=True,
            )
        )

    for timeline_index, timeline_item in enumerate(draft.timeline_items):
        source_document = source_documents_by_id.get(timeline_item.source_doc_id)
        if source_document is None:
            issues.append(
                _build_issue(
                    issue_id_prefix="issue-adapter-case-",
                    index=len(issues) + 1,
                    issue_code="adapter_bridge.timeline_source_doc_not_registered",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "timeline item source_doc_id is not present in registered source documents"
                    ),
                    target_kind=ValidationTargetKind.OTHER,
                    target_id=timeline_item.timeline_item_id,
                    field_path=f"timeline_items[{timeline_index}].source_doc_id",
                    related_ids=(timeline_item.source_doc_id,),
                    blocking=True,
                )
            )
            continue

        _append_case_span_issues(
            issues=issues,
            issue_id_prefix="issue-adapter-case-",
            target_id=timeline_item.timeline_item_id,
            source_doc_id=timeline_item.source_doc_id,
            source_text=source_document.raw_text,
            source_span_start=timeline_item.source_span_start,
            source_span_end=timeline_item.source_span_end,
            field_path_prefix=f"timeline_items[{timeline_index}]",
            item_label="timeline item",
            pair_issue_code="adapter_bridge.timeline_span_pair_required",
            invalid_issue_code="adapter_bridge.timeline_span_invalid",
            out_of_bounds_issue_code="adapter_bridge.timeline_span_out_of_bounds",
        )

    for finding_index, finding in enumerate(draft.normalized_findings):
        source_document = source_documents_by_id.get(finding.source_doc_id)
        if source_document is None:
            issues.append(
                _build_issue(
                    issue_id_prefix="issue-adapter-case-",
                    index=len(issues) + 1,
                    issue_code="adapter_bridge.finding_source_doc_not_registered",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "normalized finding source_doc_id is not present in registered source documents"
                    ),
                    target_kind=ValidationTargetKind.OTHER,
                    target_id=finding.finding_id,
                    field_path=f"normalized_findings[{finding_index}].source_doc_id",
                    related_ids=(finding.source_doc_id,),
                    blocking=True,
                )
            )
            continue

        _append_case_span_issues(
            issues=issues,
            issue_id_prefix="issue-adapter-case-",
            target_id=finding.finding_id,
            source_doc_id=finding.source_doc_id,
            source_text=source_document.raw_text,
            source_span_start=finding.source_span_start,
            source_span_end=finding.source_span_end,
            field_path_prefix=f"normalized_findings[{finding_index}]",
            item_label="normalized finding",
            pair_issue_code="adapter_bridge.finding_span_pair_required",
            invalid_issue_code="adapter_bridge.finding_span_invalid",
            out_of_bounds_issue_code="adapter_bridge.finding_span_out_of_bounds",
        )

    has_blocking_issue = any(issue.blocking for issue in issues)
    return StateValidationReport(
        report_id=f"report-adapter-case-{draft.draft_id}",
        case_id=draft.case_id,
        stage_id=draft.proposed_stage_context.stage_id,
        board_id=None,
        generated_at=utc_now(),
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=tuple(issues),
        validator_name=CASE_STRUCTURING_BRIDGE_VALIDATOR_NAME,
        validator_version=CASE_STRUCTURING_BRIDGE_VALIDATOR_VERSION,
        summary=_build_report_summary(
            success_message="Case structuring draft-source alignment validation passed.",
            issues=issues,
        ),
    )


def validate_evidence_atomization_draft_against_sources(
    draft: EvidenceAtomizationDraft,
    source_documents: tuple[SourceDocument, ...],
) -> StateValidationReport:
    base_report = validate_evidence_atoms_against_sources(
        evidence_atoms=draft.evidence_atoms,
        source_documents=source_documents,
    )

    issues: list[ValidationIssue] = list(base_report.issues)
    source_documents_by_id = {
        source_document.source_doc_id: source_document
        for source_document in source_documents
    }
    registered_source_doc_ids = set(source_documents_by_id)

    unknown_draft_source_doc_ids = tuple(
        sorted(set(draft.source_doc_ids) - registered_source_doc_ids)
    )
    if unknown_draft_source_doc_ids:
        issues.append(
            _build_issue(
                issue_id_prefix="issue-adapter-evidence-",
                index=len(issues) + 1,
                issue_code="adapter_bridge.evidence_draft_source_doc_not_registered",
                severity=ValidationSeverity.ERROR,
                message=(
                    "draft.source_doc_ids must be covered by registered source documents"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id=draft.draft_id,
                field_path="source_doc_ids",
                related_ids=unknown_draft_source_doc_ids,
                blocking=True,
            )
        )

    extraction_input_source_doc_ids = set(draft.extraction_activity.input_source_doc_ids)
    missing_in_extraction_activity = tuple(
        sorted(set(draft.source_doc_ids) - extraction_input_source_doc_ids)
    )
    if missing_in_extraction_activity:
        issues.append(
            _build_issue(
                issue_id_prefix="issue-adapter-evidence-",
                index=len(issues) + 1,
                issue_code="adapter_bridge.evidence_extraction_activity_source_doc_coverage_gap",
                severity=ValidationSeverity.ERROR,
                message=(
                    "extraction_activity.input_source_doc_ids must cover draft.source_doc_ids"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id=draft.extraction_activity.activity_id,
                field_path="extraction_activity.input_source_doc_ids",
                related_ids=missing_in_extraction_activity,
                blocking=True,
            )
        )

    has_blocking_issue = any(issue.blocking for issue in issues)
    return StateValidationReport(
        report_id=f"report-adapter-evidence-{draft.draft_id}",
        case_id=draft.case_id,
        stage_id=draft.stage_id,
        board_id=None,
        generated_at=utc_now(),
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=tuple(issues),
        validator_name=EVIDENCE_ATOMIZATION_BRIDGE_VALIDATOR_NAME,
        validator_version=EVIDENCE_ATOMIZATION_BRIDGE_VALIDATOR_VERSION,
        summary=_build_report_summary(
            success_message="Evidence atomization draft-source alignment validation passed.",
            issues=issues,
        ),
    )


def validate_adapter_drafts_against_sources(
    *,
    case_structuring_draft: CaseStructuringDraft | None = None,
    evidence_atomization_draft: EvidenceAtomizationDraft | None = None,
    source_documents: tuple[SourceDocument, ...],
) -> AdapterValidationBridgeResult:
    if case_structuring_draft is None and evidence_atomization_draft is None:
        return AdapterValidationBridgeResult(
            status=AdapterValidationBridgeStatus.FAILED,
            case_structuring_report=None,
            evidence_atomization_report=None,
            has_blocking_issue=True,
            summary="No adapter draft provided for validation bridge.",
        )

    try:
        case_report = None
        evidence_report = None

        if case_structuring_draft is not None:
            case_report = validate_case_structuring_draft_against_sources(
                case_structuring_draft,
                source_documents,
            )

        if evidence_atomization_draft is not None:
            evidence_report = validate_evidence_atomization_draft_against_sources(
                evidence_atomization_draft,
                source_documents,
            )

        has_blocking_issue = any(
            report is not None and report.has_blocking_issue
            for report in (case_report, evidence_report)
        )
        status = (
            AdapterValidationBridgeStatus.FAILED
            if has_blocking_issue
            else AdapterValidationBridgeStatus.PASSED
        )

        return AdapterValidationBridgeResult(
            status=status,
            case_structuring_report=case_report,
            evidence_atomization_report=evidence_report,
            has_blocking_issue=has_blocking_issue,
            summary=_build_bridge_summary(
                case_structuring_report=case_report,
                evidence_atomization_report=evidence_report,
                has_blocking_issue=has_blocking_issue,
            ),
        )
    except Exception as exc:  # pragma: no cover
        return AdapterValidationBridgeResult(
            status=AdapterValidationBridgeStatus.MANUAL_REVIEW,
            case_structuring_report=None,
            evidence_atomization_report=None,
            has_blocking_issue=True,
            summary=f"Adapter validation bridge raised unexpected error: {exc}",
        )


def _append_case_span_issues(
    *,
    issues: list[ValidationIssue],
    issue_id_prefix: str,
    target_id: str,
    source_doc_id: str,
    source_text: str,
    source_span_start: int | None,
    source_span_end: int | None,
    field_path_prefix: str,
    item_label: str,
    pair_issue_code: str,
    invalid_issue_code: str,
    out_of_bounds_issue_code: str,
) -> None:
    if (source_span_start is None) ^ (source_span_end is None):
        issues.append(
            _build_issue(
                issue_id_prefix=issue_id_prefix,
                index=len(issues) + 1,
                issue_code=pair_issue_code,
                severity=ValidationSeverity.ERROR,
                message=(
                    f"{item_label} source_span_start and source_span_end must be provided together"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id=target_id,
                field_path=f"{field_path_prefix}.source_span_start",
                related_ids=(source_doc_id,),
                blocking=True,
            )
        )
        return

    if source_span_start is None and source_span_end is None:
        return

    assert source_span_start is not None
    assert source_span_end is not None

    if source_span_start < 0 or source_span_end < 0 or source_span_start > source_span_end:
        issues.append(
            _build_issue(
                issue_id_prefix=issue_id_prefix,
                index=len(issues) + 1,
                issue_code=invalid_issue_code,
                severity=ValidationSeverity.ERROR,
                message=f"{item_label} source span is invalid",
                target_kind=ValidationTargetKind.OTHER,
                target_id=target_id,
                field_path=f"{field_path_prefix}.source_span_start",
                related_ids=(source_doc_id,),
                blocking=True,
            )
        )
        return

    if source_span_end > len(source_text):
        issues.append(
            _build_issue(
                issue_id_prefix=issue_id_prefix,
                index=len(issues) + 1,
                issue_code=out_of_bounds_issue_code,
                severity=ValidationSeverity.ERROR,
                message=(
                    f"{item_label} source span exceeds SourceDocument.raw_text length"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id=target_id,
                field_path=f"{field_path_prefix}.source_span_end",
                related_ids=(source_doc_id,),
                blocking=True,
            )
        )


def _build_issue(
    *,
    issue_id_prefix: str,
    index: int,
    issue_code: str,
    severity: ValidationSeverity,
    message: str,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str | None,
    related_ids: tuple[str, ...] = (),
    blocking: bool,
) -> ValidationIssue:
    return ValidationIssue(
        issue_id=f"{issue_id_prefix}{index:04d}",
        issue_code=issue_code,
        severity=severity,
        message=message,
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        related_ids=related_ids,
        blocking=blocking,
    )


def _build_report_summary(
    *,
    success_message: str,
    issues: list[ValidationIssue],
) -> str:
    if not issues:
        return success_message

    blocking_count = sum(1 for issue in issues if issue.blocking)
    non_blocking_count = len(issues) - blocking_count
    return (
        "Adapter draft-source alignment validation completed: "
        f"total={len(issues)}, blocking={blocking_count}, "
        f"non_blocking={non_blocking_count}."
    )


def _build_bridge_summary(
    *,
    case_structuring_report: StateValidationReport | None,
    evidence_atomization_report: StateValidationReport | None,
    has_blocking_issue: bool,
) -> str:
    parts: list[str] = []

    if case_structuring_report is not None:
        status = "failed" if case_structuring_report.has_blocking_issue else "passed"
        parts.append(f"case_structuring={status}")

    if evidence_atomization_report is not None:
        status = "failed" if evidence_atomization_report.has_blocking_issue else "passed"
        parts.append(f"evidence_atomization={status}")

    if not parts:
        return "No adapter draft report available."

    joined = ", ".join(parts)
    if has_blocking_issue:
        return f"Adapter validation bridge failed: {joined}."

    return f"Adapter validation bridge passed: {joined}."


__all__ = [
    "AdapterValidationBridgeResult",
    "AdapterValidationBridgeStatus",
    "validate_adapter_drafts_against_sources",
    "validate_case_structuring_draft_against_sources",
    "validate_evidence_atomization_draft_against_sources",
]