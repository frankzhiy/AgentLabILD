"""Phase 1-3 schema validator for Phase1StateEnvelope.

本模块职责：
1. 提供对 Phase1StateEnvelope 的外部 schema 校验入口。
2. 将原始 payload 的构造失败转换为结构化 StateValidationReport。
3. 保持无副作用：不修改输入、不写入存储。
"""

from __future__ import annotations

from datetime import datetime
from re import Pattern

from pydantic import ValidationError

from ..schemas.common import BOARD_ID_PATTERN, CASE_ID_PATTERN, STAGE_ID_PATTERN, STATE_ID_PATTERN
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import (
    StateValidationReport,
    ValidationIssue,
    ValidationSeverity,
    ValidationTargetKind,
)
from ..utils.time import utc_now
from .constants import (
    FALLBACK_BOARD_ID,
    FALLBACK_CASE_ID,
    FALLBACK_STAGE_ID,
    FALLBACK_STATE_ID,
)

SCHEMA_VALIDATOR_NAME = "phase1_schema_validator"
SCHEMA_VALIDATOR_VERSION = "1.3.0"

_ROOT_FIELD_TARGET_KIND_MAP: dict[str, ValidationTargetKind] = {
    "stage_context": ValidationTargetKind.STAGE_CONTEXT,
    "board_init": ValidationTargetKind.HYPOTHESIS_BOARD_INIT,
    "evidence_atoms": ValidationTargetKind.EVIDENCE_ATOM,
    "claim_references": ValidationTargetKind.CLAIM_REFERENCE,
    "hypotheses": ValidationTargetKind.HYPOTHESIS_STATE,
    "action_candidates": ValidationTargetKind.ACTION_CANDIDATE,
    "validation_report": ValidationTargetKind.STATE_VALIDATION_REPORT,
}

_COLLECTION_ID_FIELD_MAP: dict[str, str] = {
    "evidence_atoms": "evidence_id",
    "claim_references": "claim_ref_id",
    "hypotheses": "hypothesis_id",
    "action_candidates": "action_candidate_id",
}

_FALLBACK_TARGET_ID_BY_KIND: dict[ValidationTargetKind, str] = {
    ValidationTargetKind.PHASE1_STATE_ENVELOPE: FALLBACK_STATE_ID,
    ValidationTargetKind.STAGE_CONTEXT: FALLBACK_STAGE_ID,
    ValidationTargetKind.HYPOTHESIS_BOARD_INIT: FALLBACK_BOARD_ID,
    ValidationTargetKind.EVIDENCE_ATOM: "evidence-unknown",
    ValidationTargetKind.CLAIM_REFERENCE: "claim_ref-unknown",
    ValidationTargetKind.HYPOTHESIS_STATE: "hypothesis-unknown",
    ValidationTargetKind.ACTION_CANDIDATE: "action-unknown",
    ValidationTargetKind.STATE_VALIDATION_REPORT: "report-unknown",
    ValidationTargetKind.OTHER: "unknown",
}


def validate_phase1_schema(
    candidate: dict[str, object] | Phase1StateEnvelope,
    *,
    report_id: str | None = None,
    generated_at: datetime | None = None,
    validator_name: str = SCHEMA_VALIDATOR_NAME,
    validator_version: str = SCHEMA_VALIDATOR_VERSION,
) -> StateValidationReport:
    """Validate one candidate payload/envelope and return structured report."""

    if isinstance(candidate, Phase1StateEnvelope):
        return _build_report_from_envelope(
            envelope=candidate,
            issues=(),
            generated_at=generated_at,
            report_id=report_id,
            validator_name=validator_name,
            validator_version=validator_version,
        )

    if not isinstance(candidate, dict):
        issue = ValidationIssue(
            issue_id="issue-schema-0001",
            issue_code="schema.invalid_payload",
            severity=ValidationSeverity.ERROR,
            message=(
                "candidate payload must be dict[str, object] or Phase1StateEnvelope"
            ),
            target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
            target_id=FALLBACK_STATE_ID,
            blocking=True,
            suggested_fix="provide a structured payload dict aligned with Phase1StateEnvelope",
        )
        return _build_report_from_payload(
            payload=None,
            state_id=FALLBACK_STATE_ID,
            issues=(issue,),
            generated_at=generated_at,
            report_id=report_id,
            validator_name=validator_name,
            validator_version=validator_version,
        )

    try:
        envelope = Phase1StateEnvelope(**candidate)
    except ValidationError as exc:
        issues = _convert_validation_error_to_issues(exc=exc, payload=candidate)
        state_id = _extract_validated_id(
            candidate.get("state_id"),
            pattern=STATE_ID_PATTERN,
            fallback=FALLBACK_STATE_ID,
        )
        return _build_report_from_payload(
            payload=candidate,
            state_id=state_id,
            issues=issues,
            generated_at=generated_at,
            report_id=report_id,
            validator_name=validator_name,
            validator_version=validator_version,
        )

    return _build_report_from_envelope(
        envelope=envelope,
        issues=(),
        generated_at=generated_at,
        report_id=report_id,
        validator_name=validator_name,
        validator_version=validator_version,
    )


def _convert_validation_error_to_issues(
    *,
    exc: ValidationError,
    payload: dict[str, object],
) -> tuple[ValidationIssue, ...]:
    case_id = _extract_validated_id(
        payload.get("case_id"),
        pattern=CASE_ID_PATTERN,
        fallback=FALLBACK_CASE_ID,
    )
    stage_id = _extract_stage_id(payload)
    board_id = _extract_board_id(payload)
    state_id = _extract_validated_id(
        payload.get("state_id"),
        pattern=STATE_ID_PATTERN,
        fallback=FALLBACK_STATE_ID,
    )

    issues: list[ValidationIssue] = []

    for index, error_item in enumerate(exc.errors(include_url=False), start=1):
        loc = tuple(error_item.get("loc", ()))
        target_kind = _infer_target_kind(loc)
        error_type = str(error_item.get("type", ""))
        error_ctx = error_item.get("ctx")
        target_id = _infer_target_id(
            target_kind=target_kind,
            loc=loc,
            payload=payload,
            case_id=case_id,
            stage_id=stage_id,
            board_id=board_id,
            state_id=state_id,
        )
        issue_code = (
            "schema.model_error"
            if _is_model_level_error(
                loc=loc,
                error_type=error_type,
                error_ctx=error_ctx,
            )
            else "schema.field_error"
        )

        issues.append(
            ValidationIssue(
                issue_id=f"issue-schema-{index:04d}",
                issue_code=issue_code,
                severity=ValidationSeverity.ERROR,
                message=error_item.get("msg", "schema validation failed"),
                target_kind=target_kind,
                target_id=target_id,
                field_path=_format_field_path(loc),
                blocking=True,
            )
        )

    if not issues:
        return (
            ValidationIssue(
                issue_id="issue-schema-0001",
                issue_code="schema.model_error",
                severity=ValidationSeverity.ERROR,
                message="schema validation failed without structured error details",
                target_kind=ValidationTargetKind.PHASE1_STATE_ENVELOPE,
                target_id=state_id,
                blocking=True,
            ),
        )

    return tuple(issues)


def _build_report_from_envelope(
    *,
    envelope: Phase1StateEnvelope,
    issues: tuple[ValidationIssue, ...],
    generated_at: datetime | None,
    report_id: str | None,
    validator_name: str,
    validator_version: str,
) -> StateValidationReport:
    return _build_report(
        case_id=envelope.case_id,
        stage_id=envelope.stage_context.stage_id,
        board_id=envelope.board_init.board_id,
        state_id=envelope.state_id,
        issues=issues,
        generated_at=generated_at,
        report_id=report_id,
        validator_name=validator_name,
        validator_version=validator_version,
    )


def _build_report_from_payload(
    *,
    payload: dict[str, object] | None,
    state_id: str,
    issues: tuple[ValidationIssue, ...],
    generated_at: datetime | None,
    report_id: str | None,
    validator_name: str,
    validator_version: str,
) -> StateValidationReport:
    case_id = FALLBACK_CASE_ID
    stage_id = FALLBACK_STAGE_ID
    board_id: str | None = None

    if payload is not None:
        case_id = _extract_validated_id(
            payload.get("case_id"),
            pattern=CASE_ID_PATTERN,
            fallback=FALLBACK_CASE_ID,
        )
        stage_id = _extract_stage_id(payload)
        board_id = _extract_board_id(payload)

    return _build_report(
        case_id=case_id,
        stage_id=stage_id,
        board_id=board_id,
        state_id=state_id,
        issues=issues,
        generated_at=generated_at,
        report_id=report_id,
        validator_name=validator_name,
        validator_version=validator_version,
    )


def _build_report(
    *,
    case_id: str,
    stage_id: str,
    board_id: str | None,
    state_id: str,
    issues: tuple[ValidationIssue, ...],
    generated_at: datetime | None,
    report_id: str | None,
    validator_name: str,
    validator_version: str,
) -> StateValidationReport:
    has_blocking_issue = any(issue.blocking for issue in issues)

    if generated_at is None:
        generated_at = utc_now()

    if report_id is None:
        report_id = f"report-schema-{state_id}"

    if issues:
        summary = (
            "Schema validation failed: "
            f"total={len(issues)}, blocking={sum(1 for issue in issues if issue.blocking)}."
        )
    else:
        summary = "Schema validation passed."

    return StateValidationReport(
        report_id=report_id,
        case_id=case_id,
        stage_id=stage_id,
        board_id=board_id,
        generated_at=generated_at,
        is_valid=not has_blocking_issue,
        has_blocking_issue=has_blocking_issue,
        issues=issues,
        validator_name=validator_name,
        validator_version=validator_version,
        summary=summary,
    )


def _extract_validated_id(
    value: object,
    *,
    pattern: Pattern[str],
    fallback: str,
) -> str:
    maybe_id = _as_non_empty_str(value)
    if maybe_id is not None and pattern.fullmatch(maybe_id):
        return maybe_id
    return fallback


def _extract_stage_id(payload: dict[str, object]) -> str:
    stage_context = payload.get("stage_context")
    if not isinstance(stage_context, dict):
        return FALLBACK_STAGE_ID

    return _extract_validated_id(
        stage_context.get("stage_id"),
        pattern=STAGE_ID_PATTERN,
        fallback=FALLBACK_STAGE_ID,
    )


def _extract_board_id(payload: dict[str, object]) -> str | None:
    board_init = payload.get("board_init")
    if not isinstance(board_init, dict):
        return None

    board_id = _as_non_empty_str(board_init.get("board_id"))
    if board_id is None:
        return None
    if BOARD_ID_PATTERN.fullmatch(board_id):
        return board_id
    return None


def _infer_target_kind(loc: tuple[object, ...]) -> ValidationTargetKind:
    if not loc:
        return ValidationTargetKind.PHASE1_STATE_ENVELOPE

    first = loc[0]
    if isinstance(first, str):
        return _ROOT_FIELD_TARGET_KIND_MAP.get(
            first,
            ValidationTargetKind.PHASE1_STATE_ENVELOPE,
        )

    return ValidationTargetKind.PHASE1_STATE_ENVELOPE


def _infer_target_id(
    *,
    target_kind: ValidationTargetKind,
    loc: tuple[object, ...],
    payload: dict[str, object],
    case_id: str,
    stage_id: str,
    board_id: str | None,
    state_id: str,
) -> str:
    if target_kind is ValidationTargetKind.PHASE1_STATE_ENVELOPE:
        return state_id

    if target_kind is ValidationTargetKind.STAGE_CONTEXT:
        return stage_id

    if target_kind is ValidationTargetKind.HYPOTHESIS_BOARD_INIT:
        return board_id or FALLBACK_BOARD_ID

    if target_kind is ValidationTargetKind.STATE_VALIDATION_REPORT:
        report_payload = payload.get("validation_report")
        if isinstance(report_payload, dict):
            report_id = _as_non_empty_str(report_payload.get("report_id"))
            if report_id is not None:
                return report_id
        return _FALLBACK_TARGET_ID_BY_KIND[ValidationTargetKind.STATE_VALIDATION_REPORT]

    if loc:
        collection_name = loc[0]
        if isinstance(collection_name, str):
            item_id = _extract_collection_item_id(
                payload=payload,
                collection_name=collection_name,
                loc=loc,
            )
            if item_id is not None:
                return item_id

    return _FALLBACK_TARGET_ID_BY_KIND.get(target_kind, case_id)


def _extract_collection_item_id(
    *,
    payload: dict[str, object],
    collection_name: str,
    loc: tuple[object, ...],
) -> str | None:
    id_field = _COLLECTION_ID_FIELD_MAP.get(collection_name)
    if id_field is None:
        return None

    if len(loc) < 2 or not isinstance(loc[1], int):
        return None

    collection = payload.get(collection_name)
    if not isinstance(collection, (list, tuple)):
        return None

    index = loc[1]
    if index < 0 or index >= len(collection):
        return None

    item = collection[index]
    if not isinstance(item, dict):
        return None

    return _as_non_empty_str(item.get(id_field))


def _format_field_path(loc: tuple[object, ...]) -> str | None:
    if not loc:
        return None

    path = ""
    for part in loc:
        if isinstance(part, int):
            path += f"[{part}]"
            continue

        part_text = str(part)
        if not path:
            path = part_text
        else:
            path = f"{path}.{part_text}"

    return path or None


def _is_model_level_error(
    *,
    loc: tuple[object, ...],
    error_type: str,
    error_ctx: object,
) -> bool:
    """Classify model-level schema failures conservatively.

    Notes:
    - We intentionally treat object-scope errors (e.g. collection item level,
      root object level) as `schema.model_error` to avoid misclassifying
      model_validator consistency checks as field errors.
    - Missing required fields remain `schema.field_error`.
    """

    if not loc:
        return True

    if len(loc) == 1 and loc[0] in {"__root__", "model"}:
        return True

    first = loc[0]
    if isinstance(first, str) and first in _ROOT_FIELD_TARGET_KIND_MAP:
        if len(loc) == 1:
            return error_type != "missing"

        # Collection item object-level errors, e.g. evidence_atoms[0].
        if len(loc) == 2 and isinstance(loc[1], int):
            return True

        if len(loc) == 2 and loc[1] in {"__root__", "model"}:
            return True

    # Custom validator errors often carry an exception object in ctx.error.
    if isinstance(error_ctx, dict) and "error" in error_ctx:
        return len(loc) <= 2

    if error_type == "value_error":
        return len(loc) <= 2

    return False


def _as_non_empty_str(value: object) -> str | None:
    if not isinstance(value, str):
        return None

    cleaned = value.strip()
    return cleaned or None


__all__ = [
    "SCHEMA_VALIDATOR_NAME",
    "SCHEMA_VALIDATOR_VERSION",
    "validate_phase1_schema",
]