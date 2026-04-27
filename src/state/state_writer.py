"""Phase 1-3 validator-gated state writer orchestration.

The writer stays intentionally thin:
1. run validation pipeline,
2. derive write decision,
3. optionally persist accepted envelope via sink policy.

No event sourcing, repair, replay, or storage integration is implemented here.
"""

from __future__ import annotations

from ..schemas.state import Phase1StateEnvelope
from ..validators.pipeline import (
    Phase1ValidationPipelineResult,
    ValidationPipelinePolicy,
    validate_phase1_candidate_pipeline,
)
from .sinks import NoOpStateSink, StateSink
from .write_decision import WriteDecision
from .write_policy import WritePolicy
from .write_status import WriteDecisionStatus


def attempt_phase1_write(
    candidate: dict[str, object] | Phase1StateEnvelope,
    *,
    policy: WritePolicy | None = None,
    sink: StateSink | None = None,
    validation_policy: ValidationPipelinePolicy | None = None,
    require_provenance: bool | None = None,
) -> WriteDecision:
    """Attempt one validator-gated Phase1 state write.

    Behavior:
    1. Always run validation pipeline first.
    2. Derive status from pipeline reports.
    3. Persist only accepted decisions when WriteDecision resolves should_persist=True.

    Note:
    - WriteDecision describes validation-gate outcome only.
    - Persistence exceptions are intentionally not swallowed and bubble up.
    """

    resolved_policy = policy if policy is not None else WritePolicy()
    resolved_sink: StateSink = sink if sink is not None else NoOpStateSink()

    pipeline_result = validate_phase1_candidate_pipeline(
        candidate,
        policy=validation_policy,
        require_provenance=require_provenance,
    )

    status = _derive_write_status(pipeline_result)
    accepted_envelope = _derive_accepted_envelope(pipeline_result, status=status)

    decision = WriteDecision(
        candidate_state_id=pipeline_result.candidate_state_id,
        status=status,
        policy=resolved_policy,
        accepted_envelope=accepted_envelope,
        reports=pipeline_result.reports,
        summary=_build_write_summary(
            pipeline_result=pipeline_result,
            status=status,
        ),
    )

    if decision.should_persist and decision.accepted_envelope is not None:
        # Keep persistence failure behavior explicit: sink exceptions bubble to caller.
        resolved_sink.persist(decision.accepted_envelope)

    return decision


def _derive_write_status(
    pipeline_result: Phase1ValidationPipelineResult,
) -> WriteDecisionStatus:
    if pipeline_result.has_blocking_issue:
        return WriteDecisionStatus.REJECTED

    if all(report.is_valid for report in pipeline_result.reports):
        return WriteDecisionStatus.ACCEPTED

    return WriteDecisionStatus.MANUAL_REVIEW


def _derive_accepted_envelope(
    pipeline_result: Phase1ValidationPipelineResult,
    *,
    status: WriteDecisionStatus,
) -> Phase1StateEnvelope | None:
    if status is not WriteDecisionStatus.ACCEPTED:
        return None

    return pipeline_result.candidate_envelope


def _build_write_summary(
    *,
    pipeline_result: Phase1ValidationPipelineResult,
    status: WriteDecisionStatus,
) -> str:
    blocking_report_count = sum(
        1 for report in pipeline_result.reports if report.has_blocking_issue
    )
    invalid_report_count = sum(
        1 for report in pipeline_result.reports if not report.is_valid
    )

    return (
        "Write gate decision: "
        f"status={status.value}, "
        f"candidate_state_id={pipeline_result.candidate_state_id}, "
        f"reports={len(pipeline_result.reports)}, "
        f"invalid_reports={invalid_report_count}, "
        f"blocking_reports={blocking_report_count}."
    )


__all__ = ["attempt_phase1_write"]
