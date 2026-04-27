"""Phase 1-2 provenance validator.

本模块职责：
1. 调用 provenance checker 收集结构化 issue。
2. 将 issue 转换为 ValidationIssue。
3. 生成可直接用于写入门禁的 StateValidationReport（本任务仅建模，不实现 state_writer）。
"""

from __future__ import annotations

from datetime import datetime

from ..provenance.checker import ProvenanceCheckIssue, check_phase1_provenance
from ..schemas.common import find_duplicate_items
from ..schemas.evidence import EvidenceAtom
from ..schemas.intake import SourceDocument
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from ..intake.validators import validate_source_document_contains_excerpt
from ..utils.time import utc_now
from .constants import FALLBACK_CASE_ID, FALLBACK_STAGE_ID

DEFAULT_VALIDATOR_NAME = "phase1_provenance_validator"
DEFAULT_VALIDATOR_VERSION = "1.2.0"
SOURCE_ALIGNMENT_VALIDATOR_NAME = "phase1_evidence_source_alignment_validator"
SOURCE_ALIGNMENT_VALIDATOR_VERSION = "1.0.0"


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
        generated_at = utc_now()

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


def validate_evidence_atoms_against_sources(
    evidence_atoms: tuple[EvidenceAtom, ...],
    source_documents: tuple[SourceDocument, ...],
) -> StateValidationReport:
    """Validate EvidenceAtom source linkage against registered SourceDocument."""

    issues: list[ValidationIssue] = []

    source_doc_id_duplicates = find_duplicate_items(
        source_document.source_doc_id for source_document in source_documents
    )
    if source_doc_id_duplicates:
        issues.append(
            _build_source_alignment_issue(
                index=len(issues) + 1,
                issue_code="provenance.duplicate_source_document_id",
                severity=ValidationSeverity.ERROR,
                message=(
                    "Source document registry has duplicate source_doc_id values: "
                    + ", ".join(source_doc_id_duplicates)
                    + "."
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id="source_document_registry",
                field_path="source_documents.source_doc_id",
                related_ids=source_doc_id_duplicates,
                blocking=True,
            )
        )

    source_case_ids = tuple(sorted({source.case_id for source in source_documents}))
    if len(source_case_ids) > 1:
        issues.append(
            _build_source_alignment_issue(
                index=len(issues) + 1,
                issue_code="provenance.source_document_case_mismatch",
                severity=ValidationSeverity.ERROR,
                message=(
                    "source_documents must align to a single case_id for one validation run"
                ),
                target_kind=ValidationTargetKind.OTHER,
                target_id="source_document_registry",
                field_path="source_documents.case_id",
                related_ids=source_case_ids,
                blocking=True,
            )
        )

    source_documents_by_id = {
        source_document.source_doc_id: source_document
        for source_document in source_documents
    }

    for evidence_index, evidence_atom in enumerate(evidence_atoms):
        source_document = source_documents_by_id.get(evidence_atom.source_doc_id)
        if source_document is None:
            issues.append(
                _build_source_alignment_issue(
                    index=len(issues) + 1,
                    issue_code="provenance.source_doc_not_registered",
                    severity=ValidationSeverity.ERROR,
                    message=(
                        "Evidence source_doc_id is not present in registered source documents"
                    ),
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=evidence_atom.evidence_id,
                    field_path=f"evidence_atoms[{evidence_index}].source_doc_id",
                    related_ids=(evidence_atom.source_doc_id,),
                    blocking=True,
                )
            )
            continue

        try:
            is_aligned = validate_source_document_contains_excerpt(
                source_document,
                evidence_atom.raw_excerpt,
                source_span_start=evidence_atom.source_span_start,
                source_span_end=evidence_atom.source_span_end,
            )
        except ValueError as exc:
            issues.append(
                _build_source_alignment_issue(
                    index=len(issues) + 1,
                    issue_code="provenance.source_span_invalid",
                    severity=ValidationSeverity.ERROR,
                    message=f"Invalid source span for evidence atom: {exc}",
                    target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                    target_id=evidence_atom.evidence_id,
                    field_path=f"evidence_atoms[{evidence_index}].source_span_start",
                    related_ids=(evidence_atom.source_doc_id,),
                    blocking=True,
                )
            )
            continue

        if is_aligned:
            continue

        if (
            evidence_atom.source_span_start is not None
            and evidence_atom.source_span_end is not None
        ):
            issue_code = "provenance.source_span_excerpt_mismatch"
            message = (
                "Evidence raw_excerpt must exactly match SourceDocument substring "
                "at source_span_start:source_span_end"
            )
            field_path = f"evidence_atoms[{evidence_index}].source_span_start"
        else:
            issue_code = "provenance.raw_excerpt_not_found"
            message = (
                "Evidence raw_excerpt must be a substring of SourceDocument.raw_text"
            )
            field_path = f"evidence_atoms[{evidence_index}].raw_excerpt"

        issues.append(
            _build_source_alignment_issue(
                index=len(issues) + 1,
                issue_code=issue_code,
                severity=ValidationSeverity.ERROR,
                message=message,
                target_kind=ValidationTargetKind.EVIDENCE_ATOM,
                target_id=evidence_atom.evidence_id,
                field_path=field_path,
                related_ids=(evidence_atom.source_doc_id,),
                blocking=True,
            )
        )

    stage_ids = tuple(sorted({evidence.stage_id for evidence in evidence_atoms}))
    report_stage_id = stage_ids[0] if len(stage_ids) == 1 else FALLBACK_STAGE_ID

    if len(stage_ids) > 1:
        issues.append(
            _build_source_alignment_issue(
                index=len(issues) + 1,
                issue_code="provenance.evidence_stage_mismatch",
                severity=ValidationSeverity.WARNING,
                message="evidence_atoms include multiple stage_id values in one run",
                target_kind=ValidationTargetKind.OTHER,
                target_id="evidence_atom_registry",
                field_path="evidence_atoms.stage_id",
                related_ids=stage_ids,
                blocking=False,
            )
        )

    report_case_id = source_case_ids[0] if len(source_case_ids) == 1 else FALLBACK_CASE_ID
    has_blocking_issue = any(issue.blocking for issue in issues)

    if issues:
        summary = (
            "Evidence-source alignment validation completed: "
            f"total={len(issues)}, "
            f"blocking={sum(1 for issue in issues if issue.blocking)}, "
            f"non_blocking={sum(1 for issue in issues if not issue.blocking)}."
        )
    else:
        summary = "Evidence-source alignment validation passed."

    return StateValidationReport(
        report_id=f"report-provenance-source-alignment-{report_stage_id}",
        case_id=report_case_id,
        stage_id=report_stage_id,
        board_id=None,
        generated_at=utc_now(),
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=tuple(issues),
        validator_name=SOURCE_ALIGNMENT_VALIDATOR_NAME,
        validator_version=SOURCE_ALIGNMENT_VALIDATOR_VERSION,
        summary=summary,
    )


def _build_source_alignment_issue(
    *,
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
        issue_id=f"issue-provenance-source-{index:04d}",
        issue_code=issue_code,
        severity=severity,
        message=message,
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        related_ids=related_ids,
        blocking=blocking,
    )


__all__ = [
    "DEFAULT_VALIDATOR_NAME",
    "DEFAULT_VALIDATOR_VERSION",
    "SOURCE_ALIGNMENT_VALIDATOR_NAME",
    "SOURCE_ALIGNMENT_VALIDATOR_VERSION",
    "build_provenance_validation_issues",
    "convert_provenance_issues_to_validation_issues",
    "validate_evidence_atoms_against_sources",
    "validate_phase1_provenance",
]
