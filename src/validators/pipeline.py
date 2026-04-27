"""Phase 1-3 unified validation pipeline for Phase1StateEnvelope candidates.

This module orchestrates existing validators in a fixed order and returns
structured aggregate metadata for future write-gate integration.
"""

from __future__ import annotations

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    SkipValidation,
    ValidationError,
    field_validator,
    model_validator,
)

from ..schemas.common import (
    STATE_ID_PATTERN,
    NonEmptyStr,
    normalize_optional_text,
    validate_id_pattern,
)
from ..schemas.state import Phase1StateEnvelope
from ..schemas.validation import StateValidationReport
from .constants import FALLBACK_STATE_ID
from .provenance_validator import validate_phase1_provenance
from .schema_validator import validate_phase1_schema
from .temporal_validator import validate_phase1_temporal
from .unsupported_claims import validate_phase1_unsupported_claims

VALIDATOR_STAGE_SCHEMA = "schema"
VALIDATOR_STAGE_PROVENANCE = "provenance"
VALIDATOR_STAGE_TEMPORAL = "temporal"
VALIDATOR_STAGE_UNSUPPORTED_CLAIM = "unsupported_claim"

FULL_VALIDATOR_EXECUTION_ORDER: tuple[str, ...] = (
    VALIDATOR_STAGE_SCHEMA,
    VALIDATOR_STAGE_PROVENANCE,
    VALIDATOR_STAGE_TEMPORAL,
    VALIDATOR_STAGE_UNSUPPORTED_CLAIM,
)
SCHEMA_ONLY_EXECUTION_ORDER: tuple[str, ...] = (VALIDATOR_STAGE_SCHEMA,)


class ValidationPipelinePolicy(BaseModel):
    """Pipeline-level validation policy for configurable validator strictness."""

    model_config = ConfigDict(extra="forbid", frozen=True)

    require_provenance: bool = False


class Phase1ValidationPipelineResult(BaseModel):
    """Structured output of one candidate validation pipeline run.

    This result is a validator-orchestration artifact only:
    - it does not decide persistence directly,
    - it does not mutate candidate state,
    - it does not write to storage.
    """

    model_config = ConfigDict(extra="forbid", frozen=True, str_strip_whitespace=True)

    candidate_state_id: NonEmptyStr
    candidate_envelope: SkipValidation[Phase1StateEnvelope] | None = None
    reports: tuple[StateValidationReport, ...] = Field(default_factory=tuple)
    has_blocking_issue: bool
    validator_execution_order: tuple[str, ...] = Field(default_factory=tuple)
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
    def validate_pipeline_result_consistency(self) -> "Phase1ValidationPipelineResult":
        if self.candidate_envelope is not None:
            if not isinstance(self.candidate_envelope, Phase1StateEnvelope):
                raise ValueError(
                    "candidate_envelope must be Phase1StateEnvelope or None"
                )

            if self.candidate_envelope.state_id != self.candidate_state_id:
                raise ValueError(
                    "candidate_state_id must match candidate_envelope.state_id"
                )

        if not self.reports:
            raise ValueError("reports must contain at least one validation report")

        if len(self.validator_execution_order) != len(self.reports):
            raise ValueError(
                "validator_execution_order length must equal reports length"
            )

        derived_blocking = any(report.has_blocking_issue for report in self.reports)
        if self.has_blocking_issue != derived_blocking:
            raise ValueError(
                "has_blocking_issue must match reports[].has_blocking_issue"
            )

        if self.candidate_envelope is None and len(self.reports) > 1:
            raise ValueError(
                "candidate_envelope is required when downstream validators run"
            )

        return self


def validate_phase1_candidate_pipeline(
    candidate: dict[str, object] | Phase1StateEnvelope,
    *,
    require_provenance: bool | None = None,
    policy: ValidationPipelinePolicy | None = None,
) -> Phase1ValidationPipelineResult:
    """Run schema/provenance/temporal/unsupported-claim validators in order.

    Order is fixed:
    1. schema
    2. provenance
    3. temporal
    4. unsupported_claim

    Short-circuit behavior:
    - If raw payload schema fails, return schema report only.
    """

    resolved_policy = _resolve_pipeline_policy(
        policy=policy,
        require_provenance=require_provenance,
    )

    if isinstance(candidate, Phase1StateEnvelope):
        return _run_full_pipeline(
            envelope=candidate,
            candidate_state_id=candidate.state_id,
            policy=resolved_policy,
        )

    if not isinstance(candidate, dict):
        schema_report = validate_phase1_schema(candidate)  # type: ignore[arg-type]
        return _build_pipeline_result(
            candidate_state_id=FALLBACK_STATE_ID,
            candidate_envelope=None,
            reports=(schema_report,),
            validator_execution_order=SCHEMA_ONLY_EXECUTION_ORDER,
        )

    candidate_state_id = _derive_candidate_state_id(candidate)
    schema_report = validate_phase1_schema(candidate)
    if schema_report.has_blocking_issue:
        return _build_pipeline_result(
            candidate_state_id=candidate_state_id,
            candidate_envelope=None,
            reports=(schema_report,),
            validator_execution_order=SCHEMA_ONLY_EXECUTION_ORDER,
        )

    try:
        envelope = Phase1StateEnvelope(**candidate)
    except ValidationError:
        fallback_schema_report = validate_phase1_schema(candidate)
        return _build_pipeline_result(
            candidate_state_id=candidate_state_id,
            candidate_envelope=None,
            reports=(fallback_schema_report,),
            validator_execution_order=SCHEMA_ONLY_EXECUTION_ORDER,
        )

    return _run_full_pipeline(
        envelope=envelope,
        candidate_state_id=candidate_state_id,
        policy=resolved_policy,
        schema_report=schema_report,
    )


def _run_full_pipeline(
    *,
    envelope: Phase1StateEnvelope,
    candidate_state_id: str,
    policy: ValidationPipelinePolicy,
    schema_report: StateValidationReport | None = None,
) -> Phase1ValidationPipelineResult:
    if schema_report is None:
        schema_report = validate_phase1_schema(envelope)

    provenance_report = validate_phase1_provenance(
        envelope,
        require_provenance=policy.require_provenance,
    )
    temporal_report = validate_phase1_temporal(envelope)
    unsupported_claim_report = validate_phase1_unsupported_claims(envelope)

    reports = (
        schema_report,
        provenance_report,
        temporal_report,
        unsupported_claim_report,
    )

    return _build_pipeline_result(
        candidate_state_id=candidate_state_id,
        candidate_envelope=envelope,
        reports=reports,
        validator_execution_order=FULL_VALIDATOR_EXECUTION_ORDER,
    )


def _build_pipeline_result(
    *,
    candidate_state_id: str,
    candidate_envelope: Phase1StateEnvelope | None,
    reports: tuple[StateValidationReport, ...],
    validator_execution_order: tuple[str, ...],
) -> Phase1ValidationPipelineResult:
    has_blocking_issue = any(report.has_blocking_issue for report in reports)

    return Phase1ValidationPipelineResult(
        candidate_state_id=candidate_state_id,
        candidate_envelope=candidate_envelope,
        reports=reports,
        has_blocking_issue=has_blocking_issue,
        validator_execution_order=validator_execution_order,
        summary=_build_pipeline_summary(
            candidate_state_id=candidate_state_id,
            reports=reports,
            validator_execution_order=validator_execution_order,
        ),
    )


def _build_pipeline_summary(
    *,
    candidate_state_id: str,
    reports: tuple[StateValidationReport, ...],
    validator_execution_order: tuple[str, ...],
) -> str:
    if validator_execution_order == SCHEMA_ONLY_EXECUTION_ORDER:
        if reports[0].has_blocking_issue:
            return (
                "Schema validation failed; downstream validators were skipped: "
                f"candidate_state_id={candidate_state_id}."
            )

        return (
            "Schema-only validation pipeline completed: "
            f"candidate_state_id={candidate_state_id}."
        )

    blocking_report_count = sum(1 for report in reports if report.has_blocking_issue)
    invalid_report_count = sum(1 for report in reports if not report.is_valid)

    return (
        "Phase1 candidate validation pipeline completed: "
        f"candidate_state_id={candidate_state_id}, "
        f"executed={','.join(validator_execution_order)}, "
        f"total_reports={len(reports)}, "
        f"invalid_reports={invalid_report_count}, "
        f"blocking_reports={blocking_report_count}."
    )


def _resolve_pipeline_policy(
    *,
    policy: ValidationPipelinePolicy | None,
    require_provenance: bool | None,
) -> ValidationPipelinePolicy:
    resolved_policy = policy if policy is not None else ValidationPipelinePolicy()

    if require_provenance is None:
        return resolved_policy

    if resolved_policy.require_provenance == require_provenance:
        return resolved_policy

    return resolved_policy.model_copy(
        update={"require_provenance": require_provenance}
    )


def _derive_candidate_state_id(candidate: dict[str, object]) -> str:
    raw_state_id = candidate.get("state_id")
    if not isinstance(raw_state_id, str):
        return FALLBACK_STATE_ID

    cleaned_state_id = raw_state_id.strip()
    if not cleaned_state_id:
        return FALLBACK_STATE_ID

    if STATE_ID_PATTERN.fullmatch(cleaned_state_id):
        return cleaned_state_id

    return FALLBACK_STATE_ID


__all__ = [
    "FULL_VALIDATOR_EXECUTION_ORDER",
    "Phase1ValidationPipelineResult",
    "SCHEMA_ONLY_EXECUTION_ORDER",
    "ValidationPipelinePolicy",
    "VALIDATOR_STAGE_PROVENANCE",
    "VALIDATOR_STAGE_SCHEMA",
    "VALIDATOR_STAGE_TEMPORAL",
    "VALIDATOR_STAGE_UNSUPPORTED_CLAIM",
    "validate_phase1_candidate_pipeline",
]
