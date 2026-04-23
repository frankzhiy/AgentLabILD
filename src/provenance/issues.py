"""Phase 1-2 provenance issue primitives.

本模块仅承载 issue 结构与 issue 构造辅助函数。
"""

from __future__ import annotations

from dataclasses import dataclass

from ..schemas.validation import ValidationSeverity, ValidationTargetKind


@dataclass(frozen=True, slots=True)
class ProvenanceCheckIssue:
    """Structured provenance issue that is directly convertible to ValidationIssue."""

    issue_code: str
    severity: ValidationSeverity
    message: str
    target_kind: ValidationTargetKind
    target_id: str
    field_path: str | None = None
    related_ids: tuple[str, ...] = ()
    blocking: bool = True
    suggested_fix: str | None = None
    non_authoritative_note: str | None = None


def _make_issue(
    *,
    issue_code: str,
    severity: ValidationSeverity,
    message: str,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str | None = None,
    related_ids: tuple[str, ...] = (),
    blocking: bool,
    suggested_fix: str | None = None,
) -> ProvenanceCheckIssue:
    return ProvenanceCheckIssue(
        issue_code=issue_code,
        severity=severity,
        message=message,
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        related_ids=related_ids,
        blocking=blocking,
        suggested_fix=suggested_fix,
    )


def _missing_provenance_issue(
    *,
    target_kind: ValidationTargetKind,
    target_id: str,
    field_path: str,
    require_provenance: bool,
) -> ProvenanceCheckIssue:
    if require_provenance:
        return _make_issue(
            issue_code="provenance.missing_provenance",
            severity=ValidationSeverity.ERROR,
            message="provenance payload is required but missing",
            target_kind=target_kind,
            target_id=target_id,
            field_path=field_path,
            blocking=True,
            suggested_fix="attach structured provenance object for this target",
        )

    return _make_issue(
        issue_code="provenance.missing_provenance",
        severity=ValidationSeverity.WARNING,
        message="provenance payload is missing (backward-compatible warning)",
        target_kind=target_kind,
        target_id=target_id,
        field_path=field_path,
        blocking=False,
        suggested_fix="attach structured provenance object for improved traceability",
    )


def _normalize_extraction_method(value: object) -> str | None:
    """Normalize extraction method text for robust string/enum alignment checks."""

    if value is None:
        return None

    normalized = str(value).strip().lower()
    if not normalized:
        return None

    tokens = normalized.replace("-", " ").replace("_", " ").split()
    if not tokens:
        return None

    return "_".join(tokens)


__all__ = ["ProvenanceCheckIssue"]
